import re
import unicodedata
from dataclasses import dataclass

from app.database.inspector import inspect_database
from app.database.schema import DatabaseSchema


@dataclass(frozen=True)
class DomainSignal:
    terms: frozenset[str]
    weight: float
    label: str


# Cada dominio se define por conceptos, no por nombres exactos de tablas.
# Los términos se buscan tanto en tablas como en columnas y soportan
# español/inglés, snake_case, camelCase y separadores variados.
DOMAIN_PROFILES: dict[str, list[DomainSignal]] = {
    "retail": [
        DomainSignal(frozenset({"producto", "productos", "product", "products", "item", "items", "articulo", "articulos", "sku"}), 2.0, "catálogo de productos"),
        DomainSignal(frozenset({"venta", "ventas", "sale", "sales", "order", "orders", "pedido", "pedidos", "factura", "facturas", "invoice", "invoices"}), 2.0, "ventas/pedidos"),
        DomainSignal(frozenset({"inventario", "inventory", "stock", "existencia", "existencias", "warehouse"}), 1.8, "inventario"),
        DomainSignal(frozenset({"categoria", "categorias", "category", "categories", "marca", "brand", "brands", "talla", "size", "sizes", "color", "colors"}), 1.4, "atributos de catálogo"),
        DomainSignal(frozenset({"cliente", "clientes", "customer", "customers", "buyer", "buyers"}), 1.2, "clientes"),
    ],
    "education": [
        DomainSignal(frozenset({"estudiante", "estudiantes", "student", "students", "alumno", "alumnos", "pupil", "pupils"}), 2.3, "estudiantes"),
        DomainSignal(frozenset({"curso", "cursos", "course", "courses", "materia", "materias", "subject", "subjects", "asignatura", "asignaturas"}), 2.0, "cursos/materias"),
        DomainSignal(frozenset({"inscripcion", "inscripciones", "enrollment", "enrollments", "matricula", "matriculas", "registration", "registrations"}), 2.0, "inscripciones"),
        DomainSignal(frozenset({"nota", "notas", "grade", "grades", "calificacion", "calificaciones", "score", "scores"}), 1.8, "calificaciones"),
        DomainSignal(frozenset({"profesor", "profesores", "teacher", "teachers", "docente", "docentes", "instructor", "instructors"}), 1.8, "docentes"),
        DomainSignal(frozenset({"asistencia", "attendance", "aula", "aulas", "classroom", "classrooms", "periodo", "semester", "semestre"}), 1.2, "operación académica"),
    ],
    "healthcare": [
        DomainSignal(frozenset({"paciente", "pacientes", "patient", "patients"}), 2.5, "pacientes"),
        DomainSignal(frozenset({"doctor", "doctores", "doctors", "medico", "medicos", "physician", "physicians"}), 2.2, "personal médico"),
        DomainSignal(frozenset({"cita", "citas", "appointment", "appointments", "consulta", "consultas"}), 2.0, "citas/consultas"),
        DomainSignal(frozenset({"diagnostico", "diagnosticos", "diagnosis", "diagnoses", "diagnostic"}), 1.8, "diagnósticos"),
        DomainSignal(frozenset({"receta", "recetas", "prescription", "prescriptions", "medicamento", "medicamentos", "medication", "medications", "drug", "drugs"}), 1.7, "medicación"),
        DomainSignal(frozenset({"tratamiento", "tratamientos", "treatment", "treatments", "admision", "admission", "hospitalizacion", "ward", "room"}), 1.5, "tratamientos/hospitalización"),
    ],
    "transportation": [
        DomainSignal(frozenset({"vehiculo", "vehiculos", "vehicle", "vehicles", "bus", "buses", "camion", "camiones", "truck", "trucks", "fleet", "flota"}), 2.2, "vehículos/flota"),
        DomainSignal(frozenset({"ruta", "rutas", "route", "routes", "trayecto", "trayectos", "itinerary", "itineraries"}), 2.0, "rutas"),
        DomainSignal(frozenset({"viaje", "viajes", "trip", "trips", "journey", "journeys", "ride", "rides"}), 2.0, "viajes"),
        DomainSignal(frozenset({"conductor", "conductores", "driver", "drivers", "chofer", "choferes"}), 1.8, "conductores"),
        DomainSignal(frozenset({"pasajero", "pasajeros", "passenger", "passengers", "ticket", "tickets", "boleto", "boletos"}), 1.6, "pasajeros/boletos"),
        DomainSignal(frozenset({"parada", "paradas", "stop", "stops", "horario", "schedule", "schedules", "shipment", "shipments", "envio", "envios"}), 1.3, "operación logística"),
    ],
    "hospitality": [
        DomainSignal(frozenset({"hotel", "hotels", "habitacion", "habitaciones", "room", "rooms"}), 2.2, "habitaciones/alojamiento"),
        DomainSignal(frozenset({"reserva", "reservas", "reservation", "reservations", "booking", "bookings"}), 2.2, "reservas"),
        DomainSignal(frozenset({"huesped", "huespedes", "guest", "guests"}), 1.8, "huéspedes"),
        DomainSignal(frozenset({"estadia", "estadias", "stay", "stays", "checkin", "checkout"}), 1.5, "estadías"),
    ],
    "restaurant": [
        DomainSignal(frozenset({"menu", "menus", "plato", "platos", "dish", "dishes", "comida", "food"}), 2.2, "menú/platos"),
        DomainSignal(frozenset({"mesa", "mesas", "table", "tables"}), 1.8, "mesas"),
        DomainSignal(frozenset({"orden", "ordenes", "order", "orders", "pedido", "pedidos"}), 1.8, "órdenes"),
        DomainSignal(frozenset({"ingrediente", "ingredientes", "ingredient", "ingredients", "receta", "recipe", "recipes"}), 1.6, "ingredientes/recetas"),
    ],
    "professional_services": [
        DomainSignal(frozenset({"servicio", "servicios", "service", "services"}), 2.2, "servicios"),
        DomainSignal(frozenset({"cliente", "clientes", "client", "clients", "customer", "customers"}), 1.6, "clientes"),
        DomainSignal(frozenset({"cita", "citas", "appointment", "appointments", "agenda", "schedule"}), 1.5, "agenda/citas"),
        DomainSignal(frozenset({"proyecto", "proyectos", "project", "projects", "trabajo", "job", "jobs", "workorder", "workorders"}), 1.5, "trabajos/proyectos"),
        DomainSignal(frozenset({"factura", "facturas", "invoice", "invoices", "pago", "pagos", "payment", "payments"}), 1.2, "facturación"),
    ],
    "finance_accounting": [
        DomainSignal(frozenset({"cuenta", "cuentas", "account", "accounts", "ledger", "mayor"}), 2.2, "cuentas contables"),
        DomainSignal(frozenset({"transaccion", "transacciones", "transaction", "transactions", "movimiento", "movimientos"}), 2.0, "transacciones"),
        DomainSignal(frozenset({"asiento", "asientos", "journal", "entry", "entries"}), 1.8, "asientos contables"),
        DomainSignal(frozenset({"debito", "debit", "credito", "credit", "balance", "saldo"}), 1.5, "débitos/créditos/saldos"),
        DomainSignal(frozenset({"factura", "invoice", "pago", "payment", "cobro", "receipt"}), 1.0, "documentos financieros"),
    ],
    "manufacturing": [
        DomainSignal(frozenset({"produccion", "production", "manufacturing", "fabricacion"}), 2.3, "producción"),
        DomainSignal(frozenset({"material", "materials", "materia", "materias", "rawmaterial", "rawmaterials"}), 1.8, "materiales"),
        DomainSignal(frozenset({"maquina", "maquinas", "machine", "machines", "equipment", "equipo"}), 1.7, "maquinaria"),
        DomainSignal(frozenset({"lote", "lotes", "batch", "batches", "bom", "billofmaterials"}), 1.7, "lotes/BOM"),
        DomainSignal(frozenset({"ordenproduccion", "workorder", "workorders", "orden_trabajo"}), 1.6, "órdenes de producción"),
        DomainSignal(frozenset({"inventario", "inventory", "stock", "warehouse", "almacen"}), 1.0, "inventario"),
    ],
    "human_resources": [
        DomainSignal(frozenset({"empleado", "empleados", "employee", "employees", "staff", "personal"}), 2.2, "empleados"),
        DomainSignal(frozenset({"nomina", "payroll", "salario", "salary", "salaries"}), 2.0, "nómina"),
        DomainSignal(frozenset({"departamento", "departamentos", "department", "departments"}), 1.4, "departamentos"),
        DomainSignal(frozenset({"asistencia", "attendance", "turno", "turnos", "shift", "shifts"}), 1.4, "asistencia/turnos"),
        DomainSignal(frozenset({"vacacion", "vacaciones", "leave", "absence", "ausencia"}), 1.2, "ausencias/vacaciones"),
    ],
}


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def tokenize(value: str) -> set[str]:
    normalized = normalize_name(value)
    tokens = {token for token in normalized.split("_") if token}
    if normalized:
        tokens.add(normalized)
    return tokens


