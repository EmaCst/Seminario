import re
import unicodedata
from dataclasses import dataclass, field

from app.analysis.business_domain_detector import detect_business_domains
from app.database.inspector import inspect_database
from app.database.schema import DatabaseSchema, TableSchema


@dataclass(frozen=True)
class RoleProfile:
    table_terms: frozenset[str]
    column_terms: frozenset[str] = field(default_factory=frozenset)
    required_column_groups: tuple[frozenset[str], ...] = ()
    preferred_columns: dict[str, tuple[str, ...]] = field(default_factory=dict)


COMMON_ID = ("id", "codigo", "code", "uuid", "key")
COMMON_NAME = ("nombre", "name", "descripcion", "description", "titulo", "title")
COMMON_DATE = ("fecha", "date", "created_at", "created", "timestamp")
COMMON_STATUS = ("estado", "status", "activo", "active")
COMMON_TOTAL = ("total", "monto_total", "amount", "monto", "importe", "balance")
COMMON_QUANTITY = ("cantidad", "quantity", "qty", "stock", "existencia")


ROLE_PROFILES: dict[str, dict[str, RoleProfile]] = {
    "retail": {
        "sales": RoleProfile(
            frozenset({"venta", "ventas", "sale", "sales", "order", "orders", "pedido", "pedidos", "factura", "facturas", "invoice", "invoices"}),
            frozenset({"total", "subtotal", "fecha", "date", "cliente", "customer", "payment", "pago"}),
            (frozenset({"total", "amount", "monto", "subtotal"}),),
            {"id": COMMON_ID, "date": COMMON_DATE, "total": COMMON_TOTAL, "status": COMMON_STATUS},
        ),
        "sales_details": RoleProfile(
            frozenset({"detalle_ventas", "detalleventa", "sales_detail", "sale_detail", "order_detail", "order_details", "invoice_detail", "invoice_details", "line_items", "lines"}),
            frozenset({"cantidad", "quantity", "producto", "product", "precio", "price", "subtotal"}),
            (frozenset({"cantidad", "quantity", "qty"}),),
            {"id": COMMON_ID, "quantity": COMMON_QUANTITY, "total": ("total", "subtotal", "importe", "amount"), "price": ("precio_unitario", "unit_price", "precio", "price")},
        ),
        "products": RoleProfile(
            frozenset({"producto", "productos", "product", "products", "item", "items", "articulo", "articulos", "catalogo", "catalog", "sku"}),
            frozenset({"nombre", "name", "precio", "price", "sku", "categoria", "category", "marca", "brand"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME, "price": ("precio_venta", "sale_price", "selling_price", "precio", "price"), "status": COMMON_STATUS},
        ),
        "inventory": RoleProfile(
            frozenset({"inventario", "inventory", "stock", "existencias", "existencia", "warehouse_stock"}),
            frozenset({"stock", "cantidad", "quantity", "minimum", "minimo", "producto", "product"}),
            (frozenset({"stock", "cantidad", "quantity", "existencia"}),),
            {"id": COMMON_ID, "stock": COMMON_QUANTITY, "minimum": ("stock_minimo", "min_stock", "minimum_stock", "minimo", "minimum")},
        ),
        "customers": RoleProfile(
            frozenset({"cliente", "clientes", "customer", "customers", "client", "clients", "buyer", "buyers"}),
            frozenset({"nombre", "name", "email", "correo", "telefono", "phone"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "employees": RoleProfile(
            frozenset({"empleado", "empleados", "employee", "employees", "staff", "personal"}),
            frozenset({"nombre", "name", "puesto", "position", "cargo", "role"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "payments": RoleProfile(
            frozenset({"pago", "pagos", "payment", "payments", "cobro", "cobros"}),
            frozenset({"monto", "amount", "metodo", "method", "fecha", "date"}),
            (frozenset({"monto", "amount", "total"}),),
            {"id": COMMON_ID, "amount": COMMON_TOTAL, "date": COMMON_DATE, "method": ("metodo", "method", "payment_method", "forma_pago")},
        ),
        "categories": RoleProfile(
            frozenset({"categoria", "categorias", "category", "categories", "department", "departments"}),
            frozenset({"nombre", "name", "descripcion", "description"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME},
        ),
        "suppliers": RoleProfile(
            frozenset({"proveedor", "proveedores", "supplier", "suppliers", "vendor", "vendors"}),
            frozenset({"nombre", "name", "email", "correo", "telefono", "phone"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
    },
    "education": {
        "students": RoleProfile(
            frozenset({"estudiante", "estudiantes", "student", "students", "alumno", "alumnos", "pupil", "pupils"}),
            frozenset({"nombre", "name", "grado", "grade", "carrera", "career", "matricula", "student_id"}),
            (),
            {"id": COMMON_ID + ("student_id", "alumno_id"), "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "teachers": RoleProfile(
            frozenset({"profesor", "profesores", "teacher", "teachers", "docente", "docentes", "instructor", "instructors"}),
            frozenset({"nombre", "name", "especialidad", "specialty", "department", "departamento"}),
            (),
            {"id": COMMON_ID + ("teacher_id", "docente_id"), "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "courses": RoleProfile(
            frozenset({"curso", "cursos", "course", "courses", "materia", "materias", "subject", "subjects", "asignatura", "asignaturas"}),
            frozenset({"nombre", "name", "creditos", "credits", "codigo", "code"}),
            (),
            {"id": COMMON_ID + ("course_id", "subject_id"), "name": COMMON_NAME, "credits": ("creditos", "credits"), "status": COMMON_STATUS},
        ),
        "enrollments": RoleProfile(
            frozenset({"inscripcion", "inscripciones", "enrollment", "enrollments", "matricula", "matriculas", "registration", "registrations"}),
            frozenset({"estudiante", "student", "curso", "course", "fecha", "date", "periodo", "semester"}),
            (),
            {"id": COMMON_ID, "date": COMMON_DATE, "status": COMMON_STATUS},
        ),
        "grades": RoleProfile(
            frozenset({"nota", "notas", "grade", "grades", "calificacion", "calificaciones", "score", "scores", "evaluation", "evaluations"}),
            frozenset({"nota", "grade", "score", "valor", "value", "estudiante", "student", "curso", "course"}),
            (frozenset({"nota", "grade", "score", "calificacion", "valor"}),),
            {"id": COMMON_ID, "value": ("nota", "grade", "score", "calificacion", "valor", "value"), "date": COMMON_DATE},
        ),
        "attendance": RoleProfile(
            frozenset({"asistencia", "attendance", "attendances", "presence"}),
            frozenset({"fecha", "date", "presente", "present", "ausente", "absent", "student", "estudiante"}),
            (),
            {"id": COMMON_ID, "date": COMMON_DATE, "status": ("estado", "status", "presente", "present")},
        ),
    },
    "healthcare": {
        "patients": RoleProfile(
            frozenset({"paciente", "pacientes", "patient", "patients", "expediente", "expedientes", "medical_record", "medical_records"}),
            frozenset({"nombre", "name", "nacimiento", "birth", "sangre", "blood", "patient_id"}),
            (),
            {"id": COMMON_ID + ("patient_id", "paciente_id"), "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "doctors": RoleProfile(
            frozenset({"doctor", "doctores", "doctors", "medico", "medicos", "physician", "physicians", "personal_medico"}),
            frozenset({"nombre", "name", "especialidad", "specialty", "license", "colegiado"}),
            (),
            {"id": COMMON_ID + ("doctor_id", "medico_id"), "name": COMMON_NAME, "specialty": ("especialidad", "specialty", "specialization")},
        ),
        "appointments": RoleProfile(
            frozenset({"cita", "citas", "appointment", "appointments", "consulta", "consultas", "visit", "visits"}),
            frozenset({"paciente", "patient", "doctor", "medico", "fecha", "date", "motivo", "reason"}),
            (frozenset({"fecha", "date", "appointment_date"}),),
            {"id": COMMON_ID, "date": COMMON_DATE + ("appointment_date", "fecha_cita"), "status": COMMON_STATUS, "reason": ("motivo", "reason", "reason_for_visit")},
        ),
        "diagnoses": RoleProfile(
            frozenset({"diagnostico", "diagnosticos", "diagnosis", "diagnoses", "diagnostic"}),
            frozenset({"diagnostico", "diagnosis", "codigo", "code", "descripcion", "description"}),
            (),
            {"id": COMMON_ID, "name": ("diagnostico", "diagnosis", "nombre", "name", "descripcion", "description"), "date": COMMON_DATE},
        ),
        "treatments": RoleProfile(
            frozenset({"tratamiento", "tratamientos", "treatment", "treatments", "procedure", "procedures"}),
            frozenset({"tratamiento", "treatment", "descripcion", "description", "fecha", "date"}),
            (),
            {"id": COMMON_ID, "name": COMMON_NAME + ("tratamiento", "treatment"), "date": COMMON_DATE, "status": COMMON_STATUS},
        ),
        "prescriptions": RoleProfile(
            frozenset({"receta", "recetas", "prescription", "prescriptions", "rx", "medicacion", "medication"}),
            frozenset({"medicamento", "medication", "drug", "dosis", "dose", "fecha", "date"}),
            (),
            {"id": COMMON_ID, "date": COMMON_DATE, "dose": ("dosis", "dose", "dosage")},
        ),
        "admissions": RoleProfile(
            frozenset({"admision", "admisiones", "admission", "admissions", "hospitalizacion", "hospitalizaciones", "stay", "stays"}),
            frozenset({"patient", "paciente", "entrada", "admission_date", "alta", "discharge"}),
            (),
            {"id": COMMON_ID, "date": COMMON_DATE + ("admission_date", "fecha_ingreso"), "status": COMMON_STATUS},
        ),
    },
    "transportation": {
        "vehicles": RoleProfile(
            frozenset({"vehiculo", "vehiculos", "vehicle", "vehicles", "bus", "buses", "camion", "camiones", "truck", "trucks", "fleet", "flota"}),
            frozenset({"placa", "plate", "modelo", "model", "marca", "brand", "capacidad", "capacity"}),
            (),
            {"id": COMMON_ID + ("vehicle_id",), "name": ("placa", "plate", "numero", "number", "nombre", "name"), "status": COMMON_STATUS},
        ),
        "drivers": RoleProfile(
            frozenset({"conductor", "conductores", "driver", "drivers", "chofer", "choferes"}),
            frozenset({"nombre", "name", "licencia", "license", "telefono", "phone"}),
            (),
            {"id": COMMON_ID + ("driver_id",), "name": COMMON_NAME, "status": COMMON_STATUS},
        ),
        "routes": RoleProfile(
            frozenset({"ruta", "rutas", "route", "routes", "trayecto", "trayectos", "itinerary", "itineraries"}),
            frozenset({"origen", "origin", "destino", "destination", "distance", "distancia"}),
            (),
            {"id": COMMON_ID + ("route_id",), "name": COMMON_NAME, "origin": ("origen", "origin", "from_location"), "destination": ("destino", "destination", "to_location")},
        ),
        "trips": RoleProfile(
            frozenset({"viaje", "viajes", "trip", "trips", "journey", "journeys", "ride", "rides"}),
            frozenset({"fecha", "date", "salida", "departure", "llegada", "arrival", "ruta", "route", "vehicle"}),
            (frozenset({"fecha", "date", "departure", "salida"}),),
            {"id": COMMON_ID + ("trip_id",), "date": COMMON_DATE + ("departure", "salida", "departure_time"), "status": COMMON_STATUS},
        ),
        "passengers": RoleProfile(
            frozenset({"pasajero", "pasajeros", "passenger", "passengers", "traveler", "travelers"}),
            frozenset({"nombre", "name", "documento", "document", "ticket", "boleto"}),
            (),
            {"id": COMMON_ID + ("passenger_id",), "name": COMMON_NAME},
        ),
        "tickets": RoleProfile(
            frozenset({"ticket", "tickets", "boleto", "boletos", "pasaje", "pasajes"}),
            frozenset({"precio", "price", "seat", "asiento", "trip", "viaje", "passenger", "pasajero"}),
            (),
            {"id": COMMON_ID, "amount": COMMON_TOTAL + ("precio", "price", "fare"), "status": COMMON_STATUS},
        ),
    },
    "hospitality": {
        "rooms": RoleProfile(frozenset({"habitacion", "habitaciones", "room", "rooms"}), frozenset({"numero", "number", "precio", "price", "tipo", "type"}), (), {"id": COMMON_ID, "name": ("numero", "number", "nombre", "name"), "price": ("precio", "price", "rate"), "status": COMMON_STATUS}),
        "guests": RoleProfile(frozenset({"huesped", "huespedes", "guest", "guests"}), frozenset({"nombre", "name", "email", "correo"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
        "reservations": RoleProfile(frozenset({"reserva", "reservas", "reservation", "reservations", "booking", "bookings"}), frozenset({"checkin", "checkout", "guest", "huesped", "room", "habitacion"}), (), {"id": COMMON_ID, "date": COMMON_DATE + ("checkin", "check_in", "arrival_date"), "total": COMMON_TOTAL, "status": COMMON_STATUS}),
        "stays": RoleProfile(frozenset({"estadia", "estadias", "stay", "stays"}), frozenset({"entrada", "salida", "checkin", "checkout"}), (), {"id": COMMON_ID, "date": COMMON_DATE + ("checkin", "check_in"), "status": COMMON_STATUS}),
    },
    "restaurant": {
        "menu_items": RoleProfile(frozenset({"menu", "plato", "platos", "dish", "dishes", "menu_item", "menu_items"}), frozenset({"nombre", "name", "precio", "price", "categoria", "category"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "price": ("precio", "price")}),
        "tables": RoleProfile(frozenset({"mesa", "mesas", "dining_table", "dining_tables"}), frozenset({"numero", "number", "capacity", "capacidad"}), (), {"id": COMMON_ID, "name": ("numero", "number", "nombre", "name"), "status": COMMON_STATUS}),
        "orders": RoleProfile(frozenset({"orden", "ordenes", "order", "orders", "pedido", "pedidos"}), frozenset({"total", "fecha", "date", "mesa", "table"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "total": COMMON_TOTAL, "status": COMMON_STATUS}),
        "order_details": RoleProfile(frozenset({"order_detail", "order_details", "detalle_orden", "detalle_pedido", "line_items"}), frozenset({"quantity", "cantidad", "price", "precio"}), (), {"id": COMMON_ID, "quantity": COMMON_QUANTITY, "price": ("precio", "price", "unit_price"), "total": COMMON_TOTAL}),
        "ingredients": RoleProfile(frozenset({"ingrediente", "ingredientes", "ingredient", "ingredients"}), frozenset({"nombre", "name", "stock", "quantity", "cantidad"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "stock": COMMON_QUANTITY}),
    },
    "professional_services": {
        "services": RoleProfile(frozenset({"servicio", "servicios", "service", "services"}), frozenset({"nombre", "name", "precio", "price", "tarifa", "rate"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "price": ("precio", "price", "tarifa", "rate")}),
        "clients": RoleProfile(frozenset({"cliente", "clientes", "client", "clients", "customer", "customers"}), frozenset({"nombre", "name", "email", "correo"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
        "appointments": RoleProfile(frozenset({"cita", "citas", "appointment", "appointments", "agenda"}), frozenset({"fecha", "date", "client", "cliente", "service", "servicio"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "status": COMMON_STATUS}),
        "projects": RoleProfile(frozenset({"proyecto", "proyectos", "project", "projects", "job", "jobs", "workorder", "workorders"}), frozenset({"cliente", "client", "fecha", "date", "estado", "status"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "date": COMMON_DATE, "status": COMMON_STATUS}),
        "invoices": RoleProfile(frozenset({"factura", "facturas", "invoice", "invoices"}), frozenset({"total", "amount", "fecha", "date", "cliente", "client"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "total": COMMON_TOTAL, "status": COMMON_STATUS}),
        "payments": RoleProfile(frozenset({"pago", "pagos", "payment", "payments"}), frozenset({"amount", "monto", "fecha", "date"}), (), {"id": COMMON_ID, "amount": COMMON_TOTAL, "date": COMMON_DATE}),
    },
    "finance_accounting": {
        "accounts": RoleProfile(frozenset({"cuenta", "cuentas", "account", "accounts", "ledger"}), frozenset({"nombre", "name", "saldo", "balance", "tipo", "type"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "balance": ("saldo", "balance", "current_balance")}),
        "transactions": RoleProfile(frozenset({"transaccion", "transacciones", "transaction", "transactions", "movimiento", "movimientos"}), frozenset({"amount", "monto", "fecha", "date", "debit", "credit"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "amount": COMMON_TOTAL, "type": ("tipo", "type", "transaction_type")}),
        "journal_entries": RoleProfile(frozenset({"asiento", "asientos", "journal", "journal_entry", "journal_entries", "entries"}), frozenset({"debit", "debito", "credit", "credito", "account", "cuenta"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "debit": ("debito", "debit"), "credit": ("credito", "credit")}),
    },
    "manufacturing": {
        "products": RoleProfile(frozenset({"producto", "productos", "product", "products", "finished_goods"}), frozenset({"nombre", "name", "sku", "code"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
        "materials": RoleProfile(frozenset({"material", "materials", "materia_prima", "raw_material", "raw_materials"}), frozenset({"nombre", "name", "stock", "quantity"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "stock": COMMON_QUANTITY}),
        "machines": RoleProfile(frozenset({"maquina", "maquinas", "machine", "machines", "equipment", "equipo"}), frozenset({"nombre", "name", "status", "estado"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "status": COMMON_STATUS}),
        "production_orders": RoleProfile(frozenset({"orden_produccion", "production_order", "production_orders", "workorder", "workorders"}), frozenset({"quantity", "cantidad", "fecha", "date", "product", "producto"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "quantity": COMMON_QUANTITY, "status": COMMON_STATUS}),
        "inventory": RoleProfile(frozenset({"inventario", "inventory", "stock", "warehouse", "almacen"}), frozenset({"stock", "quantity", "cantidad"}), (), {"id": COMMON_ID, "stock": COMMON_QUANTITY}),
        "suppliers": RoleProfile(frozenset({"proveedor", "proveedores", "supplier", "suppliers", "vendor", "vendors"}), frozenset({"nombre", "name"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
    },
    "human_resources": {
        "employees": RoleProfile(frozenset({"empleado", "empleados", "employee", "employees", "staff", "personal"}), frozenset({"nombre", "name", "puesto", "position", "salary", "salario"}), (), {"id": COMMON_ID, "name": COMMON_NAME, "status": COMMON_STATUS}),
        "payroll": RoleProfile(frozenset({"nomina", "payroll", "payrolls"}), frozenset({"salario", "salary", "amount", "monto", "employee", "empleado"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "amount": COMMON_TOTAL + ("salario", "salary")}),
        "departments": RoleProfile(frozenset({"departamento", "departamentos", "department", "departments"}), frozenset({"nombre", "name"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
        "attendance": RoleProfile(frozenset({"asistencia", "attendance", "attendances"}), frozenset({"fecha", "date", "entrada", "checkin", "salida", "checkout"}), (), {"id": COMMON_ID, "date": COMMON_DATE, "status": COMMON_STATUS}),
        "shifts": RoleProfile(frozenset({"turno", "turnos", "shift", "shifts"}), frozenset({"inicio", "start", "fin", "end"}), (), {"id": COMMON_ID, "name": COMMON_NAME}),
    },
}


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def tokens(value: str) -> set[str]:
    normalized = normalize_name(value)
    result = {token for token in normalized.split("_") if token}
    if normalized:
        result.add(normalized)
    return result


def table_column_tokens(table: TableSchema) -> set[str]:
    result: set[str] = set()
    for column in table.columns:
        result.update(tokens(column.name))
    return result


def _column_matches_group(table: TableSchema, group: frozenset[str]) -> bool:
    for column in table.columns:
        if group & tokens(column.name):
            return True
    return False


def _relationship_degree(schema: DatabaseSchema, table_name: str) -> int:
    degree = 0
    for relation in schema.relationships:
        if relation.table == table_name or relation.references_table == table_name:
            degree += 1
    return degree


def score_table_for_role(
    schema: DatabaseSchema,
    table_name: str,
    role: RoleProfile,
) -> tuple[float, list[str]]:
    table = schema.tables[table_name]
    table_tokens = tokens(table_name)
    column_tokens = table_column_tokens(table)
    evidence: list[str] = []
    score = 0.0

    exact_normalized = normalize_name(table_name)
    normalized_terms = {normalize_name(term) for term in role.table_terms}

    if exact_normalized in normalized_terms:
        score += 6.0
        evidence.append("coincidencia exacta del nombre de tabla")
    else:
        table_hits = role.table_terms & table_tokens
        if table_hits:
            score += min(4.0, 1.5 + len(table_hits))
            evidence.append(f"nombre de tabla coincide con {sorted(table_hits)}")

    column_hits = role.column_terms & column_tokens
    if column_hits:
        score += min(4.0, len(column_hits) * 0.8)
        evidence.append(f"columnas semánticas {sorted(column_hits)}")

    required_ok = True
    for group in role.required_column_groups:
        if not _column_matches_group(table, group):
            required_ok = False
            break

    if role.required_column_groups:
        if required_ok:
            score += 2.0
            evidence.append("cumple columnas estructurales requeridas")
        else:
            score -= 2.0
            evidence.append("faltan columnas estructurales esperadas")

    if table.primary_key:
        score += 0.4
        evidence.append("tiene llave primaria")

    degree = _relationship_degree(schema, table_name)
    if degree:
        bonus = min(1.5, degree * 0.3)
        score += bonus
        evidence.append(f"participa en {degree} relación(es)")

    return max(score, 0.0), evidence


def find_best_table_for_role(
    schema: DatabaseSchema,
    role: RoleProfile,
    minimum_score: float = 2.5,
) -> dict | None:
    candidates: list[dict] = []

    for table_name in schema.tables:
        score, evidence = score_table_for_role(schema, table_name, role)
        if score <= 0:
            continue
        candidates.append({
            "table": table_name,
            "score": round(score, 2),
            "evidence": evidence,
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)

    if not candidates or candidates[0]["score"] < minimum_score:
        return None

    best = candidates[0]
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    margin = best["score"] - second_score

    if best["score"] >= 8 and margin >= 1.5:
        confidence = "high"
    elif best["score"] >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    best["confidence"] = confidence
    best["ambiguous"] = len(candidates) > 1 and margin < 1.25
    best["alternatives"] = candidates[1:4]
    return best


def find_column(table: TableSchema, aliases: tuple[str, ...]) -> str | None:
    normalized_aliases = [normalize_name(alias) for alias in aliases]

    for alias in normalized_aliases:
        for column in table.columns:
            if normalize_name(column.name) == alias:
                return column.name

    for alias in normalized_aliases:
        alias_tokens = tokens(alias)
        for column in table.columns:
            if alias_tokens & tokens(column.name):
                return column.name

    return None


def map_role_columns(table: TableSchema, role: RoleProfile) -> dict:
    mapped: dict[str, str] = {}
    for semantic_name, aliases in role.preferred_columns.items():
        column = find_column(table, aliases)
        if column:
            mapped[semantic_name] = column
    return mapped


def map_relations(schema: DatabaseSchema, entities: dict[str, dict]) -> list[dict]:
    table_to_role = {
        entity["table"]: role
        for role, entity in entities.items()
        if entity.get("table")
    }

    relations: list[dict] = []
    for relation in schema.relationships:
        from_role = table_to_role.get(relation.table)
        to_role = table_to_role.get(relation.references_table)

        if not from_role and not to_role:
            continue

        relations.append({
            "from_role": from_role,
            "from_table": relation.table,
            "from_column": relation.column,
            "to_role": to_role,
            "to_table": relation.references_table,
            "to_column": relation.references_column,
        })

    return relations


def build_semantic_model(
    schema: DatabaseSchema,
    domain_result: dict | None = None,
) -> dict:
    domain_result = domain_result or detect_business_domains(schema)
    domain = domain_result.get("primary_domain")

    if not domain or domain not in ROLE_PROFILES:
        return {
            "domain": domain,
            "domain_confidence": domain_result.get("primary_confidence", "insufficient"),
            "ambiguous_domain": domain_result.get("ambiguous", False),
            "entities": {},
            "relations": [],
            "unmapped_tables": sorted(schema.tables.keys()),
        }

    entities: dict[str, dict] = {}

    for role_name, role_profile in ROLE_PROFILES[domain].items():
        match = find_best_table_for_role(schema, role_profile)
        if not match:
            continue

        table = schema.tables[match["table"]]
        entities[role_name] = {
            "table": match["table"],
            "confidence": match["confidence"],
            "ambiguous": match["ambiguous"],
            "score": match["score"],
            "columns": map_role_columns(table, role_profile),
            "evidence": match["evidence"],
            "alternatives": match["alternatives"],
        }

    mapped_tables = {entity["table"] for entity in entities.values()}

    return {
        "domain": domain,
        "domain_confidence": domain_result.get("primary_confidence", "insufficient"),
        "ambiguous_domain": domain_result.get("ambiguous", False),
        "entities": entities,
        "relations": map_relations(schema, entities),
        "unmapped_tables": sorted(set(schema.tables.keys()) - mapped_tables),
    }


def inspect_semantic_model() -> dict:
    schema = inspect_database()
    domain_result = detect_business_domains(schema)
    semantic_model = build_semantic_model(schema, domain_result)

    return {
        "database": schema.database,
        "business_domain": {
            "primary": domain_result.get("primary_domain"),
            "confidence": domain_result.get("primary_confidence"),
            "ambiguous": domain_result.get("ambiguous", False),
            "candidates": domain_result.get("candidates", []),
        },
        "semantic_model": semantic_model,
    }
