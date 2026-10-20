"""Schema-grounded conversational *drafts*, never automatic dashboard writes.

Interpret business visualization requests against the same semantic catalog and
preview engine as the manual builder. An ambiguous request returns a question
rather than silently selecting a metric or entity. This module NEVER persists.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.database.database_manager import database_manager
from app.visualizations.semantic_catalog import get_semantic_visualization_catalog
from app.visualizations.visualization_service import (
    VisualizationDefinition,
    VisualizationFilter,
    preview_visualization,
)
from app.visualizations.visualization_store import _source_key


ROLE_ALIASES = {
    "sales": ("venta", "ventas", "sales"),
    "sales_details": ("detalle de ventas",),
    "appointments": ("cita", "citas", "consultas", "appointment", "appointments"),
    "enrollments": ("inscripcion", "inscripciones", "matricula", "matriculas", "enrollment"),
    "students": ("estudiante", "estudiantes", "alumnos", "students"),
    "grades": ("nota", "notas", "calificacion", "calificaciones", "grades"),
    "attendance": ("asistencia", "attendance"),
    "trips": ("viaje", "viajes", "vuelo", "vuelos", "trips", "flights"),
    "tickets": ("boleto", "boletos", "pasajes", "tickets"),
    "reservations": ("reserva", "reservas", "reservacion", "reservaciones", "bookings"),
    "orders": ("pedido", "pedidos", "orden", "ordenes", "orders"),
    "invoices": ("factura", "facturas", "invoices"),
    "payments": ("pago", "pagos", "payments"),
    "transactions": ("transaccion", "transacciones", "movimiento", "movimientos"),
    "production_orders": ("produccion", "ordenes de produccion", "production"),
    "employees": ("empleado", "empleados", "trabajador", "trabajadores"),
    "payroll": ("nomina", "planilla", "payroll"),
    "patients": ("paciente", "pacientes", "patients"),
    "products": ("producto", "productos", "products"),
    "customers": ("cliente", "clientes", "customers"),
    "inventory": ("inventario", "existencias", "stock"),
}


def _normalize(value: str) -> str:
    ascii_text = "".join(char for char in unicodedata.normalize("NFKD", value.lower())
                         if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9_]+", " ", ascii_text)).strip()


def _contains(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(_normalize(term)) + r"(?!\w)", text))


def is_visualization_creation_request(question: str) -> bool:
    text = _normalize(question)
    action = any(_contains(text, word) for word in (
        "crea", "crear", "creame", "haz", "hacer", "genera", "generar",
        "grafica", "grafico", "muestrame", "visualiza", "visualizar",
        "construye", "dibuja", "prepara", "create", "show", "plot", "make",
    ))
    target = any(_contains(text, word) for word in (
        "grafica", "grafico", "diagrama", "visualizacion", "chart",
        "graph", "tabla", "table", "kpi", "indicador", "barras", "lineas",
    ))
    # Preserve existing text-question behavior for statements about charts.
    return action and target and not any(
        text.startswith(prefix) for prefix in (
            "por que", "que significa", "explica como", "como crear",
            "what is", "how do i", "que es",
        )
    )


def _visual_type(text: str) -> str:
    if any(_contains(text, part) for part in ("tabla", "table")):
        return "table"
    if any(_contains(text, part) for part in ("lineas", "linea", "line", "tendencia", "trend")):
        return "line"
    if any(_contains(text, part) for part in ("dona", "donut", "pastel", "circular", "pie chart")):
        return "donut"
    if any(_contains(text, part) for part in ("indicador", "kpi", "tarjeta")):
        return "kpi"
    return "bar"


def _pick_entity(text: str, entities: list[dict]) -> dict:
    subject = re.split(r"\bpor (?:mes|ano|dia|fecha|estado|tipo|categoria|producto|cliente|departamento|metodo|semana)\b", text)[0]
    matches = []
    for item in entities:
        role = item.get("semantic_role")
        labels = [item.get("label") or "", item.get("table") or "",
                  (role or "").replace("_", " ")]
        labels.extend(ROLE_ALIASES.get(role, ()))
        unique = {_normalize(label) for label in labels if label and len(_normalize(label)) >= 3}
        strength = max((
            8 if _contains(subject, label) else 3
            for label in unique if _contains(text, label)
        ), default=0)
        if strength:
            matches.append((strength, bool(role), item))
    if not matches:
        raise ValueError(
            "¿Qué entidad del negocio quieres representar? "
            "Indica una de las que reconoce tu base de datos, por ejemplo ventas, citas o inscripciones."
        )
    matches.sort(key=lambda group: (group[0], group[1]), reverse=True)
    highest = matches[0][0:2]
    winners = [entry for score, semantic, entry in matches if (score, semantic) == highest]
    if len(winners) != 1:
        raise ValueError(
            "La solicitud coincide con varias entidades: "
            + ", ".join(item["label"] for item in winners[:4])
            + ". Especifica cuál deseas analizar."
        )
    return winners[0]


def _choose_date(entity: dict) -> dict:
    dates = [
        item for item in entity.get("fields", [])
        if item.get("kind") == "date" or item.get("semantic") == "date"
    ]
    if len(dates) != 1:
        raise ValueError(
            "Para agrupar o filtrar por fecha necesito una única columna temporal "
            f"verificable en «{entity['label']}». Revísala en el constructor."
        )
    return dates[0]


def _choose_dimension(text: str, entity: dict, visual_type: str) -> tuple[dict | None, str]:
    if visual_type == "kpi":
        return None, "raw"
    if any(_contains(text, phrase) for phrase in ("por mes", "mensual", "monthly", "by month")):
        return _choose_date(entity), "month"
    if any(_contains(text, phrase) for phrase in ("por ano", "anual", "yearly", "by year")):
        return _choose_date(entity), "year"
    if any(_contains(text, phrase) for phrase in ("por fecha", "por dia", "diario", "daily")):
        return _choose_date(entity), "raw"

    pieces = re.findall(r"\b(?:por|segun|by)\s+([a-z_]+)", text)
    if not pieces:
        if visual_type == "table":
            return None, "raw"
        raise ValueError(
            "¿Cómo quieres agrupar los datos? Indica, por ejemplo, «por mes», "
            "«por estado» o «por categoría»."
        )
    requested = _normalize(pieces[-1])
    matches = [
        item for item in entity.get("dimensions", [])
        if any(_contains(requested, token) for token in (
            item.get("label") or "", item.get("key") or "",
            item.get("semantic") or "",
        ))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"No pude identificar de forma inequívoca la dimensión «{requested}» "
            f"en «{entity['label']}». Selecciona una columna válida en el creador."
        )
    return matches[0], "raw"


def _choose_metric(text: str, entity: dict) -> tuple[dict | None, str]:
    metrics = entity.get("metrics") or []
    count_terms = ("cantidad de registros", "numero de", "cantidad de ventas",
                   "numero de ventas", "conteo", "cuantos", "cuantas",
                   "cantidad de citas", "how many", "record count")
    if any(_contains(text, phrase) for phrase in count_terms):
        return None, "count"
    average = any(_contains(text, part) for part in ("promedio", "media", "average"))
    sum_intent = any(_contains(text, part) for part in (
        "importe", "ingreso", "ingresos", "recaudacion", "facturacion",
        "monto", "dinero", "total de ventas", "revenue", "amount", "unidades",
        "cantidad producida", "volumen", "sum",
    ))
    sales = entity.get("semantic_role") == "sales"
    desired = []
    if average or sum_intent or sales:
        expected_semantics = (
            {"quantity"} if any(_contains(text, token) for token in
                                ("unidades", "produccion", "cantidad producida"))
            else {"total", "amount", "price", "value"}
        )
        desired = [item for item in metrics if item.get("semantic") in expected_semantics]
        if not desired:
            desired = [item for item in metrics if any(
                _contains(_normalize(item.get("key", "")), phrase) for phrase in
                (("cantidad", "quantity", "unidades") if "quantity" in expected_semantics
                 else ("total", "monto", "importe", "amount", "valor"))
            )]
        if len(desired) != 1:
            raise ValueError(
                f"No puedo identificar una única métrica numérica para «{entity['label']}». "
                "Indica el campo y el cálculo (suma o promedio) o revísalo en el creador."
            )
        return desired[0], "avg" if average else "sum"
    # Explicitly named numerical metric (e.g. promedio de calificaciones)
    return None, "count"


def _year_bounds(text: str, entity: dict) -> list[VisualizationFilter]:
    years = sorted({int(y) for y in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)})
    if not years:
        return []
    if len(years) > 2 or (len(years) == 2 and not any(
        _contains(text, term) for term in ("entre", "desde", "hasta", "between", "from", "to")
    )):
        raise ValueError("Especifica un año o un rango claro de dos años para filtrar la gráfica.")
    date_field = _choose_date(entity)
    first, last = years[0], years[-1]
    if last - first > 10:
        raise ValueError("El rango solicitado supera diez años; acótalo antes de crear la gráfica.")
    return [
        VisualizationFilter(table=entity["table"], column=date_field["key"],
                            operator="gte", value=f"{first}-01-01"),
        VisualizationFilter(table=entity["table"], column=date_field["key"],
                            operator="lt", value=f"{last + 1}-01-01"),
    ]


def _placement(text: str) -> dict:
    dashboard = any(_contains(text, word) for word in ("dashboard", "tablero", "panel principal"))
    analytics = any(_contains(text, word) for word in ("analitica", "analisis", "analytics"))
    # When no explicit placement is requested, default to the builder's
    # existing Analytics choice. The user may change it before saving.
    return {"dashboard": dashboard, "analytics": analytics or not dashboard}


def _customer_rank_request(text: str) -> bool:
    """Business customer rankings are *sales-based*, not customer row counts."""
    return (
        any(_contains(text, word) for word in ("cliente", "clientes", "customers", "customer"))
        and any(_contains(text, word) for word in (
            "compra", "compras", "compran", "compraron", "gastaron", "gastan",
            "gasto", "gastos", "spend", "spent", "buy", "purchases",
        ))
        and any(_contains(text, word) for word in (
            "menos", "menor", "menores", "mas", "mayor", "mayores",
            "top", "bottom", "least", "most",
        ))
    )


def _customer_metric_kind(text: str) -> str:
    """Resolve spending vs. frequency; ambiguous 'compran menos' asks instead."""
    if any(_contains(text, term) for term in ("por categoria", "por category", "by category")):
        raise ValueError(
            "Tu solicitud era un ranking de clientes, no de categorías. "
            "¿Quieres los cinco clientes con menor importe gastado o con menor número de compras?"
        )
    spending = any(_contains(text, term) for term in (
        "importe", "monto", "dinero", "gasto", "gastaron", "gastan", "gastado",
        "facturacion", "valor comprado", "total gastado", "spent", "amount",
        "revenue", "dinero gastado",
    ))
    frequency = any(_contains(text, term) for term in (
        "cantidad de compras", "numero de compras", "numero de pedidos",
        "cantidad de pedidos", "frecuencia", "veces que compraron",
        "cuantas compras", "compras realizadas", "purchase count",
        "number of purchases", "fewest purchases", "menos compras",
    ))
    if spending and frequency:
        raise ValueError(
            "Mencionaste tanto importe como frecuencia. ¿Quieres ordenar por "
            "dinero gastado o por cantidad de compras?"
        )
    if not spending and not frequency:
        raise ValueError(
            "Para crear el ranking de clientes necesito una aclaración: "
            "¿«compran menos» significa menor importe gastado o menor número "
            "de compras? Responde «por importe» o «por cantidad de compras»."
        )
    return "amount" if spending else "count"


def _rank_limit(text: str) -> int:
    match = re.search(
        r"\b(?:los|las|top|bottom)\s+(\d{1,3})\b|\b(\d{1,3})\s+(?:clientes|customers)\b",
        text,
    )
    if not match:
        return 5
    value = int(match.group(1) or match.group(2))
    if not 1 <= value <= 100:
        raise ValueError("El ranking debe incluir entre 1 y 100 clientes.")
    return value


def _customer_ranking(text: str, catalog: dict) -> tuple[VisualizationDefinition, str, str]:
    kind = _customer_metric_kind(text)
    entities = catalog.get("entities") or []
    sales = [item for item in entities if item.get("semantic_role") == "sales"]
    customers = [item for item in entities if item.get("semantic_role") == "customers"]
    if len(sales) != 1 or len(customers) != 1:
        raise ValueError(
            "No puedo identificar una única tabla de ventas y clientes "
            "para construir un ranking verificable."
        )
    fact, customer = sales[0], customers[0]
    links = [
        rel for rel in catalog.get("relationships") or []
        if rel["from_table"] == fact["table"] and rel["to_table"] == customer["table"]
    ]
    if len(links) != 1:
        raise ValueError(
            "No encontré una relación inequívoca de ventas hacia clientes. "
            "Es necesario verificar las claves para no atribuir compras al cliente equivocado."
        )
    # The backend validates this FK target against its real primary key.
    from app.database.inspector import inspect_database
    schema = inspect_database()
    customer_schema = schema.tables.get(customer["table"])
    if not customer_schema or links[0]["to_column"] not in customer_schema.primary_key:
        raise ValueError(
            "La relación cliente-venta no apunta a una clave primaria verificada."
        )
    identifiers = [
        field for field in customer.get("fields") or []
        if field.get("semantic") == "name" and field.get("key") != links[0]["to_column"]
    ]
    if len(identifiers) != 1:
        raise ValueError(
            "No pude identificar un único nombre de cliente; revisa el catálogo semántico."
        )
    label = identifiers[0]
    if kind == "amount":
        measures = [
            field for field in fact.get("metrics") or []
            if field.get("semantic") in {"total", "amount"}
        ]
        if len(measures) != 1:
            raise ValueError(
                "Las ventas no tienen un único importe verificable. "
                "Especifica una métrica monetaria antes de generar el ranking."
            )
        metric = measures[0]
        aggregation, y_label = "sum", "Importe total comprado"
    else:
        metric = None
        aggregation, y_label = "count", "Número de compras"
    smaller = any(_contains(text, term) for term in (
        "menos", "menor", "menores", "bottom", "least",
    ))
    limit = _rank_limit(text)
    filters = _year_bounds(text, fact)
    measure_name = "importe" if kind == "amount" else "compras"
    definition = VisualizationDefinition(
        title=(f"{limit} clientes con {'menor' if smaller else 'mayor'} {measure_name}")[:120],
        visualization=_visual_type(text),
        table=fact["table"],
        metric=metric["key"] if metric else None,
        metric_table=fact["table"],
        aggregation=aggregation,
        group_by=label["key"],
        group_by_table=customer["table"],
        group_by_identity=links[0]["to_column"],
        sort_direction="asc" if smaller else "desc",
        filters=filters,
        limit=limit,
    )
    return definition, "Clientes", y_label


def interpret_visualization_request(question: str) -> dict:
    """Return a verified preview + editable draft, without any write action."""
    normalized = _normalize(question)
    catalog = get_semantic_visualization_catalog()
    entities = catalog.get("entities") or []
    if not entities:
        raise ValueError("No encontré entidades disponibles en la fuente activa.")
    ranking = _customer_rank_request(normalized)
    if ranking:
        definition, x_label, y_label = _customer_ranking(normalized, catalog)
    else:
        selected = _pick_entity(normalized, entities)
        chart_type = _visual_type(normalized)
        dimension, grain = _choose_dimension(normalized, selected, chart_type)
        metric, aggregation = _choose_metric(normalized, selected)
        filters = _year_bounds(normalized, selected)
        if metric and aggregation not in metric.get("aggregations", []):
            raise ValueError("La métrica solicitada no admite esa operación.")
        if chart_type == "donut" and grain != "raw":
            raise ValueError("Para series temporales usa barras o líneas; la gráfica de dona no representa bien meses.")
        period = " por mes" if grain == "month" else " por año" if grain == "year" else (
            " por " + dimension["label"].lower() if dimension else ""
        )
        measure_name = metric["label"] if metric else "Cantidad de registros"
        years = sorted(set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", normalized)))
        year_part = f" ({'-'.join(years)})" if years else ""
        definition = VisualizationDefinition(
            title=(measure_name + " de " + selected["label"] + period + year_part)[:120],
            visualization=chart_type,
            table=selected["table"],
            metric=metric["key"] if metric else None,
            metric_table=selected["table"],
            aggregation=aggregation,
            group_by=dimension["key"] if dimension else None,
            group_by_table=selected["table"],
            time_granularity=grain,
            filters=filters,
            limit=100 if grain != "raw" else 20,
        )
        x_label = dimension["label"] if dimension else "Indicador"
        if grain == "month":
            x_label = "Mes y año"
        elif grain == "year":
            x_label = "Año"
        y_label = ("Cantidad de registros" if not metric else
                   ("Promedio de " if aggregation == "avg" else "Suma de ") + metric["label"])
    result = preview_visualization(definition)
    rows = result.get("data") or []
    placement = _placement(normalized)
    status = database_manager.status()
    return {
        "definition": definition.model_dump(),
        "preview": result,
        "placement": placement,
        "axes": {"x": x_label, "y": y_label},
        "source": {"key": _source_key(), "database": status.get("database"),
                   "provider": status.get("provider"),
                   "server": status.get("server"), "host": status.get("host"),
                   "port": status.get("port")},
        "notes": [
            "Es una propuesta editable; no se guardará hasta que confirmes en el creador.",
            *([] if rows else ["No hay registros para esa combinación de filtros. Revísala antes de guardar."]),
        ],
        "status": "ready" if rows else "empty",
    }
