import re
import unicodedata

from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.inspector import inspect_database


ROLE_LABELS = {
    "sales": "Ventas", "sales_details": "Detalle de ventas", "products": "Productos",
    "inventory": "Inventario", "customers": "Clientes", "employees": "Empleados",
    "payments": "Pagos", "categories": "Categorías", "suppliers": "Proveedores",
    "students": "Estudiantes", "teachers": "Docentes", "courses": "Cursos",
    "enrollments": "Inscripciones", "grades": "Calificaciones", "attendance": "Asistencia",
    "patients": "Pacientes", "doctors": "Médicos", "appointments": "Citas",
    "diagnoses": "Diagnósticos", "treatments": "Tratamientos", "prescriptions": "Recetas",
    "admissions": "Admisiones", "vehicles": "Vehículos", "drivers": "Conductores",
    "routes": "Rutas", "trips": "Viajes", "passengers": "Pasajeros", "tickets": "Boletos",
    "rooms": "Habitaciones", "guests": "Huéspedes", "reservations": "Reservas",
    "stays": "Estadías", "menu_items": "Elementos del menú", "tables": "Mesas",
    "orders": "Órdenes", "order_details": "Detalle de órdenes", "ingredients": "Ingredientes",
    "services": "Servicios", "clients": "Clientes", "projects": "Proyectos",
    "invoices": "Facturas", "accounts": "Cuentas", "transactions": "Transacciones",
    "journal_entries": "Asientos contables", "materials": "Materiales", "machines": "Máquinas",
    "production_orders": "Órdenes de producción", "payroll": "Nómina",
    "departments": "Departamentos", "shifts": "Turnos",
}

SEMANTIC_LABELS = {
    "id": "Identificador", "name": "Nombre", "date": "Fecha", "total": "Total",
    "amount": "Monto", "status": "Estado", "quantity": "Cantidad", "price": "Precio",
    "stock": "Existencias", "minimum": "Stock mínimo", "method": "Método de pago",
    "value": "Valor", "credits": "Créditos", "specialty": "Especialidad",
    "reason": "Motivo", "dose": "Dosis", "origin": "Origen", "destination": "Destino",
    "balance": "Saldo", "type": "Tipo", "debit": "Débito", "credit": "Crédito",
}

COLUMN_LABELS = {
    "fecha": "Fecha", "nombre": "Nombre", "estado": "Estado", "status": "Estado",
    "total": "Total", "monto": "Monto", "amount": "Monto", "cantidad": "Cantidad",
    "quantity": "Cantidad", "precio": "Precio", "price": "Precio", "descuento": "Descuento",
    "discount": "Descuento", "canal": "Canal", "channel": "Canal", "ciudad": "Ciudad",
    "city": "Ciudad", "categoria": "Categoría", "category": "Categoría",
    "metodo": "Método", "method": "Método", "email": "Correo electrónico",
    "telefono": "Teléfono", "phone": "Teléfono",
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _humanize(value: str) -> str:
    normalized = _normalize(value)
    if normalized in COLUMN_LABELS:
        return COLUMN_LABELS[normalized]
    parts = [COLUMN_LABELS.get(part, part) for part in normalized.split("_") if part]
    label = " ".join(parts).replace(" id", " ID")
    return label[:1].upper() + label[1:] if label else value


def _column_kind(type_name: str) -> str:
    value = type_name.lower()
    if any(token in value for token in ("int", "numeric", "decimal", "real", "float", "double", "money")):
        return "number"
    if any(token in value for token in ("date", "time")):
        return "date"
    if any(token in value for token in ("bool", "bit")):
        return "boolean"
    return "text"


def _column_capabilities(kind: str, is_identifier: bool) -> dict:
    if is_identifier:
        return {"metric": False, "dimension": False, "filter": True, "aggregations": ["count"]}
    if kind == "number":
        return {"metric": True, "dimension": False, "filter": True, "aggregations": ["sum", "avg", "min", "max", "count"]}
    return {"metric": False, "dimension": True, "filter": True, "aggregations": ["count"]}


def get_semantic_visualization_catalog() -> dict:
    schema = inspect_database()
    semantic_response = inspect_semantic_model()
    model = semantic_response.get("semantic_model", {})
    entities = model.get("entities", {})

    table_roles: dict[str, list[tuple[str, dict]]] = {}
    for role, entity in entities.items():
        table_roles.setdefault(entity["table"], []).append((role, entity))

    catalog_entities = []
    for table_name, table in schema.tables.items():
        role_matches = sorted(
            table_roles.get(table_name, []),
            key=lambda item: item[1].get("score", 0),
            reverse=True,
        )
        role, semantic_entity = role_matches[0] if role_matches else (None, {})
        semantic_columns = {
            physical: semantic_name
            for semantic_name, physical in semantic_entity.get("columns", {}).items()
        }

        fields = []
        for column in table.columns:
            semantic_name = semantic_columns.get(column.name)
            kind = _column_kind(column.type)
            is_identifier = (
                column.name in table.primary_key
                or semantic_name == "id"
                or _normalize(column.name).endswith("_id")
            )
            capabilities = _column_capabilities(kind, is_identifier)
            fields.append({
                "key": column.name,
                "label": SEMANTIC_LABELS.get(semantic_name) if semantic_name else _humanize(column.name),
                "semantic": semantic_name,
                "kind": kind,
                "technical_type": column.type,
                "is_identifier": is_identifier,
                **capabilities,
            })

        label = ROLE_LABELS.get(role, _humanize(table_name))
        catalog_entities.append({
            "key": role or table_name,
            "label": label,
            "table": table_name,
            "semantic_role": role,
            "confidence": semantic_entity.get("confidence", "unmapped"),
            "fields": fields,
            "metrics": [field for field in fields if field["metric"]],
            "dimensions": [field for field in fields if field["dimension"]],
            "filters": [field for field in fields if field["filter"]],
        })

    relations = []
    for relation in schema.relationships:
        relations.append({
            "from_table": relation.table,
            "from_column": relation.column,
            "to_table": relation.references_table,
            "to_column": relation.references_column,
            "from_label": next((e["label"] for e in catalog_entities if e["table"] == relation.table), _humanize(relation.table)),
            "to_label": next((e["label"] for e in catalog_entities if e["table"] == relation.references_table), _humanize(relation.references_table)),
        })

    return {
        "database": schema.database,
        "domain": model.get("domain"),
        "domain_confidence": model.get("domain_confidence"),
        "entities": catalog_entities,
        "relationships": relations,
        "builder": {
            "visualizations": [
                {"key": "kpi", "label": "Indicador"},
                {"key": "bar", "label": "Barras"},
                {"key": "line", "label": "Líneas"},
                {"key": "donut", "label": "Dona"},
                {"key": "table", "label": "Tabla"},
            ],
            "aggregations": {
                "count": "Cantidad",
                "sum": "Suma",
                "avg": "Promedio",
                "min": "Mínimo",
                "max": "Máximo",
            },
        },
    }
