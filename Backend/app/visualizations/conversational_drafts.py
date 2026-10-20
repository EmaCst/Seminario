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
    "doctors": ("doctor", "doctores", "medico", "medicos", "physicians"),
    "teachers": ("docente", "docentes", "profesor", "profesores", "teachers"),
    "courses": ("curso", "cursos", "materia", "materias", "courses"),
    "routes": ("ruta", "rutas", "routes"),
    "vehicles": ("vehiculo", "vehiculos", "vehicles"),
    "drivers": ("conductor", "conductores", "drivers"),
    "rooms": ("habitacion", "habitaciones", "rooms"),
    "guests": ("huesped", "huespedes", "guests"),
    "categories": ("categoria", "categorias", "categories"),
    "departments": ("departamento", "departamentos", "departments"),
    "accounts": ("cuenta", "cuentas", "accounts"),
    "materials": ("material", "materiales", "materials"),
    "suppliers": ("proveedor", "proveedores", "suppliers"),
    "services": ("servicio", "servicios", "services"),
    "clients": ("cliente", "clientes", "clients"),
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


def _related_dimension(text: str, root: dict, catalog: dict) -> tuple[dict, dict] | None:
    """Resolve 'by doctor/course/customer' through many-to-one relations only."""
    matches = re.findall(r"\b(?:por|segun|by)\s+([a-z_]+)", text)
    if not matches:
        return None
    requested = matches[-1]
    entities = catalog.get("entities") or []
    by_table = {entity["table"]: entity for entity in entities}
    reachable = {root["table"]}
    for _ in range(4):
        changed = False
        for link in catalog.get("relationships") or []:
            if link["from_table"] in reachable and link["to_table"] not in reachable:
                parent = by_table.get(link["to_table"])
                if parent and link["to_column"] in (parent.get("primary_key") or []):
                    reachable.add(link["to_table"])
                    changed = True
        if not changed:
            break

    candidates = []
    for table in reachable - {root["table"]}:
        entity = by_table[table]
        role = entity.get("semantic_role") or ""
        names = [
            role.replace("_", " "), entity.get("label", ""),
            entity.get("table", ""), *ROLE_ALIASES.get(role, ()),
        ]
        matched_role = any(_contains(requested, name) for name in names if name)
        fields = entity.get("dimensions") or []
        matching_fields = [
            field for field in fields
            if any(_contains(requested, name) for name in (
                field.get("key") or "", field.get("label") or "",
                field.get("semantic") or "",
            ))
        ]
        if matched_role:
            named = [field for field in fields if field.get("semantic") == "name"]
            if len(named) != 1:
                named = [
                    field for field in fields
                    if _normalize(field.get("key", "")) in (
                        "nombre", "name", "title", "codigo", "code",
                    )
                ]
            if len(named) == 1:
                candidates.append((named[0], entity))
        elif len(matching_fields) == 1:
            candidates.append((matching_fields[0], entity))
    if len(candidates) > 1:
        raise ValueError(
            f"La dimensión «{requested}» existe en varias entidades relacionadas. "
            "Especifica cuál deseas usar en el creador."
        )
    return candidates[0] if candidates else None


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


def _inventory_critical_request(text: str) -> bool:
    """A business condition can mention inventory AND products intentionally."""
    has_stock = any(_contains(text, term) for term in (
        "inventario", "inventory", "stock", "existencias",
        "producto", "productos", "products",
    ))
    has_critical = any(_contains(text, term) for term in (
        "critico", "criticos", "critica", "criticas", "critical",
        "bajo stock", "stock bajo", "stock minimo", "minimo de inventario",
        "existencias bajas", "punto de reposicion", "por agotarse",
        "debajo del minimo", "por debajo del minimo",
    ))
    return has_stock and has_critical


def _inventory_field(entity: dict, semantic: str, names: tuple[str, ...]) -> dict | None:
    """Match exactly one verified numeric field; never guess a similarly named column."""
    numbers = [
        field for field in entity.get("fields") or []
        if field.get("kind") == "number" and not field.get("is_identifier")
    ]
    semantic_matches = [field for field in numbers if field.get("semantic") == semantic]
    if len(semantic_matches) > 1:
        raise ValueError(
            f"Hay varias columnas relacionadas con {semantic} en «{entity['label']}». "
            "Revisa cuál debe utilizarse en el creador."
        )
    if semantic_matches:
        return semantic_matches[0]
    aliases = {_normalize(word) for word in names}
    matches = [field for field in numbers if _normalize(field["key"]) in aliases]
    if len(matches) > 1:
        raise ValueError(
            f"Hay varias columnas candidatas para {semantic} en «{entity['label']}». "
            "Especifica la métrica o revisa el esquema."
        )
    return matches[0] if matches else None