def _schema_tokens(schema: DatabaseSchema) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    table_tokens: dict[str, set[str]] = {}
    column_tokens: dict[str, set[str]] = {}

    for table_name, table in schema.tables.items():
        table_tokens[table_name] = tokenize(table_name)
        tokens: set[str] = set()
        for column in table.columns:
            tokens.update(tokenize(column.name))
        column_tokens[table_name] = tokens

    return table_tokens, column_tokens


def _matching_tables(
    schema: DatabaseSchema,
    signal: DomainSignal,
    table_tokens: dict[str, set[str]],
    column_tokens: dict[str, set[str]],
) -> list[str]:
    matches: list[str] = []

    for table_name in schema.tables:
        combined = table_tokens[table_name] | column_tokens[table_name]
        if signal.terms & combined:
            matches.append(table_name)

    return matches


def _relationship_bonus(schema: DatabaseSchema, matched_tables: set[str]) -> float:
    if len(matched_tables) < 2:
        return 0.0

    links = 0
    for relationship in schema.relationships:
        if (
            relationship.table in matched_tables
            and relationship.references_table in matched_tables
        ):
            links += 1

    return min(links * 0.35, 1.75)


def detect_business_domains(schema: DatabaseSchema) -> dict:
    table_tokens, column_tokens = _schema_tokens(schema)
    results: list[dict] = []

    for domain, signals in DOMAIN_PROFILES.items():
        raw_score = 0.0
        max_score = sum(signal.weight for signal in signals) + 1.75
        evidence: list[dict] = []
        domain_tables: set[str] = set()

        for signal in signals:
            tables = _matching_tables(
                schema,
                signal,
                table_tokens,
                column_tokens,
            )

            if not tables:
                continue

            # Una señal cuenta una vez aunque aparezca en varias tablas.
            raw_score += signal.weight
            domain_tables.update(tables)
            evidence.append({
                "signal": signal.label,
                "weight": signal.weight,
                "tables": sorted(tables),
            })

        relationship_bonus = _relationship_bonus(schema, domain_tables)
        raw_score += relationship_bonus

        score = round(min(raw_score / max_score, 1.0) * 100, 1) if max_score else 0.0

        if score >= 65:
            confidence = "high"
        elif score >= 40:
            confidence = "medium"
        elif score >= 20:
            confidence = "low"
        else:
            confidence = "insufficient"

        results.append({
            "domain": domain,
            "score": score,
            "confidence": confidence,
            "matched_tables": sorted(domain_tables),
            "relationship_bonus": round(relationship_bonus, 2),
            "evidence": evidence,
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    candidates = [
        item for item in results
        if item["confidence"] in {"high", "medium"}
    ]

    primary = candidates[0] if candidates else None

    # Si los dos primeros están muy cerca, no fingimos certeza absoluta.
    ambiguous = False
    if len(candidates) >= 2:
        ambiguous = abs(candidates[0]["score"] - candidates[1]["score"]) < 8

    return {
        "database": schema.database,
        "primary_domain": primary["domain"] if primary else None,
        "primary_confidence": primary["confidence"] if primary else "insufficient",
        "ambiguous": ambiguous,
        "candidates": candidates,
        "all_scores": results,
        "schema_summary": {
            "tables": len(schema.tables),
            "relationships": len(schema.relationships),
        },
    }


def inspect_business_domains() -> dict:
    return detect_business_domains(inspect_database())
