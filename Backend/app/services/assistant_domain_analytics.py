"""Schema-grounded, domain-aware analytics for Kenneth's ten business domains.

This module deliberately supports only metrics that can be verified in a single
mapped entity. More complex joins remain for the general SQL planner.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import text

from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.connection import get_connection
from app.services.assistant_analytics import _month_expr, _year_expr, _number, _period_year
from app.analysis.adaptive_dashboard_service import _provider, _quote
from app.services.assistant_router import MONTH_LABELS, months_in, normalize

# Business words must be scoped by detected domain; "citas" can belong to
# healthcare or professional services, and "productos" to retail or industry.
ROLE_WORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "retail": {
        "sales": ("venta", "ventas", "factura", "facturas"),
        "products": ("producto", "productos"),
        "customers": ("cliente", "clientes"),
        "inventory": ("inventario", "existencias"),
        "payments": ("pago", "pagos"),
    },
    "education": {
        "students": ("estudiante", "estudiantes", "alumno", "alumnos"),
        "teachers": ("profesor", "profesores", "docente", "docentes"),
        "courses": ("curso", "cursos", "materia", "materias", "asignatura", "asignaturas"),
        "enrollments": ("inscripcion", "inscripciones", "matricula", "matriculas"),
        "grades": ("nota", "notas", "calificacion", "calificaciones"),
        "attendance": ("asistencia", "asistencias"),
    },
    "healthcare": {
        "patients": ("paciente", "pacientes"),
        "doctors": ("doctor", "doctores", "medico", "medicos"),
        "appointments": ("cita", "citas", "consulta", "consultas"),
        "diagnoses": ("diagnostico", "diagnosticos"),
        "treatments": ("tratamiento", "tratamientos"),
        "prescriptions": ("receta", "recetas"),
        "admissions": ("admision", "admisiones", "hospitalizacion", "hospitalizaciones"),
    },
    "transportation": {
        "vehicles": ("vehiculo", "vehiculos", "flota"),
        "drivers": ("conductor", "conductores", "chofer", "choferes"),
        "routes": ("ruta", "rutas"),
        "trips": ("viaje", "viajes", "trayecto", "trayectos"),
        "passengers": ("pasajero", "pasajeros"),
        "tickets": ("boleto", "boletos", "pasaje", "pasajes"),
    },
    "hospitality": {
        "rooms": ("habitacion", "habitaciones"),
        "guests": ("huesped", "huespedes"),
        "reservations": ("reserva", "reservas"),
        "stays": ("estadia", "estadias", "estancia", "estancias"),
    },
    "restaurant": {
        "menu_items": ("plato", "platos", "menu"),
        "tables": ("mesa", "mesas"),
        "orders": ("pedido", "pedidos", "orden", "ordenes"),
        "order_details": ("detalle", "detalles"),
        "ingredients": ("ingrediente", "ingredientes"),
    },
    "professional_services": {
        "clients": ("cliente", "clientes"),
        "services": ("servicio", "servicios"),
        "appointments": ("cita", "citas"),
        "projects": ("proyecto", "proyectos"),
        "invoices": ("factura", "facturas"),
        "payments": ("pago", "pagos", "cobro", "cobros"),
    },
    "finance_accounting": {
        "accounts": ("cuenta", "cuentas"),
        "transactions": ("transaccion", "transacciones", "movimiento", "movimientos"),
        "journal_entries": ("asiento", "asientos", "apunte", "apuntes"),
    },
    "manufacturing": {
        "products": ("producto", "productos"),
        "materials": ("material", "materiales", "materia prima"),
        "machines": ("maquina", "maquinas"),
        "production_orders": ("orden de produccion", "ordenes de produccion", "produccion"),
        "inventory": ("inventario", "existencias"),
        "suppliers": ("proveedor", "proveedores"),
    },
    "human_resources": {
        "employees": ("empleado", "empleados", "trabajador", "trabajadores"),
        "payroll": ("nomina", "nominas"),
        "departments": ("departamento", "departamentos"),
        "attendance": ("asistencia", "asistencias"),
        "shifts": ("turno", "turnos"),
    },
}

# Human-friendly labels are for display only; SQL always uses schema-mapped names.
ROLE_LABELS = {
    "sales": "ventas", "products": "productos", "customers": "clientes",
    "inventory": "registros de inventario", "payments": "pagos",
    "students": "estudiantes", "teachers": "docentes", "courses": "cursos",
    "enrollments": "inscripciones", "grades": "calificaciones",
    "attendance": "registros de asistencia", "patients": "pacientes",
    "doctors": "médicos", "appointments": "citas",
    "diagnoses": "diagnósticos", "treatments": "tratamientos",
    "prescriptions": "recetas", "admissions": "admisiones",
    "vehicles": "vehículos", "drivers": "conductores", "routes": "rutas",
    "trips": "viajes", "passengers": "pasajeros", "tickets": "boletos",
    "rooms": "habitaciones", "guests": "huéspedes",
    "reservations": "reservas", "stays": "estadías",
    "menu_items": "platos", "tables": "mesas", "orders": "pedidos",
    "order_details": "líneas de pedido", "ingredients": "ingredientes",
    "clients": "clientes", "services": "servicios", "projects": "proyectos",
    "invoices": "facturas", "accounts": "cuentas",
    "transactions": "transacciones", "journal_entries": "asientos contables",
    "materials": "materiales", "machines": "máquinas",
    "production_orders": "órdenes de producción", "suppliers": "proveedores",
    "employees": "empleados", "payroll": "registros de nómina",
    "departments": "departamentos", "shifts": "turnos",
}

# This is a restricted allowlist of additive, recorded financial measures.
# In particular: current stock, account balances, grades and list prices MUST
# NOT be treated as sums of sales/income.
MONETARY_ROLES = {
    ("retail", "sales"): ("total",),
    ("retail", "payments"): ("amount",),
    ("restaurant", "orders"): ("total",),
    ("hospitality", "reservations"): ("total",),
    ("professional_services", "invoices"): ("total",),
    ("professional_services", "payments"): ("amount",),
    ("finance_accounting", "transactions"): ("amount",),
    ("human_resources", "payroll"): ("amount",),
    ("transportation", "tickets"): ("amount",),
}


@dataclass(frozen=True)
class DomainQuery:
    domain: str
    role: str
    operation: str
    months: tuple[int, ...] = ()
    year: int | None = None
    metric: str = "count"


def _previous_questions(history: list[dict] | None) -> list[str]:
    messages = []
    for item in (history or [])[-12:]:
        if (item.get("role") or item.get("from")) in ("user", "usuario"):
            value = str(item.get("content") or item.get("text") or "").strip()
            if value:
                messages.append(value)
    return messages


def _matched_role(text: str, domain: str) -> str | None:
    padded = f" {text} "
    found = [
        (len(term.split()), len(term), role)
        for role, aliases in ROLE_WORDS.get(domain, {}).items()
        for term in aliases if f" {term} " in padded
    ]
    if not found:
        return None
    # A request mentioning patients AND appointments, for example, usually
    # contains a relationship predicate. Never choose the longest word and
    # silently count the wrong entity.
    if len({entry[2] for entry in found}) > 1:
        return None
    return found[0][2]


def classify_domain_question(
    question: str, history: list[dict] | None, semantic: dict,
) -> DomainQuery | None:
    """Return only operations clearly supported by the recognized role.

    A mapper ambiguity or missing table is not silently resolved by picking a
    guessed table. Explicitly multi-entity questions stay with SQL planning.
    """
    domain = semantic.get("domain")
    if domain not in ROLE_WORDS:
        return None
    text = normalize(question)
    role = _matched_role(text, domain)
    ellipsis = text.startswith(("y ", "ese ", "esa ", "del mismo ", "en ese "))
    previous = _previous_questions(history)
    if role is None and ellipsis:
        for message in reversed(previous[-5:]):
            context = normalize(message)
            if context in {"hola", "buenas", "gracias"}:
                break
            role = _matched_role(context, domain)
            if role:
                break
    if role is None:
        return None
    entity = (semantic.get("entities") or {}).get(role)
    if not entity or not entity.get("table") or entity.get("ambiguous"):
        return None
    months = months_in(question)
    if not months and ellipsis and any(term in text for term in ("diferencia", "compar", "dos meses", "ambos")):
        for message in reversed(previous[-5:]):
            seen = months_in(message)
            if seen:
                months = seen
                if len(months) > 1:
                    break
    if len(months) > 2:
        return None
    # A single-table shortcut may only handle a whole month, not a day or a
    # different time window. Let the general SQL planner handle specific dates.
    if (re.search(r"\\b(?:[1-9]|[12][0-9]|3[01])\\s+de\\s+(?:" +
                  "|".join(MONTH_LABELS.values()) + r")\\b", text)
            or any(term in text for term in ("hoy", "ayer", "manana", "esta semana",
                                               "semana pasada", "este ano", "ano pasado",
                                               "trimestre", "semestre", "ultimos"))):
        return None
    match = re.search(r"\b(20\d{2})\b", text)
    year = int(match.group(1)) if match else None
    if year is None and ellipsis:
        for message in reversed(previous[-5:]):
            year_match = re.search(r"\b(20\d{2})\b", normalize(message))
            if year_match:
                year = int(year_match.group(1))
                break

    count_terms = ("cuantos", "cuantas", "cantidad", "numero", "total de", "cuanto", "cuanta")
    amount_terms = ("monto", "importe", "dinero", "facturacion", "ingresos",
                    "recaudacion", "gasto", "pagamos", "pagado", "pagos de", "valor total")
    compare_terms = ("diferencia", "comparar", "comparacion", "frente a", "versus", "variacion", " vs ")
    status_terms = ("por estado", "por estatus", "distribucion por estado", "segun estado")
    rank_terms = ("top ", "mayor", "mas alta", "mas alto", "mejor", "ranking")
    status_values = ("programada", "programado", "programadas", "programados",
                     "pagada", "pagado", "pagadas", "pagados",
                     "cancelado", "cancelada", "cancelados", "canceladas",
                     "confirmado", "confirmada", "confirmados", "confirmadas",
                     "pendiente", "pendientes", "aprobado", "aprobada",
                     "activo", "activa", "activos", "activas",
                     "completado", "completada", "completados", "completadas",
                     "reprobado", "reprobada", "ausentes", "presentes")
    if any(f" {word} " in f" {text} " for word in status_values):
        return None  # Status predicates need an explicit verified value mapping.
    if year is not None and not months:
        return None  # An annual filter is not the same as lifetime totals.
    if any(f" {term} " in f" {text} " for term in ("con", "sin", "excepto", "solo",
                                                    "unicamente", "por", "segun")) and not any(
            term in text for term in status_terms):
        return None  # Qualifiers might require grouping/filtering by another column.
    if any(term in text for term in ("del doctor", "del medico", "del paciente",
                                    "del cliente", "por cliente", "del alumno",
                                    "del estudiante", "de una sucursal", "por sucursal")):
        return None

    if any(term in text for term in rank_terms):
        return None  # Ranking involving joins/semantics should never degrade to COUNT.
    if any(term in text for term in ("promedio", "media", "porcentaje", "tasa", "ocupacion",
                                     "ingresos por", "por alumno", "por cliente", "por curso",
                                     "por doctor", "por medico", "por empleado")):
        return None
    if any(term in text for term in status_terms):
        return DomainQuery(domain, role, "status", tuple(months), year)

    amount = any(term in text for term in amount_terms)
    metric = "amount" if amount else "count"
    if ellipsis and not amount and previous:
        # "¿y en febrero?" keeps the previous monetary-vs-counting metric.
        for prior in reversed(previous[-5:]):
            ptext = normalize(prior)
            if _matched_role(ptext, domain) == role:
                if any(term in ptext for term in amount_terms):
                    metric = "amount"
                break
    if metric == "amount" and (domain, role) not in MONETARY_ROLES:
        return None
    comparing = any(term in text for term in compare_terms)
    if comparing and len(months) == 2:
        return DomainQuery(domain, role, "compare", tuple(months), year, metric)
    if comparing:
        return None
    if len(months) == 1:
        return DomainQuery(domain, role, "month", tuple(months), year, metric)
    # No month: count entities, or sum an explicitly requested recorded measure.
    if any(term in text for term in count_terms) or (amount and metric == "amount"):
        return DomainQuery(domain, role, "total", (), year, metric)
    return None


def _query(sql: str, params: dict | None = None) -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute(text(sql), params or {}).mappings().all()]


def _measure(domain: str, role: str, entity: dict, metric: str) -> str | None:
    if metric == "count":
        return "COUNT(*)"
    keys = MONETARY_ROLES.get((domain, role), ())
    columns = entity.get("columns") or {}
    name = next((columns[key] for key in keys if columns.get(key)), None)
    return f"SUM(t.{_quote(name)})" if name else None


def _query_series(entity: dict, expression: str) -> list[dict]:
    date = (entity.get("columns") or {}).get("date")
    if not date:
        return []
    qdate = f"t.{_quote(date)}"
    y, m = _year_expr(qdate), _month_expr(qdate)
    sql = (f"SELECT {y} AS year, {m} AS month, {expression} AS total "
           f"FROM {_quote(entity['table'])} t WHERE {qdate} IS NOT NULL "
           f"GROUP BY {y}, {m} ORDER BY {y}, {m}")
    rows = _query(sql)
    return [{"year": int(item["year"]), "month": int(item["month"]), "total": float(item["total"])}
            for item in rows if item["year"] is not None and item["month"] is not None
            and item["total"] is not None]


def execute_domain_question(query: DomainQuery, semantic: dict) -> dict:
    """A restricted single-entity query, not a general business inference."""
    entity = (semantic.get("entities") or {}).get(query.role) or {}
    if not entity.get("table") or entity.get("ambiguous"):
        return {"mode": "analytics", "sql": None, "data": [],
                "answer": "No pude identificar una entidad única y confiable para esa consulta."}
    label = ROLE_LABELS.get(query.role, query.role)
    measure = _measure(query.domain, query.role, entity, query.metric)
    if measure is None:
        return {"mode": "analytics", "sql": None, "data": [],
                "answer": f"No encontré un importe monetario verificable para {label}; no lo sustituiré por un conteo."}
    if query.operation == "total":
        value = _query(f"SELECT {measure} AS total FROM {_quote(entity['table'])} t")
        total = value[0]["total"] if value else None
        if total is None:
            answer = f"No hay valores disponibles para calcular el importe de {label}."
        else:
            unit = "registros" if query.metric == "count" else "de importe registrado"
            answer = f"El total de {label} es {_number(total, money=query.metric == 'amount')} {unit}."
        return {"mode": "analytics", "sql": None, "data": value, "answer": answer}
    if query.operation == "status":
        status_column = (entity.get("columns") or {}).get("status")
        if not status_column:
            return {"mode": "analytics", "sql": None, "data": [],
                    "answer": f"No hay una columna de estado identificada para {label}."}
        if query.months and not (entity.get("columns") or {}).get("date"):
            return {"mode": "analytics", "sql": None, "data": [],
                    "answer": f"No hay una columna de fecha identificada para filtrar {label} por mes."}
        status = f"t.{_quote(status_column)}"
        conditions = [f"{status} IS NOT NULL"]
        params = {}
        if query.months:
            if len(query.months) != 1:
                return {"mode": "analytics", "sql": None, "data": [],
                        "answer": "Para distribuir estados, indica un solo mes por consulta."}
            year = query.year
            if year is None:
                series = _query_series(entity, "COUNT(*)")
                year = _period_year(series, query.months, None)
            if year is None:
                return {"mode": "analytics", "sql": None, "data": [],
                        "answer": "No encontré registros del mes solicitado para distribuir estados."}
            date = f"t.{_quote((entity.get('columns') or {})['date'])}"
            conditions.extend([f"{_month_expr(date)} = :month", f"{_year_expr(date)} = :year"])
            params = {"month": query.months[0], "year": year}
        rendered = f"CAST({status} AS {'NVARCHAR(255)' if _provider() == 'sqlserver' else 'VARCHAR(255)'})"
        sql = (f"SELECT {rendered} AS label, COUNT(*) AS total FROM {_quote(entity['table'])} t "
               f"WHERE {' AND '.join(conditions)} GROUP BY {rendered} ORDER BY total DESC")
        rows = _query(sql, params)
        summary = "; ".join(f"{item['label']}: {item['total']}" for item in rows[:12])
        scope = (f" en {MONTH_LABELS[query.months[0]]} de {params['year']}"
                 if query.months else "")
        answer = f"Distribución por estado de {label}{scope}: {summary}." if rows else f"No encontré estados registrados para {label}{scope}."
        return {"mode": "analytics", "sql": None, "data": rows[:12], "answer": answer}
    date_column = (entity.get("columns") or {}).get("date")
    if not date_column:
        return {"mode": "analytics", "sql": None, "data": [],
                "answer": f"No encontré una fecha verificable para analizar {label} por mes."}
    rows = _query_series(entity, measure)
    year = _period_year(rows, query.months, query.year)
    if year is None:
        return {"mode": "analytics", "sql": None, "data": [],
                "answer": f"No hay registros suficientes de {label} para el periodo solicitado."}
    totals = {(item["year"], item["month"]): item["total"] for item in rows}
    selected = [{"year": year, "month": m, "total": totals[(year, m)]}
                for m in query.months if (year, m) in totals]
    if len(selected) != len(query.months):
        return {"mode": "analytics", "sql": None, "data": selected,
                "answer": f"No encontré registros de {label} en todos los meses solicitados de {year}; no asumiré valores cero."}
    unit = "registros" if query.metric == "count" else "de importe registrado"
    if query.operation == "month":
        m = query.months[0]
        answer = (f"En {MONTH_LABELS[m]} de {year} hubo "
                  f"{_number(selected[0]['total'], money=query.metric == 'amount')} {unit} de {label}.")
    else:
        a, bb = query.months
        va, vb = selected[0]["total"], selected[1]["total"]
        pct = ((va - vb) / vb * 100) if vb else None
        answer = (f"En {MONTH_LABELS[a]} de {year} hubo {_number(va, money=query.metric == 'amount')} {unit} de {label}; "
                  f"en {MONTH_LABELS[bb]} hubo {_number(vb, money=query.metric == 'amount')}. "
                  f"La diferencia absoluta fue {_number(abs(va - vb), money=query.metric == 'amount')} {unit}.")
        if pct is not None:
            answer += f" Variación respecto a {MONTH_LABELS[bb]}: {pct:+.2f}%."
    return {"mode": "analytics", "sql": None, "data": selected, "answer": answer}


def run_domain_analytics(question: str, history: list[dict] | None = None) -> tuple[dict | None, str | None]:
    """Returns a response and the detected domain. Caller decides retail routing."""
    analysis = inspect_semantic_model()
    semantic = analysis.get("semantic_model") or {}
    domain = semantic.get("domain")
    if not domain or semantic.get("ambiguous_domain"):
        return None, None
    request = classify_domain_question(question, history, semantic)
    if request is None:
        return None, domain
    return execute_domain_question(request, semantic), domain