def _inventory_label(entity: dict) -> dict | None:
    """A human-readable dimension must be present in the active source catalog."""
    possibilities = [
        field for field in entity.get("dimensions") or []
        if (field.get("semantic") == "name"
            or _normalize(field.get("key", "")) in (
                "nombre", "name", "nombre_producto", "producto_nombre",
                "product_name", "sku", "codigo_producto", "product_code",
            ))
    ]
    if len(possibilities) == 1:
        return possibilities[0]
    if not possibilities:
        return None
    preferred = [field for field in possibilities if field.get("semantic") == "name"]
    return preferred[0] if len(preferred) == 1 else None


def _explicit_critical_threshold(text: str) -> int | None:
    """Only a number attached to an explicit stock threshold is accepted."""
    expression = re.search(
        r"\b(?:umbral(?: de)?|limite(?: de)?|minimo(?: de)?|"
        r"menos de|debajo de|por debajo de|menor(?:es)? a|hasta)"
        r"\s+(\d{1,6})\s*(?:unidades|productos|existencias)?\b",
        text,
    )
    if not expression:
        expression = re.search(r"\b(\d{1,6})\s+unidades\b", text)
    if not expression:
        return None
    return int(expression.group(1))


def _inventory_critical(text: str, catalog: dict) -> tuple[VisualizationDefinition, str, str, list[str]]:
    entities = catalog.get("entities") or []
    threshold = _explicit_critical_threshold(text)
    candidates = []
    for entity in entities:
        if entity.get("semantic_role") not in {"inventory", "products"}:
            continue
        stock = _inventory_field(
            entity, "stock", (
                "stock", "stock_actual", "existencias", "existencia",
                "cantidad_disponible", "unidades_disponibles", "stock_disponible",
            ),
        )
        minimum = _inventory_field(
            entity, "minimum", (
                "stock_minimo", "min_stock", "minimum_stock", "minimo",
                "minimum", "cantidad_minima", "existencias_minimas",
                "punto_reorden", "punto_reposicion",
            ),
        )
        minimum_table = entity["table"]
        if stock and minimum is None and threshold is None and entity.get("semantic_role") == "inventory":
            # Some schemas store current units in Inventory and the minimum
            # policy in Products. Verify a single forward inventory->product
            # relation instead of inventing a cross-table association.
            possible = []
            for product in entities:
                if product.get("semantic_role") != "products":
                    continue
                links = [
                    rel for rel in catalog.get("relationships") or []
                    if rel["from_table"] == entity["table"]
                    and rel["to_table"] == product["table"]
                ]
                parent_min = _inventory_field(
                    product, "minimum", (
                        "stock_minimo", "min_stock", "minimum_stock", "minimo",
                        "minimum", "cantidad_minima", "existencias_minimas",
                        "punto_reorden", "punto_reposicion",
                    ),
                )
                if len(links) == 1 and parent_min:
                    possible.append((product, parent_min))
            if len(possible) > 1:
                raise ValueError(
                    "Hay varias tablas relacionadas con un mínimo de producto. "
                    "Especifica cuál define el umbral de inventario."
                )
            if possible:
                minimum_table = possible[0][0]["table"]
                minimum = possible[0][1]
        if stock and (threshold is not None or (minimum and stock["key"] != minimum["key"])):
            candidates.append((entity, stock, minimum, minimum_table))

    if not candidates:
        raise ValueError(
            "No encontré un par verificable de columnas numéricas de existencias "
            "y mínimo permitido en Inventario o Productos. Para identificar "
            "inventario crítico necesito ambas, o un umbral fijo "
            "como «mínimo de 5 unidades»."
        )
    if len(candidates) > 1:
        # An inventory movement/stock table is more authoritative than
        # product catalog metadata for an explicitly stated stock condition.
        inventory = [row for row in candidates if row[0].get("semantic_role") == "inventory"]
        if len(inventory) != 1:
            raise ValueError(
                "Hay varias fuentes de existencias con mínimo propio. "
                "Indica cuál es la tabla autoritativa del inventario."
            )
        selected, stock, minimum, minimum_table = inventory[0]
    else:
        selected, stock, minimum, minimum_table = candidates[0]

    group_entity = selected
    name = _inventory_label(selected)
    # If the inventory table only stores a product FK, obtain the human
    # label through a single verified many-to-one inventory->product link.
    if name is None and selected.get("semantic_role") == "inventory":
        product_entities = [e for e in entities if e.get("semantic_role") == "products"]
        links = [
            (product, rel)
            for product in product_entities
            for rel in catalog.get("relationships") or []
            if rel["from_table"] == selected["table"]
            and rel["to_table"] == product["table"]
        ]
        if len(links) == 1:
            product, relation = links[0]
            from app.database.inspector import inspect_database
            schema = inspect_database()
            parent = schema.tables.get(product["table"])
            if not parent or relation["to_column"] not in parent.primary_key:
                raise ValueError(
                    "La relación entre Inventario y Productos no apunta a una "
                    "clave primaria validada."
                )
            name = _inventory_label(product)
            if name:
                group_entity = product
                # Product-wide stock is only meaningful if there is exactly
                # one inventory row for each product. Multiple warehouse
                # entries require an explicit separate aggregation rule.
                from app.database.query_executor import execute_query
                from app.visualizations.visualization_service import _quote
                col = _quote(relation["from_column"])
                table = _quote(selected["table"])
                provider = database_manager.status().get("provider")
                limit = "TOP 1 " if provider == "sqlserver" else ""
                suffix = "" if provider == "sqlserver" else " LIMIT 1"
                duplicates = execute_query(
                    f"SELECT {limit}{col} AS product_id FROM {table} "
                    f"WHERE {col} IS NOT NULL GROUP BY {col} "
                    f"HAVING COUNT(*) > 1{suffix}"
                )
                if duplicates:
                    raise ValueError(
                        "Hay varios registros de inventario para un mismo "
                        "producto (por ejemplo, distintas bodegas). No puedo "
                        "calificar el stock total como crítico comparando cada "
                        "registro por separado. Define primero el alcance "
                        "por bodega o el mínimo global."
                    )
    if name is None:
        raise ValueError(
            "Encontré existencias y mínimo, pero no un nombre de producto "
            "verificable ni una relación única hacia Productos. "
            "Revisa las columnas y claves en el constructor."
        )
    from app.database.inspector import inspect_database
    schema = inspect_database()
    named = schema.tables.get(group_entity["table"])
    primary = named.primary_key if named else []
    identity = primary[0] if len(primary) == 1 else None

    # Critical means CURRENT STOCK <= MINIMUM for a single stock record.
    # Comparing the two columns is performed by the trusted SQL query
    # builder, which checks both identifiers against its live schema.
    definition = VisualizationDefinition(
        title="Productos con inventario crítico",
        visualization=_visual_type(text),
        table=selected["table"],
        metric=stock["key"],
        metric_table=selected["table"],
        aggregation="sum",
        group_by=name["key"],
        group_by_table=group_entity["table"],
        group_by_identity=identity,
        filters=[
            VisualizationFilter(
                table=selected["table"], column=stock["key"],
                operator="lte" if threshold is not None else "lte_field",
                value=threshold if threshold is not None else minimum["key"],
                value_table=minimum_table if threshold is None else None,
            ),
        ],
        sort_direction="asc",
        limit=100,
    )
    criterion = (
        f"Umbral indicado en la solicitud: {stock['label']} "
        f"menor o igual a {threshold} unidades."
        if threshold is not None else
        f"Criterio verificado: {stock['label']} menor o igual a "
        f"{minimum['label']} en la tabla {minimum_table}."
    )
    return definition, "Producto", "Existencias disponibles", [
        criterion,
        "Se muestran como máximo 100 resultados; el límite puede modificarse en el creador.",
        "Una cifra pequeña, por sí sola, no determina inventario crítico.",
    ]


