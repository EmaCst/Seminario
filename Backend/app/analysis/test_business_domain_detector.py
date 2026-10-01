from app.analysis.business_domain_detector import detect_business_domains
from app.database.schema import (
    ColumnSchema,
    DatabaseSchema,
    RelationshipSchema,
    TableSchema,
)


def table(name: str, *columns: str) -> TableSchema:
    return TableSchema(
        name=name,
        columns=[
            ColumnSchema(name=column, type="varchar", nullable=True)
            for column in columns
        ],
        primary_key=["id"] if "id" in columns else [],
    )


def education_schema() -> DatabaseSchema:
    return DatabaseSchema(
        database="ColegioDemo",
        tables={
            "tbl_personas_alumno": table("tbl_personas_alumno", "id", "nombre"),
            "catalogo_materias": table("catalogo_materias", "id", "nombre_materia"),
            "registro_matricula": table("registro_matricula", "id", "alumno_id", "materia_id"),
            "evaluaciones": table("evaluaciones", "id", "alumno_id", "calificacion"),
            "personal_docente": table("personal_docente", "id", "nombre_profesor"),
        },
        relationships=[
            RelationshipSchema("registro_matricula", "alumno_id", "tbl_personas_alumno", "id"),
            RelationshipSchema("registro_matricula", "materia_id", "catalogo_materias", "id"),
            RelationshipSchema("evaluaciones", "alumno_id", "tbl_personas_alumno", "id"),
        ],
    )


def healthcare_schema() -> DatabaseSchema:
    return DatabaseSchema(
        database="ClinicaDemo",
        tables={
            "personas": table("personas", "id", "nombre_paciente"),
            "agenda": table("agenda", "id", "paciente_id", "medico_id", "fecha_cita"),
            "personal": table("personal", "id", "nombre_medico"),
            "historial": table("historial", "id", "paciente_id", "diagnostico", "tratamiento"),
            "farmacia": table("farmacia", "id", "medicamento", "dosis"),
        },
        relationships=[
            RelationshipSchema("agenda", "paciente_id", "personas", "id"),
            RelationshipSchema("agenda", "medico_id", "personal", "id"),
            RelationshipSchema("historial", "paciente_id", "personas", "id"),
        ],
    )


def transportation_schema() -> DatabaseSchema:
    return DatabaseSchema(
        database="MovilidadDemo",
        tables={
            "fleet_units": table("fleet_units", "id", "vehicle_plate"),
            "service_routes": table("service_routes", "id", "route_name"),
            "operations": table("operations", "id", "vehicle_id", "route_id", "trip_date"),
            "operators": table("operators", "id", "driver_name"),
            "travel_tickets": table("travel_tickets", "id", "trip_id", "passenger_name"),
        },
        relationships=[
            RelationshipSchema("operations", "vehicle_id", "fleet_units", "id"),
            RelationshipSchema("operations", "route_id", "service_routes", "id"),
            RelationshipSchema("travel_tickets", "trip_id", "operations", "id"),
        ],
    )


def retail_clothing_schema() -> DatabaseSchema:
    return DatabaseSchema(
        database="RopaDemo",
        tables={
            "catalog": table("catalog", "id", "sku", "brand", "size", "color", "price"),
            "orders": table("orders", "id", "customer_id", "total", "order_date"),
            "order_lines": table("order_lines", "id", "order_id", "item_id", "quantity"),
            "warehouse_balance": table("warehouse_balance", "id", "item_id", "stock"),
            "buyers": table("buyers", "id", "customer_name"),
        },
        relationships=[
            RelationshipSchema("order_lines", "order_id", "orders", "id"),
            RelationshipSchema("warehouse_balance", "item_id", "catalog", "id"),
            RelationshipSchema("orders", "customer_id", "buyers", "id"),
        ],
    )


def main() -> None:
    scenarios = [
        ("ESCUELA", education_schema(), "education"),
        ("HOSPITAL/CLÍNICA", healthcare_schema(), "healthcare"),
        ("TRANSPORTE", transportation_schema(), "transportation"),
        ("TIENDA DE ROPA", retail_clothing_schema(), "retail"),
    ]

    failed = False

    for label, schema, expected in scenarios:
        result = detect_business_domains(schema)
        detected = result["primary_domain"]

        print("\n" + "=" * 60)
        print(label)
        print(f"Esperado:  {expected}")
        print(f"Detectado: {detected}")
        print(f"Confianza: {result['primary_confidence']}")
        print(f"Ambiguo:   {result['ambiguous']}")

        for candidate in result["candidates"][:3]:
            print(
                f"  - {candidate['domain']}: "
                f"{candidate['score']}% ({candidate['confidence']})"
            )

        if detected != expected:
            failed = True

    if failed:
        raise SystemExit("Uno o más escenarios no fueron clasificados correctamente.")

    print("\nTodos los escenarios fueron clasificados correctamente.")


if __name__ == "__main__":
    main()
