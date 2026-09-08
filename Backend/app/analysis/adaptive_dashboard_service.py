from sqlalchemy import text

from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.connection import get_connection


DOMAIN_KPI_ROLES = {
    "education": ["students", "teachers", "courses", "enrollments"],
    "healthcare": ["patients", "doctors", "appointments", "admissions"],
    "transportation": ["vehicles", "drivers", "routes", "trips"],
    "hospitality": ["rooms", "guests", "reservations", "stays"],
    "restaurant": ["menu_items", "tables", "orders", "ingredients"],
    "professional_services": ["clients", "services", "projects", "invoices"],
    "finance_accounting": ["accounts", "transactions", "journal_entries"],
    "manufacturing": ["products", "materials", "machines", "production_orders"],
    "human_resources": ["employees", "departments", "attendance", "payroll"],
}

DOMAIN_TREND_PRIORITY = {
    "education": ["enrollments", "attendance", "grades"],
    "healthcare": ["appointments", "admissions", "treatments"],
    "transportation": ["trips", "tickets"],
    "hospitality": ["reservations", "stays"],
    "restaurant": ["orders"],
    "professional_services": ["appointments", "projects", "invoices", "payments"],
    "finance_accounting": ["transactions", "journal_entries"],
    "manufacturing": ["production_orders"],
    "human_resources": ["attendance", "payroll"],
}

DOMAIN_STATUS_PRIORITY = {
    "education": ["enrollments", "attendance", "students"],
    "healthcare": ["appointments", "admissions", "treatments"],
    "transportation": ["trips", "vehicles", "drivers", "tickets"],
    "hospitality": ["reservations", "rooms", "stays"],
    "restaurant": ["orders", "tables"],
    "professional_services": ["projects", "appointments", "invoices"],
    "finance_accounting": ["transactions"],
    "manufacturing": ["production_orders", "machines"],
    "human_resources": ["employees", "attendance"],
}


def _quote(identifier: str) -> str:
    return "[" + identifier.replace("]", "]]" ) + "]"


def _count_table(table: str) -> int:
    sql = text(f"SELECT COUNT(*) AS total FROM {_quote(table)};")
    with get_connection() as connection:
        row = connection.execute(sql).mappings().first()
    return int(row["total"] if row else 0)


def _monthly_count(table: str, date_column: str) -> list[dict]:
    sql = text(
        f"""
        SELECT
            YEAR({_quote(date_column)}) AS year,
            MONTH({_quote(date_column)}) AS month,
            COUNT(*) AS total
        FROM {_quote(table)}
        WHERE {_quote(date_column)} IS NOT NULL
        GROUP BY YEAR({_quote(date_column)}), MONTH({_quote(date_column)})
        ORDER BY YEAR({_quote(date_column)}), MONTH({_quote(date_column)});
        """
    )

    with get_connection() as connection:
        rows = connection.execute(sql).mappings().all()

    return [
        {"year": int(row["year"]), "month": int(row["month"]), "total": int(row["total"])}
        for row in rows
        if row["year"] is not None and row["month"] is not None
    ]


def _status_distribution(table: str, status_column: str) -> list[dict]:
    sql = text(
        f"""
        SELECT TOP 12
            CAST({_quote(status_column)} AS NVARCHAR(255)) AS label,
            COUNT(*) AS total
        FROM {_quote(table)}
        WHERE {_quote(status_column)} IS NOT NULL
        GROUP BY CAST({_quote(status_column)} AS NVARCHAR(255))
        ORDER BY total DESC;
        """
    )

    with get_connection() as connection:
        rows = connection.execute(sql).mappings().all()

    return [
        {"label": str(row["label"]), "total": int(row["total"])}
        for row in rows
    ]


def _entity_counts(entities: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role, entity in entities.items():
        table = entity.get("table")
        if not table:
            continue
        try:
            counts[role] = _count_table(table)
        except Exception:
            counts[role] = 0
    return counts


def _select_kpis(domain: str | None, entities: dict, counts: dict[str, int]) -> list[dict]:
    preferred = DOMAIN_KPI_ROLES.get(domain, [])
    selected: list[str] = []

    for role in preferred:
        if role in entities and role not in selected:
            selected.append(role)

    for role in entities:
        if role not in selected:
            selected.append(role)
        if len(selected) >= 4:
            break

    return [
        {
            "role": role,
            "value": counts.get(role, 0),
            "table": entities[role].get("table"),
        }
        for role in selected[:4]
    ]


def _select_trend(domain: str | None, entities: dict) -> dict:
    candidates = DOMAIN_TREND_PRIORITY.get(domain, []) + list(entities.keys())
    seen: set[str] = set()

    for role in candidates:
        if role in seen:
            continue
        seen.add(role)
        entity = entities.get(role)
        if not entity:
            continue
        table = entity.get("table")
        date_column = (entity.get("columns") or {}).get("date")
        if not table or not date_column:
            continue
        try:
            return {
                "available": True,
                "role": role,
                "data": _monthly_count(table, date_column),
            }
        except Exception:
            continue

    return {"available": False, "role": None, "data": []}


def _select_status(domain: str | None, entities: dict) -> dict:
    candidates = DOMAIN_STATUS_PRIORITY.get(domain, []) + list(entities.keys())
    seen: set[str] = set()

    for role in candidates:
        if role in seen:
            continue
        seen.add(role)
        entity = entities.get(role)
        if not entity:
            continue
        table = entity.get("table")
        status_column = (entity.get("columns") or {}).get("status")
        if not table or not status_column:
            continue
        try:
            return {
                "available": True,
                "role": role,
                "data": _status_distribution(table, status_column),
            }
        except Exception:
            continue

    return {"available": False, "role": None, "data": []}


def get_adaptive_dashboard_summary() -> dict:
    analysis = inspect_semantic_model()
    semantic = analysis.get("semantic_model") or {}
    domain = semantic.get("domain")
    entities = semantic.get("entities") or {}

    counts = _entity_counts(entities)

    return {
        "database": analysis.get("database"),
        "domain": domain,
        "domain_confidence": semantic.get("domain_confidence"),
        "ambiguous_domain": semantic.get("ambiguous_domain", False),
        "kpis": _select_kpis(domain, entities, counts),
        "trend": _select_trend(domain, entities),
        "status_distribution": _select_status(domain, entities),
        "entity_counts": [
            {
                "role": role,
                "value": counts.get(role, 0),
                "table": entity.get("table"),
                "confidence": entity.get("confidence"),
            }
            for role, entity in entities.items()
        ],
        "relations_detected": len(semantic.get("relations") or []),
        "unmapped_tables": semantic.get("unmapped_tables") or [],
    }
