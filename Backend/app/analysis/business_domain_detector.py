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
    "insurance": [
        DomainSignal(frozenset({"poliza","polizas","policy","policies","policy_number","numero_poliza"}), 3.4, "pólizas"),
        DomainSignal(frozenset({"siniestro","siniestros","claim","claims","reclamacion","reclamaciones"}), 3.1, "siniestros y reclamaciones"),
        DomainSignal(frozenset({"asegurado","asegurados","insured","insureds","beneficiario_poliza"}), 2.5, "asegurados"),
        DomainSignal(frozenset({"cobertura","coberturas","coverage","coverages","deducible","deductible"}), 2.2, "coberturas"),
        DomainSignal(frozenset({"prima","primas","premium","premiums","renovacion_poliza"}), 2, "primas"),
        DomainSignal(frozenset({"aseguradora","aseguradoras","insurer","insurers","corredor_seguros"}), 1.8, "aseguradoras"),
    ],
    "pharmacy": [
        DomainSignal(frozenset({"medicamento","medicamentos","farmaco","farmacos","drug","drugs","medicine","medicines","pharmaceutical"}), 3.4, "medicamentos"),
        DomainSignal(frozenset({"lote_medicamento","lotes_medicamentos","batch_number","numero_lote","fecha_caducidad","fecha_vencimiento","expiration_date"}), 3.2, "lotes y caducidad"),
        DomainSignal(frozenset({"dispensacion","dispensaciones","dispensing","dispensation","venta_farmacia"}), 3, "dispensaciones"),
        DomainSignal(frozenset({"receta_medica","recetas_medicas","prescription","prescriptions","prescriptor"}), 2, "prescripciones"),
        DomainSignal(frozenset({"farmacia","farmacias","pharmacy","pharmacies","botica","boticas"}), 2.7, "farmacias"),
        DomainSignal(frozenset({"principio_activo","active_ingredient","dosis","dosage","presentacion_farmaceutica"}), 1.8, "composición farmacéutica"),
    ],
    "saas": [
        DomainSignal(frozenset({"suscripcion","suscripciones","subscription","subscriptions","subscription_id"}), 3.5, "suscripciones"),
        DomainSignal(frozenset({"plan_saas","planes_saas","pricing_plan","subscription_plan","plan_id"}), 2.2, "planes"),
        DomainSignal(frozenset({"tenant_id","organization_id","organizacion","organizaciones","workspace","workspaces"}), 2.2, "organizaciones"),
        DomainSignal(frozenset({"ticket_soporte","tickets_soporte","support_ticket","support_tickets","incident_ticket"}), 2.4, "soporte"),
        DomainSignal(frozenset({"facturacion_recurrente","recurring_invoice","billing_cycle","mrr","arr","renovacion_suscripcion"}), 2.5, "facturación recurrente"),
        DomainSignal(frozenset({"software","saas","licencia_software","software_license","licencias_software"}), 2, "software"),
    ],
    "events": [
        DomainSignal(frozenset({"evento","eventos","event","events","festival","concierto","conciertos"}), 3.5, "eventos"),
        DomainSignal(frozenset({"entrada_evento","entradas_evento","ticket_event","event_tickets","boleto_evento"}), 3.1, "entradas"),
        DomainSignal(frozenset({"asistente","asistentes","attendee","attendees","registro_evento"}), 2.8, "asistentes"),
        DomainSignal(frozenset({"recinto","recintos","venue","venues","escenario","auditorio"}), 1.8, "recintos"),
        DomainSignal(frozenset({"aforo","capacity_event","localidad","localidades","seat_number","numero_asiento"}), 1.7, "aforo y asientos"),
        DomainSignal(frozenset({"organizador_evento","event_organizer","promotor_evento","event_booking"}), 1.8, "organización"),
    ],
    "fitness": [
        DomainSignal(frozenset({"gimnasio","gimnasios","gym","gyms","fitness_center"}), 3.3, "gimnasios"),
        DomainSignal(frozenset({"membresia","membresias","membership","memberships","member_id"}), 3.3, "membresías"),
        DomainSignal(frozenset({"entrenador","entrenadores","trainer","trainers","coach","coaches"}), 2.3, "entrenadores"),
        DomainSignal(frozenset({"clase_fitness","clases_fitness","fitness_class","fitness_classes","class_booking"}), 2.4, "clases"),
        DomainSignal(frozenset({"control_acceso","check_in_gym","asistencia_gimnasio","gym_attendance"}), 2.2, "asistencia"),
        DomainSignal(frozenset({"rutina","rutinas","workout","workouts","plan_entrenamiento"}), 1.7, "entrenamientos"),
    ],
    # Distinct economic sectors (ISIC Rev.5 A, F, M). Avoid generic
    # "project", "client", or "payment" as primary evidence.
    "real_estate": [
        DomainSignal(frozenset({"inmueble", "inmuebles", "propiedad", "propiedades",
                                "property", "properties", "real_estate", "inmobiliaria"}), 3.4, "inmuebles"),
        DomainSignal(frozenset({"arrendamiento", "arrendamientos", "arriendo", "arriendos",
                                "lease", "leases", "leasing", "contrato_alquiler"}), 2.6, "arrendamientos"),
        DomainSignal(frozenset({"inquilino", "inquilinos", "tenant", "tenants",
                                "arrendatario", "arrendatarios"}), 2.3, "inquilinos"),
        DomainSignal(frozenset({"agente_inmobiliario", "corredor_inmobiliario",
                                "agentes_inmobiliarios", "real_estate_agent", "realtor",
                                "property_manager"}), 1.8, "agentes inmobiliarios"),
        DomainSignal(frozenset({"venta_inmueble", "compraventa", "venta_propiedad",
                                "property_sale", "real_estate_sale", "escritura"}), 1.7, "operaciones inmobiliarias"),
        DomainSignal(frozenset({"unidad_habitacional", "unidad_inmobiliaria",
                                "apartamento", "apartamentos", "condominio",
                                "lote_terreno", "parcelas_urbanas"}), 1.4, "unidades inmobiliarias"),
    ],
    "construction": [
        DomainSignal(frozenset({"obra", "obras", "construccion", "construcciones",
                                "construction", "construction_projects", "building_site",
                                "site_work"}), 3.6, "obras"),
        DomainSignal(frozenset({"presupuesto_obra", "presupuestos_obra",
                                "presupuesto_construccion", "construction_budget",
                                "budgeted_cost", "costo_obra"}), 2.4, "presupuestos de obra"),
        DomainSignal(frozenset({"contratista", "contratistas", "subcontratista",
                                "subcontratistas", "contractor", "contractors",
                                "subcontractor", "subcontractors"}), 2.4, "contratistas"),
        DomainSignal(frozenset({"avance_obra", "avance_fisico", "porcentaje_avance",
                                "construction_progress", "progress_pct",
                                "certificacion_obra"}), 2.1, "avance de obra"),
        DomainSignal(frozenset({"materiales_obra", "consumo_materiales", "material_construccion",
                                "building_materials", "requisicion_materiales"}), 1.4, "materiales de construcción"),
        DomainSignal(frozenset({"planilla_obra", "etapas_obra", "cronograma_obra",
                                "hitos_obra", "construction_schedule"}), 1.3, "etapas y planificación"),
    ],
    "agriculture": [
        DomainSignal(frozenset({"cultivo", "cultivos", "crop", "crops", "siembra",
                                "siembras", "plantacion", "plantaciones"}), 3.2, "cultivos"),
        DomainSignal(frozenset({"cosecha", "cosechas", "harvest", "harvests",
                                "rendimiento_cultivo", "yield_per_hectare"}), 2.8, "cosechas"),
        DomainSignal(frozenset({"parcela", "parcelas", "lote_agricola", "lotes_agricolas",
                                "farmland", "field", "fields", "finca", "fincas"}), 2.5, "parcelas agrícolas"),
        DomainSignal(frozenset({"ganado", "ganaderia", "livestock", "rebaño",
                                "rebanos", "animales_granja", "animal_farm"}), 2.8, "ganadería"),
        DomainSignal(frozenset({"riego", "irrigacion", "irrigation", "fertilizante",
                                "fertilizantes", "fertilizer", "fertilizers",
                                "agroquimico", "agroquimicos"}), 1.5, "insumos agrícolas"),
        DomainSignal(frozenset({"produccion_agricola", "produccion_pecuaria",
                                "agricultural_output", "farm_production",
                                "peso_cosechado", "toneladas_cosecha"}), 2.0, "producción primaria"),
    ],
    # Logistics is distinct from passenger transportation and from retail sales.
    # One generic "pedido" is intentionally insufficient to classify it.
    "logistics": [
        DomainSignal(frozenset({"movimiento_inventario", "stock_movement", "transferencia_almacen", "stock_transfer", "entrada_almacen"}), 2.5, "movimientos de inventario"),
        DomainSignal(frozenset({"orden_compra", "ordenes_compra", "purchase_order", "purchase_orders", "recepcion_mercancia"}), 1.8, "abastecimiento"),

        DomainSignal(frozenset({"envio", "envios", "shipment", "shipments", "shipping",
                                "entrega", "entregas", "delivery", "deliveries",
                                "despacho", "despachos", "dispatch", "fulfillment"}), 4.0, "envíos y entregas"),
        DomainSignal(frozenset({"guia", "guias", "numero_guia", "tracking", "tracking_number",
                                "rastreo", "seguimiento", "remision", "remisiones",
                                "waybill", "awb"}), 3.0, "guías y seguimiento"),
        DomainSignal(frozenset({"paquete", "paquetes", "parcel", "parcels",
                                "package", "packages", "bulto", "bultos"}), 2.0, "paquetería"),
        DomainSignal(frozenset({"transportista", "transportistas", "carrier", "carriers",
                                "courier", "couriers", "mensajero", "mensajeros",
                                "repartidor", "repartidores"}), 1.8, "transportistas"),
        DomainSignal(frozenset({"fecha_envio", "estado_envio", "fecha_entrega",
                                "estado_entrega", "shipping_date", "shipped_at",
                                "delivery_date", "delivery_status", "shipment_status",
                                "delivered_at"}), 2.8, "fechas y estados logísticos"),
        DomainSignal(frozenset({"destinatario", "destinatarios", "recipient", "recipients",
                                "direccion_entrega", "delivery_address",
                                "direccion_destino", "destination_address"}), 1.6, "destinos y destinatarios"),
        DomainSignal(frozenset({"pedido", "pedidos", "order", "orders", "picking",
                                "preparacion_pedido", "order_fulfillment"}), 1.2, "órdenes a despachar"),
        DomainSignal(frozenset({"bodega", "bodegas", "warehouse", "warehouses",
                                "almacen", "almacenes", "centro_distribucion"}), 1.1, "almacenamiento"),
    ],
    "vehicle_rental": [
        DomainSignal(frozenset({"renta", "rentas", "alquiler", "alquileres", "rental", "rentals", "rentacar", "car_rental"}), 3.2, "contratos de renta"),
        DomainSignal(frozenset({"reserva", "reservas", "reservation", "reservations", "booking", "bookings"}), 2.5, "reservas de vehículos"),
        DomainSignal(frozenset({"vehiculo", "vehiculos", "vehicle", "vehicles", "flota", "fleet"}), 2.1, "flota de vehículos"),
        DomainSignal(frozenset({"tarifa", "tarifas", "rental_rate", "diaria", "daily_rate", "kilometraje"}), 1.3, "tarifas y kilometraje"),
        DomainSignal(frozenset({"mantenimiento", "maintenance", "taller", "servicio"}), 1.9, "mantenimiento de flota"),
        DomainSignal(frozenset({"cliente", "clientes", "customer", "customers"}), 0.8, "clientes"),
    ],
    "retail": [
        DomainSignal(frozenset({"carrito", "carritos", "shopping_cart", "shopping_carts", "cart_items", "checkout"}), 2.2, "carritos electrónicos"),
        DomainSignal(frozenset({"devolucion", "devoluciones", "return", "returns", "refund", "refunds", "reembolso"}), 1.6, "devoluciones y reembolsos"),

        DomainSignal(frozenset({"producto", "productos", "product", "products", "item", "items", "articulo", "articulos", "sku", "catalogo", "catalog"}), 2.0, "catálogo de productos"),
        DomainSignal(frozenset({"venta", "ventas", "sale", "sales", "order", "orders", "pedido", "pedidos", "factura", "facturas", "invoice", "invoices"}), 2.0, "ventas/pedidos"),
        DomainSignal(frozenset({"id_pedido", "pedido_id", "order_id", "fecha_pedido",
                                "order_date", "estado_pedido", "order_status",
                                "numero_pedido", "order_number", "orden_compra"}), 3.0, "operación de pedidos"),
        DomainSignal(frozenset({"total_pedido", "order_total", "monto_pedido",
                                "importe_pedido", "total_orden", "order_amount"}), 2.4, "importes de pedidos"),
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
        DomainSignal(frozenset({"paciente", "pacientes", "patient", "patients", "expediente", "expedientes", "historia_clinica", "medical_record", "medical_records"}), 2.5, "pacientes"),
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
        DomainSignal(frozenset({"parada", "paradas", "stop", "stops", "horario", "schedule", "schedules", "terminal", "estacion"}), 1.3, "operación logística"),
    ],
    "hospitality": [
        DomainSignal(frozenset({"hotel", "hotels", "habitacion", "habitaciones", "room", "rooms", "alojamiento", "lodging"}), 2.2, "habitaciones/alojamiento"),
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
        DomainSignal(frozenset({"prestamo", "prestamos", "loan", "loans", "credito_bancario", "amortizacion", "loan_payment"}), 2.6, "préstamos"),
        DomainSignal(frozenset({"tarjeta_bancaria", "tarjetas_bancarias", "credit_card", "bank_card", "card_transactions"}), 2.0, "tarjetas bancarias"),
        DomainSignal(frozenset({"sucursal_bancaria", "bank_branch", "iban", "cuenta_bancaria", "bank_account"}), 2.2, "operación bancaria"),

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
        DomainSignal(frozenset({"empleado", "empleados", "employee", "employees", "staff", "personal", "colaborador", "colaboradores", "worker", "workers"}), 2.2, "empleados"),
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
        # Do not dilute confidence in existing retail schemas merely because
        # optional order aliases were added. Keep the original five-signal
        # reference range; the new signals supplement evidence.
        max_score = sum(signal.weight for signal in (
            signals[2:7] if domain == "retail" else
            signals[3:] if domain == "finance_accounting" else signals
        )) + 1.75
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

        # A dataset containing only a shipment register is a valid logistics
        # source, even if it does not have all optional carriers/warehouses.
        # Require explicit table/column evidence to avoid using a lone
        # "delivery date" in unrelated business sectors as proof.
        if domain == "logistics" and score >= 30 and len(evidence) >= 2:
            has_shipping_entity = any(
                tokenize(table_name) & {
                    "envio", "envios", "entrega", "entregas",
                    "shipment", "shipments", "delivery", "deliveries",
                    "despacho", "despachos", "dispatch"
                } for table_name in schema.tables
            )
            if not has_shipping_entity:
                has_shipping_entity = any(
                    len({"id_envio", "fecha_envio", "estado_envio",
                         "shipment_id", "shipping_date", "shipment_status"}
                        & {normalize_name(col.name) for col in table.columns}) >= 2
                    for table in schema.tables.values()
                )
            if has_shipping_entity:
                score = max(score, 42.0)

        if domain == "retail":
            retail_context = any(
                label in {item["signal"] for item in evidence}
                for label in ("catálogo de productos", "inventario",
                              "atributos de catálogo", "clientes")
            )
            if not retail_context:
                # A standalone pedido/order table can still be recognized,
                # but it does not prove a particular type of commerce.
                score = min(score, 59.0)

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