def interpret_visualization_request(question: str) -> dict:
    """Return a verified preview + editable draft, without any write action."""
    normalized = _normalize(question)
    catalog = get_semantic_visualization_catalog()
    entities = catalog.get("entities") or []
    if not entities:
        raise ValueError("No encontré entidades disponibles en la fuente activa.")
    ranking = _customer_rank_request(normalized)
    extra_notes = []
    if _inventory_critical_request(normalized):
        definition, x_label, y_label, extra_notes = _inventory_critical(normalized, catalog)
    elif ranking:
        definition, x_label, y_label = _customer_ranking(normalized, catalog)
    else:
        selected = _pick_entity(normalized, entities)
        chart_type = _visual_type(normalized)
        dimension_entity = selected
        try:
            dimension, grain = _choose_dimension(normalized, selected, chart_type)
        except ValueError as exc:
            related = _related_dimension(normalized, selected, catalog)
            if related is None:
                raise exc
            dimension, dimension_entity = related
            grain = "raw"
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
            group_by_table=dimension_entity["table"],
            group_by_identity=(
                dimension_entity["primary_key"][0]
                if dimension and dimension_entity["table"] != selected["table"]
                and dimension.get("semantic") == "name"
                and len(dimension_entity.get("primary_key") or []) == 1
                else None
            ),
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
            *extra_notes,
            *([] if rows else ["No hay registros para esa combinación de filtros. Revísala antes de guardar."]),
        ],
        "status": "ready" if rows else "empty",
    }
