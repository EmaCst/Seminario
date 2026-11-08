import re
import unicodedata
from dataclasses import dataclass, field

from app.analysis.business_domain_detector import detect_business_domains
from app.database.inspector import inspect_database
from app.database.source_cache import source_cached
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
    "insurance": {
        "policies": RoleProfile(frozenset({"polizas","poliza","policies","policy"}), frozenset({"poliza","cobertura","prima","vigencia"}), (), {"id": ("id_poliza", "policy_id", "id"), "date": ("fecha_emision", "issue_date", "fecha"), "end_date": ("fecha_vencimiento", "expiry_date"), "status": ("estado_poliza", "policy_status", "estado"), "amount": ("prima", "prima_anual", "premium", "amount"), "customer_id": ("id_asegurado", "insured_id", "id_cliente")}),
        "claims": RoleProfile(frozenset({"siniestros","siniestro","claims","claim","reclamaciones","reclamacion"}), frozenset({"siniestro","reclamacion","indemnizacion","fecha","estado"}), (), {"id": ("id_siniestro", "claim_id", "id"), "date": ("fecha_siniestro", "claim_date", "fecha"), "status": ("estado_siniestro", "claim_status", "estado"), "amount": ("monto_indemnizado", "paid_amount", "monto_reclamado", "claim_amount"), "policy_id": ("id_poliza", "policy_id")}),
        "coverages": RoleProfile(frozenset({"coberturas","cobertura","coverages","coverage"}), frozenset({"cobertura","deducible","limite","riesgo"}), (), {"id": ("id_cobertura", "coverage_id", "id"), "name": ("nombre_cobertura", "nombre", "name"), "amount": ("limite_cobertura", "coverage_limit"), "policy_id": ("id_poliza", "policy_id")}),
        "insured": RoleProfile(frozenset({"asegurados","asegurado","insureds","insured","clientes_seguros"}), frozenset({"asegurado","nombre","documento","telefono"}), (), {"id": ("id_asegurado", "insured_id", "id_cliente", "id"), "name": ("nombre_completo", "nombre", "name")}),
        "payments": RoleProfile(frozenset({"pagos_primas","pago_prima","insurance_payments","premium_payments"}), frozenset({"prima","pago","monto","fecha"}), (), {"id": ("id_pago", "payment_id", "id"), "date": ("fecha_pago", "payment_date", "fecha"), "amount": ("monto_pagado", "amount", "monto"), "status": ("estado_pago", "status"), "policy_id": ("id_poliza", "policy_id")}),
    },
    "pharmacy": {
        "medicines": RoleProfile(frozenset({"medicamentos","medicamento","farmacos","farmaco","medicines","medicine","drugs"}), frozenset({"medicamento","principio","presentacion","dosis","precio"}), (), {"id": ("id_medicamento", "medicine_id", "drug_id", "id"), "name": ("nombre_medicamento", "nombre", "name"), "price": ("precio_venta", "sale_price", "precio"), "status": ("estado", "status")}),
        "batches": RoleProfile(frozenset({"lotes_medicamentos","lotes","lotes_farmacia","medicine_batches","drug_batches"}), frozenset({"lote","caducidad","vencimiento","cantidad","medicamento"}), (), {"id": ("id_lote", "batch_id", "id"), "date": ("fecha_caducidad", "fecha_vencimiento", "expiration_date", "expiry_date"), "quantity": ("cantidad_disponible", "cantidad", "quantity", "stock"), "medicine_id": ("id_medicamento", "medicine_id"), "status": ("estado", "status")}),
        "dispensations": RoleProfile(frozenset({"dispensaciones","dispensacion","ventas_farmacia","dispensing","dispensations"}), frozenset({"dispensacion","receta","medicamento","cantidad","fecha"}), (), {"id": ("id_dispensacion", "dispensation_id", "id"), "date": ("fecha_dispensacion", "dispensed_at", "fecha"), "quantity": ("cantidad", "quantity"), "total": ("total_venta", "total", "importe_total"), "status": ("estado", "status"), "medicine_id": ("id_medicamento", "medicine_id")}),
        "prescriptions": RoleProfile(frozenset({"recetas_medicas","recetas","prescripciones","prescriptions","prescription"}), frozenset({"receta","prescriptor","medicamento","paciente"}), (), {"id": ("id_receta", "prescription_id", "id"), "date": ("fecha_receta", "prescribed_at", "fecha"), "status": ("estado", "status")}),
        "suppliers": RoleProfile(frozenset({"proveedores_farmacia","proveedores","suppliers","pharmacy_suppliers"}), frozenset({"proveedor","laboratorio","contacto"}), (), {"id": ("id_proveedor", "supplier_id", "id"), "name": ("nombre", "name", "laboratorio")}),
    },
    "saas": {
        "subscriptions": RoleProfile(frozenset({"suscripciones","suscripcion","subscriptions","subscription"}), frozenset({"suscripcion","plan","estado","inicio","renovacion"}), (), {"id": ("id_suscripcion", "subscription_id", "id"), "date": ("fecha_inicio", "start_date", "created_at"), "end_date": ("fecha_renovacion", "next_billing_date", "fecha_fin"), "status": ("estado_suscripcion", "subscription_status", "estado"), "amount": ("monto_recurrente", "recurring_amount", "monthly_amount", "mrr", "amount"), "organization_id": ("id_organizacion", "organization_id")}),
        "plans": RoleProfile(frozenset({"planes_saas","planes","pricing_plans","subscription_plans","plans"}), frozenset({"plan","precio","periodo","limite"}), (), {"id": ("id_plan", "plan_id", "id"), "name": ("nombre_plan", "nombre", "name"), "price": ("precio_mensual", "monthly_price", "price"), "status": ("estado", "status")}),
        "organizations": RoleProfile(frozenset({"organizaciones","organizacion","organizations","organization","workspaces"}), frozenset({"organizacion","empresa","workspace","dominio"}), (), {"id": ("id_organizacion", "organization_id", "id"), "name": ("nombre", "name", "razon_social")}),
        "support_tickets": RoleProfile(frozenset({"tickets_soporte","support_tickets","tickets","incidencias_software"}), frozenset({"ticket","soporte","prioridad","resolucion"}), (), {"id": ("id_ticket", "ticket_id", "id"), "date": ("fecha_apertura", "opened_at", "created_at", "fecha"), "status": ("estado_ticket", "ticket_status", "estado"), "end_date": ("fecha_resolucion", "resolved_at")}),
        "invoices": RoleProfile(frozenset({"facturacion_recurrente","facturas_saas","subscription_invoices","invoices"}), frozenset({"factura","monto","suscripcion","periodo"}), (), {"id": ("id_factura", "invoice_id", "id"), "date": ("fecha_factura", "invoice_date", "fecha"), "total": ("monto_facturado", "total", "amount"), "status": ("estado", "status")}),
    },
    "events": {
        "events": RoleProfile(frozenset({"eventos","evento","events","event","conciertos","festivales"}), frozenset({"evento","fecha","ubicacion","aforo","organizador"}), (), {"id": ("id_evento", "event_id", "id"), "name": ("nombre_evento", "nombre", "event_name", "name"), "date": ("fecha_evento", "event_date", "fecha"), "status": ("estado_evento", "event_status", "estado"), "quantity": ("aforo", "capacity")}),
        "tickets": RoleProfile(frozenset({"entradas_evento","boletos_evento","entradas","event_tickets","tickets_event"}), frozenset({"entrada","boleto","evento","asiento","precio"}), (), {"id": ("id_entrada", "ticket_id", "id"), "date": ("fecha_compra", "purchase_date", "fecha"), "total": ("total_pagado", "precio_pagado", "paid_amount", "total"), "status": ("estado_entrada", "ticket_status", "estado"), "event_id": ("id_evento", "event_id")}),
        "attendees": RoleProfile(frozenset({"asistentes","asistente","attendees","attendee","inscritos_evento"}), frozenset({"asistente","correo","nombre","registro"}), (), {"id": ("id_asistente", "attendee_id", "id"), "name": ("nombre_completo", "nombre", "name"), "date": ("fecha_registro", "registration_date")}),
        "venues": RoleProfile(frozenset({"recintos","recinto","sedes_evento","event_venues","venues","venue"}), frozenset({"recinto","direccion","capacidad","aforo"}), (), {"id": ("id_recinto", "venue_id", "id"), "name": ("nombre_recinto", "nombre", "name"), "quantity": ("aforo", "capacidad", "capacity")}),
        "reservations": RoleProfile(frozenset({"reservas_evento","event_reservations","event_bookings"}), frozenset({"reserva","asiento","evento","fecha"}), (), {"id": ("id_reserva", "reservation_id", "id"), "date": ("fecha_reserva", "reservation_date", "fecha"), "status": ("estado_reserva", "status"), "event_id": ("id_evento", "event_id")}),
    },
    "fitness": {
        "members": RoleProfile(frozenset({"socios","socio","miembros","miembro","gym_members","members"}), frozenset({"socio","miembro","nombre","telefono"}), (), {"id": ("id_socio", "member_id", "id_miembro", "id"), "name": ("nombre_completo", "nombre", "name"), "date": ("fecha_registro", "joined_at", "fecha")}),
        "memberships": RoleProfile(frozenset({"membresias","membresia","memberships","membership"}), frozenset({"membresia","socio","plan","renovacion","fecha"}), (), {"id": ("id_membresia", "membership_id", "id"), "date": ("fecha_inicio", "start_date", "fecha"), "end_date": ("fecha_vencimiento", "end_date"), "status": ("estado_membresia", "membership_status", "estado"), "amount": ("cuota_pagada", "monto_pagado", "fee_paid", "amount"), "member_id": ("id_socio", "member_id")}),
        "trainers": RoleProfile(frozenset({"entrenadores","entrenador","trainers","trainer"}), frozenset({"entrenador","especialidad","nombre"}), (), {"id": ("id_entrenador", "trainer_id", "id"), "name": ("nombre", "name"), "status": ("estado", "status")}),
        "classes": RoleProfile(frozenset({"clases_fitness","clases_gimnasio","gym_classes","fitness_classes"}), frozenset({"clase","entrenador","cupo","fecha","horario"}), (), {"id": ("id_clase", "class_id", "id"), "name": ("nombre_clase", "nombre", "name"), "date": ("fecha_clase", "class_date", "fecha"), "quantity": ("cupo", "capacidad", "capacity"), "status": ("estado", "status")}),
        "attendance": RoleProfile(frozenset({"asistencia_gimnasio","control_acceso","gym_attendance","check_ins"}), frozenset({"asistencia","entrada","socio","fecha"}), (), {"id": ("id_asistencia", "attendance_id", "id"), "date": ("fecha_entrada", "check_in", "fecha"), "member_id": ("id_socio", "member_id")}),
    },
    "real_estate": {
        "properties": RoleProfile(
            frozenset({"inmuebles", "inmueble", "propiedades", "propiedad", "properties",
                        "property", "unidades_inmobiliarias", "real_estate_properties"}),
            frozenset({"inmueble", "propiedad", "direccion", "superficie", "area",
                        "precio", "tipo", "disponibilidad"}),
            (), {"id": ("id_inmueble", "inmueble_id", "property_id", "id_propiedad", "id"),
                 "name": ("direccion", "address", "nombre", "name", "codigo"),
                 "status": ("estado", "disponibilidad", "status", "property_status"),
                 "price": ("precio_venta", "valor_propiedad", "precio", "asking_price"),
                 "category": ("tipo_inmueble", "property_type", "tipo")}),
        "leases": RoleProfile(
            frozenset({"arrendamientos", "arrendamiento", "arriendos", "arriendo",
                        "contratos_alquiler", "leases", "lease", "tenancies"}),
            frozenset({"arrendamiento", "alquiler", "canon", "renta_mensual",
                        "inquilino", "contrato", "inicio", "vencimiento"}),
            (), {"id": ("id_arrendamiento", "lease_id", "id_contrato", "id"),
                 "date": ("fecha_inicio", "fecha_contrato", "start_date", "lease_start", "fecha"),
                 "end_date": ("fecha_fin", "fecha_vencimiento", "end_date", "lease_end"),
                 "status": ("estado_contrato", "lease_status", "estado", "status"),
                 "total": ("total_cobrado", "importe_total", "total", "total_renta"),
                 "amount": ("renta_mensual", "canon_mensual", "monthly_rent", "monto"),
                 "property_id": ("id_inmueble", "property_id", "id_propiedad"),
                 "tenant_id": ("id_inquilino", "tenant_id", "id_arrendatario")}),
        "tenants": RoleProfile(
            frozenset({"inquilinos", "inquilino", "arrendatarios", "arrendatario",
                        "tenants", "tenant"}),
            frozenset({"inquilino", "tenant", "nombre", "contacto", "telefono"}),
            (), {"id": ("id_inquilino", "tenant_id", "id_arrendatario", "id"),
                 "name": ("nombre_completo", "nombre", "name"),
                 "date": ("fecha_registro", "created_at", "registration_date")}),
        "agents": RoleProfile(
            frozenset({"agentes_inmobiliarios", "agente_inmobiliario", "corredores",
                        "agentes", "realtors", "real_estate_agents", "brokers"}),
            frozenset({"agente", "corredor", "broker", "comision", "inmueble"}),
            (), {"id": ("id_agente", "agent_id", "broker_id", "id"),
                 "name": ("nombre", "name", "agente", "broker")}),
    },
    "construction": {
        "projects": RoleProfile(
            frozenset({"obras", "obra", "proyectos_construccion", "proyectos_obra",
                        "construction_projects", "construction_sites", "construcciones"}),
            frozenset({"obra", "construccion", "presupuesto", "avance",
                        "fecha_inicio", "fecha_fin", "contratista"}),
            (), {"id": ("id_obra", "obra_id", "construction_project_id", "id"),
                 "name": ("nombre_obra", "nombre_proyecto", "nombre", "project_name"),
                 "date": ("fecha_inicio", "start_date", "fecha"),
                 "end_date": ("fecha_fin", "end_date", "fecha_entrega"),
                 "status": ("estado_obra", "project_status", "estado", "status"),
                 "amount": ("costo_real", "actual_cost", "gasto_obra"),
                 "value": ("porcentaje_avance", "avance_fisico", "progress_pct"),
                 "total": ("total_ejecutado", "total", "costo_total")}),
        "budgets": RoleProfile(
            frozenset({"presupuestos_obra", "presupuesto_obra", "presupuestos_construccion",
                        "construction_budgets", "cost_estimates", "estimaciones_obra"}),
            frozenset({"presupuesto", "obra", "estimado", "partida", "costo"}),
            (), {"id": ("id_presupuesto", "budget_id", "id"),
                 "date": ("fecha", "fecha_presupuesto", "created_at"),
                 "amount": ("monto_presupuestado", "presupuesto", "budget", "estimated_cost"),
                 "total": ("total_presupuesto", "total"),
                 "status": ("estado", "status")}),
        "contractors": RoleProfile(
            frozenset({"contratistas", "contratista", "subcontratistas", "subcontratista",
                        "contractors", "contractor", "subcontractors"}),
            frozenset({"contratista", "empresa", "especialidad", "contrato"}),
            (), {"id": ("id_contratista", "contractor_id", "id"),
                 "name": ("razon_social", "empresa", "nombre", "name"),
                 "status": ("estado", "status")}),
        "materials": RoleProfile(
            frozenset({"materiales_obra", "insumos_obra", "material_construccion",
                        "building_materials", "construction_materials"}),
            frozenset({"material", "cantidad", "costo", "unidad", "obra"}),
            (), {"id": ("id_material", "material_id", "id"),
                 "name": ("nombre", "material", "name"),
                 "quantity": ("cantidad_consumida", "cantidad", "quantity"),
                 "amount": ("costo_total", "total_costo", "total"),
                 "date": ("fecha_consumo", "fecha", "date")}),
    },
    "agriculture": {
        "fields": RoleProfile(
            frozenset({"parcelas", "parcela", "fincas", "finca", "lotes_agricolas",
                        "fields", "farmland", "farms"}),
            frozenset({"parcela", "hectareas", "superficie", "finca", "ubicacion"}),
            (), {"id": ("id_parcela", "field_id", "farm_id", "id"),
                 "name": ("nombre", "name", "ubicacion", "location"),
                 "quantity": ("hectareas", "area_hectareas", "area")}),
        "crops": RoleProfile(
            frozenset({"cultivos", "cultivo", "siembras", "siembra",
                        "crops", "crop", "plantaciones", "plantations"}),
            frozenset({"cultivo", "siembra", "semilla", "parcela", "especie"}),
            (), {"id": ("id_cultivo", "crop_id", "id_siembra", "id"),
                 "name": ("tipo_cultivo", "nombre", "crop_name", "name"),
                 "date": ("fecha_siembra", "planting_date", "fecha"),
                 "status": ("estado", "status"),
                 "quantity": ("area_sembrada", "hectareas", "cantidad")}),
        "harvests": RoleProfile(
            frozenset({"cosechas", "cosecha", "recolecciones", "harvests", "harvest"}),
            frozenset({"cosecha", "recoleccion", "toneladas", "rendimiento",
                        "kilogramos", "fecha", "cultivo"}),
            (), {"id": ("id_cosecha", "harvest_id", "id"),
                 "date": ("fecha_cosecha", "harvest_date", "fecha"),
                 "quantity": ("kilos_cosechados", "kilogramos", "toneladas",
                              "cantidad_cosechada", "yield_kg", "quantity"),
                 "status": ("estado", "status"),
                 "total": ("valor_cosecha", "valor_total", "total")}),
        "livestock": RoleProfile(
            frozenset({"ganado", "ganaderia", "animales_granja", "rebanos",
                        "livestock", "herds", "farm_animals"}),
            frozenset({"ganado", "animal", "raza", "peso", "especie", "edad"}),
            (), {"id": ("id_animal", "animal_id", "livestock_id", "id"),
                 "name": ("especie", "raza", "nombre", "name"),
                 "status": ("estado", "status"),
                 "quantity": ("peso", "weight", "cantidad")}),
    },
    "logistics": {
        "stock_movements": RoleProfile(frozenset({"movimientos_inventario", "movimientos_almacen", "stock_movements", "inventory_movements"}), frozenset({"movimiento", "almacen", "cantidad", "fecha", "producto"}), (), {"id": ("id_movimiento", "movement_id", "id"), "date": ("fecha_movimiento", "movement_date", "fecha"), "quantity": ("cantidad", "quantity", "units"), "status": ("estado", "status"), "warehouse_id": ("id_almacen", "warehouse_id")}),
        "purchase_orders": RoleProfile(frozenset({"ordenes_compra", "orden_compra", "purchase_orders", "purchase_order"}), frozenset({"compra", "proveedor", "recepcion", "estado", "monto"}), (), {"id": ("id_orden_compra", "purchase_order_id", "id"), "date": ("fecha_orden", "order_date", "fecha"), "total": ("total_compra", "purchase_total", "total"), "status": ("estado_orden", "order_status", "estado")}),
        "transfers": RoleProfile(frozenset({"transferencias_almacen", "transferencias_inventario", "warehouse_transfers", "stock_transfers"}), frozenset({"transferencia", "origen", "destino", "cantidad"}), (), {"id": ("id_transferencia", "transfer_id", "id"), "date": ("fecha_transferencia", "transfer_date", "fecha"), "quantity": ("cantidad", "quantity"), "status": ("estado_transferencia", "status")}),

        "shipments": RoleProfile(
            frozenset({"envios", "envio", "entregas", "entrega", "despachos", "despacho",
                        "shipments", "shipment", "shipping", "deliveries", "delivery",
                        "dispatch", "guia_envio", "guias_envio", "tracking_envios"}),
            frozenset({"envio", "entrega", "despacho", "guia", "tracking",
                        "destinatario", "direccion", "estado", "fecha", "pedido"}),
            (frozenset({"envio", "entrega", "despacho", "shipment", "shipping",
                        "delivery", "guia", "tracking"}),),
            {"id": ("id_envio", "envio_id", "shipment_id", "delivery_id", "id_entrega", "id"),
             "date": ("fecha_envio", "fecha_despacho", "shipping_date", "shipped_at",
                      "fecha_entrega", "delivery_date", "created_at", "fecha"),
             "end_date": ("fecha_entrega", "delivered_at", "delivered_date", "delivery_date"),
             "status": ("estado_envio", "shipment_status", "estado_entrega",
                        "delivery_status", "estado", "status"),
             "total": ("costo_envio", "shipping_cost", "tarifa_envio", "shipping_fee",
                       "valor_envio", "total", "amount"),
             "quantity": ("cantidad_paquetes", "packages_count", "numero_bultos"),
             "order_id": ("id_pedido", "pedido_id", "order_id"),
             "carrier_id": ("id_transportista", "carrier_id"),
             "tracking": ("numero_guia", "tracking_number", "codigo_guia", "guia", "tracking")}),
        "orders": RoleProfile(
            frozenset({"pedidos", "pedido", "ordenes", "ordenes_pedido",
                        "ordenes_compra", "orders", "order", "sales_orders"}),
            frozenset({"pedido", "order", "cliente", "customer", "fecha", "estado", "total"}),
            (frozenset({"pedido", "order"}),),
            {"id": ("id_pedido", "pedido_id", "order_id", "id"),
             "date": ("fecha_pedido", "order_date", "created_at", "fecha"),
             "status": ("estado_pedido", "order_status", "estado", "status"),
             "total": ("total_pedido", "order_total", "monto_pedido", "total"),
             "customer_id": ("id_cliente", "cliente_id", "customer_id")}),
        "packages": RoleProfile(
            frozenset({"paquetes", "paquete", "bultos", "bulto", "parcels",
                        "parcel", "packages", "package"}),
            frozenset({"paquete", "bulto", "peso", "weight", "volumen", "volume"}),
            (frozenset({"paquete", "bulto", "parcel", "package", "peso", "weight"}),),
            {"id": ("id_paquete", "package_id", "parcel_id", "id"),
             "status": ("estado_paquete", "package_status", "estado", "status"),
             "quantity": ("cantidad", "quantity", "bultos"),
             "shipment_id": ("id_envio", "envio_id", "shipment_id")}),
        "carriers": RoleProfile(
            frozenset({"transportistas", "transportista", "mensajeros", "mensajero",
                        "repartidores", "repartidor", "couriers", "courier",
                        "carriers", "carrier"}),
            frozenset({"transportista", "repartidor", "mensajero", "carrier",
                        "courier", "empresa", "nombre"}),
            (frozenset({"transportista", "repartidor", "mensajero", "carrier", "courier"}),),
            {"id": ("id_transportista", "carrier_id", "courier_id", "id"),
             "name": ("nombre", "name", "empresa", "carrier_name"),
             "status": ("estado", "status")}),
        "warehouses": RoleProfile(
            frozenset({"bodegas", "bodega", "almacenes", "almacen",
                        "warehouses", "warehouse", "centros_distribucion"}),
            frozenset({"bodega", "almacen", "warehouse", "ubicacion", "location"}),
            (frozenset({"bodega", "almacen", "warehouse"}),),
            {"id": ("id_bodega", "warehouse_id", "id_almacen", "id"),
             "name": ("nombre", "name", "ubicacion", "location")}),
    },
    "vehicle_rental": {
        "rentals": RoleProfile(
            frozenset({"reservas_y_rentas", "reservas_rentas", "rentas", "renta", "alquileres", "alquiler", "rentals", "rental_agreements", "reservas_vehiculos", "car_rentals"}),
            frozenset({"reserva", "renta", "alquiler", "inicio", "fin", "tarifa", "subtotal", "seguro", "descuento", "total"}),
            (frozenset({"reserva", "renta", "rental", "alquiler"}),),
            {"id": ("id_reserva", "id_renta", "rental_id", "reservation_id", "id"),
             "date": ("fecha_inicio", "fecha_reserva", "rental_date", "start_date", "fecha"),
             "end_date": ("fecha_fin", "end_date", "fecha_devolucion"),
             "total": ("total_general", "total", "importe_total", "monto_total", "total_renta", "amount"),
             "status": ("estado_reserva", "estado_renta", "rental_status", "status", "estado"),
             "quantity": ("dias_renta", "dias_alquiler", "rental_days", "days"),
             "price": ("tarifa_dia", "tarifa_diaria", "daily_rate", "precio_dia"),
             "customer_id": ("id_cliente", "cliente_id", "customer_id"),
             "vehicle_id": ("id_vehiculo", "vehiculo_id", "vehicle_id")}),
        "vehicles": RoleProfile(
            frozenset({"flota_vehiculos", "flota", "vehiculos", "vehiculo", "vehicles", "fleet", "cars", "autos"}),
            frozenset({"placa", "marca", "modelo", "kilometraje", "combustible", "categoria", "tarifa"}),
            (frozenset({"vehiculo", "vehiculos", "placa", "modelo"}),),
            {"id": ("id_vehiculo", "vehiculo_id", "vehicle_id", "id"),
             "name": ("placa", "modelo", "nombre", "name"),
             "status": ("estado", "status", "disponibilidad"),
             "price": ("tarifa_diaria", "tarifa", "daily_rate"),
             "category": ("categoria", "category", "tipo_vehiculo")}),
        "customers": RoleProfile(
            frozenset({"clientes", "cliente", "customers", "customer", "clients", "client"}),
            frozenset({"nombre", "apellido", "correo", "telefono", "licencia", "documento"}),
            (frozenset({"cliente", "clientes", "nombre", "correo"}),),
            {"id": ("id_cliente", "cliente_id", "customer_id", "id"),
             "name": ("nombre_completo", "nombre", "name", "full_name"),
             "date": ("fecha_registro", "registration_date", "created_at")}),
        "maintenance": RoleProfile(
            frozenset({"mantenimiento", "mantenimientos", "maintenance", "vehicle_maintenance", "servicios_flota"}),
            frozenset({"mantenimiento", "servicio", "taller", "costo", "ingreso", "entrega"}),
            (frozenset({"mantenimiento", "servicio", "taller"}),),
            {"id": ("id_mantenimiento", "maintenance_id", "id"),
             "date": ("fecha_ingreso", "service_date", "fecha_servicio", "fecha"),
             "end_date": ("fecha_entrega", "end_date"),
             "status": ("estado", "status", "estado_servicio"),
             "amount": ("costo", "costo_total", "total_costo", "cost", "amount"),
             "vehicle_id": ("id_vehiculo", "vehiculo_id", "vehicle_id")}),
        "payments": RoleProfile(
            frozenset({"pagos", "pago", "payments", "payment", "cobros"}),
            frozenset({"monto", "metodo", "pago", "fecha"}),
            (frozenset({"pago", "monto", "amount"}),),
            {"id": COMMON_ID, "amount": COMMON_TOTAL,
             "date": COMMON_DATE, "status": COMMON_STATUS}),
    },
    "retail": {
        "carts": RoleProfile(frozenset({"carritos", "carrito", "shopping_carts", "carts"}), frozenset({"carrito", "usuario", "fecha", "estado"}), (), {"id": ("id_carrito", "cart_id", "id"), "date": ("fecha_creacion", "created_at", "fecha"), "status": ("estado_carrito", "cart_status", "estado"), "total": ("total_carrito", "cart_total", "total")}),
        "returns": RoleProfile(frozenset({"devoluciones", "devolucion", "returns", "refunds", "reembolsos"}), frozenset({"devolucion", "reembolso", "pedido", "motivo", "monto"}), (), {"id": ("id_devolucion", "return_id", "refund_id", "id"), "date": ("fecha_devolucion", "returned_at", "fecha"), "status": ("estado_devolucion", "return_status", "estado"), "amount": ("monto_reembolsado", "refund_amount", "amount"), "order_id": ("id_pedido", "order_id")}),

        "sales": RoleProfile(
            frozenset({"venta", "ventas", "sale", "sales", "factura", "facturas", "invoice", "invoices"}),
            frozenset({"total", "subtotal", "fecha", "date", "cliente", "customer", "payment", "pago"}),
            (frozenset({"total", "amount", "monto", "subtotal"}),),
            {"id": COMMON_ID, "date": COMMON_DATE, "total": COMMON_TOTAL, "status": COMMON_STATUS},
        ),
        "orders": RoleProfile(
            frozenset({"pedidos", "pedido", "ordenes_venta", "ordenes_compra",
                        "ordenes_pedido", "ordenes", "orders", "order",
                        "purchase_orders", "sales_orders"}),
            frozenset({"pedido", "order", "cliente", "customer", "fecha",
                        "date", "estado", "status", "total", "subtotal"}),
            (frozenset({"pedido", "order"}),),
            {"id": ("id_pedido", "pedido_id", "order_id", "numero_pedido", "id"),
             "date": ("fecha_pedido", "order_date", "fecha_orden", "created_at", "fecha"),
             "status": ("estado_pedido", "order_status", "estado_orden", "estado", "status"),
             "total": ("total_pedido", "order_total", "monto_pedido",
                       "total_orden", "total", "subtotal"),
             "customer_id": ("id_cliente", "cliente_id", "customer_id"),
             "quantity": ("cantidad", "quantity", "items_count")}),
        "sales_details": RoleProfile(
            frozenset({"detalle_ventas", "detalleventa", "detalle_pedidos", "detalles_pedido", "detalle_orden", "order_items", "sales_detail", "sale_detail", "order_detail", "order_details", "invoice_detail", "invoice_details", "line_items", "lines"}),
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
        "loans": RoleProfile(frozenset({"prestamos", "prestamo", "loans", "loan", "creditos_bancarios"}), frozenset({"prestamo", "interes", "capital", "cuota", "vencimiento"}), (), {"id": ("id_prestamo", "loan_id", "id"), "date": ("fecha_desembolso", "disbursement_date", "fecha"), "amount": ("monto_desembolsado", "principal_amount", "amount"), "status": ("estado_prestamo", "loan_status", "estado")}),
        "cards": RoleProfile(frozenset({"tarjetas_bancarias", "tarjetas_credito", "bank_cards", "credit_cards"}), frozenset({"tarjeta", "limite", "vencimiento", "cuenta"}), (), {"id": ("id_tarjeta", "card_id", "id"), "status": ("estado_tarjeta", "card_status", "estado"), "amount": ("saldo_pendiente", "outstanding_balance")}),
        "branches": RoleProfile(frozenset({"sucursales_bancarias", "sucursales", "bank_branches"}), frozenset({"sucursal", "direccion", "banco"}), (), {"id": ("id_sucursal", "branch_id", "id"), "name": ("nombre", "name", "sucursal")}),

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
    # Newly added roles must carry sector-specific evidence; shared fields
    # such as 'fecha', 'estado', 'nombre' never prove an entity type.
    guarded_roles = {
        "insurance", "pharmacy", "saas", "events", "fitness"
    }
    guarded_extensions = {
        ("retail", "carts"), ("retail", "returns"),
        ("logistics", "stock_movements"), ("logistics", "purchase_orders"),
        ("logistics", "transfers"),
        ("finance_accounting", "loans"), ("finance_accounting", "cards"),
        ("finance_accounting", "branches"),
    }
    guarded = any(
        role is item for domain in guarded_roles
        for item in ROLE_PROFILES[domain].values()
    ) or any(
        role is ROLE_PROFILES[domain][role_name]
        for domain, role_name in guarded_extensions
    )
    if guarded and not (tokens(table_name) & role.table_terms):
        specific_columns = role.column_terms - {
            "fecha", "date", "estado", "status", "nombre", "name",
            "precio", "monto", "total", "cantidad", "cliente", "id",
        }
        if not (specific_columns & table_column_tokens(table)):
            return 0.0, []
    # Do not confuse an order record with an actual sale just because both
    # have a date, status and monetary total. They are different business
    # events and must remain separate roles.
    if role is ROLE_PROFILES["retail"]["sales"] and (
        table_tokens & {"pedido", "pedidos", "order", "orders", "orden", "ordenes"}
    ) and not (
        table_tokens & {"venta", "ventas", "sale", "sales", "factura",
                        "facturas", "invoice", "invoices"}
    ):
        return 0.0, []
    if role is ROLE_PROFILES["retail"]["orders"] and (
        table_tokens & {"venta", "ventas", "sale", "sales", "factura",
                        "facturas", "invoice", "invoices"}
    ) and not (
        table_tokens & {"pedido", "pedidos", "order", "orders", "orden", "ordenes"}
    ):
        return 0.0, []
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

    # Avoid matching generic tokens such as "id" inside foreign keys or
    # "fecha" inside unrelated date columns. Prefer unique, meaningful matches.
    for alias in normalized_aliases:
        if len(alias) < 4 or alias in {"id", "name", "date", "code", "key"}:
            continue
        candidates = [column.name for column in table.columns
                      if alias in tokens(column.name)]
        if len(candidates) == 1:
            return candidates[0]

    return None


def map_role_columns(table: TableSchema, role: RoleProfile) -> dict:
    mapped: dict[str, str] = {}
    for semantic_name, aliases in role.preferred_columns.items():
        column = find_column(table, aliases)
        if column:
            mapped[semantic_name] = column
    if "date" in role.preferred_columns and "date" not in mapped:
        date_column = find_column(table, COMMON_DATE)
        if date_column:
            mapped["date"] = date_column
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
        # Expose actual tables with truthful, generic labels rather than
        # inventing a business sector or returning an empty dashboard.
        # Keep ambiguous/unsupported domains explicitly unclassified.
        generic_profile = RoleProfile(
            frozenset(), frozenset(), (),
            {"id": COMMON_ID, "date": COMMON_DATE + ("fecha_pedido", "fecha_envio", "fecha_entrega"),
             "status": COMMON_STATUS, "total": COMMON_TOTAL,
             "amount": ("costo", "cost", "monto", "amount"),
             "quantity": COMMON_QUANTITY},
        )
        entities = {}
        for table_name in sorted(schema.tables)[:12]:
            role = "tabla_" + normalize_name(table_name)
            table = schema.tables[table_name]
            entities[role] = {
                "table": table_name, "confidence": "low", "ambiguous": False,
                "score": 0, "columns": map_role_columns(table, generic_profile),
                "evidence": ["tabla real sin clasificación sectorial"],
                "alternatives": [],
            }
        return {
            "domain": "general",
            "domain_confidence": "insufficient",
            "ambiguous_domain": True,
            "entities": entities,
            "uncertain_entities": {},
            "relations": map_relations(schema, entities),
            "unmapped_tables": sorted(set(schema.tables) -
                                      {e["table"] for e in entities.values()}),
        }

    # Existing, positively identified domains keep their original role mapping.

    entities: dict[str, dict] = {}

    used_tables: set[str] = set()
    uncertain_entities: dict[str, dict] = {}
    for role_name, role_profile in ROLE_PROFILES[domain].items():
        match = find_best_table_for_role(schema, role_profile)
        if not match:
            continue
        # Do not assign the same physical table to unrelated business roles.
        # Ambiguous matches remain available as alternatives, not asserted facts.
        if match["table"] in used_tables or (match["ambiguous"] and match["confidence"] == "low"):
            uncertain_entities[role_name] = {
                **match,
                "reason": "tabla ya asociada a otro rol" if match["table"] in used_tables else "coincidencia de baja confianza",
            }
            continue

        used_tables.add(match["table"])
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
        "uncertain_entities": uncertain_entities,
        "relations": map_relations(schema, entities),
        "unmapped_tables": sorted(set(schema.tables.keys()) - mapped_tables),
    }


@source_cached(seconds=120)
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
