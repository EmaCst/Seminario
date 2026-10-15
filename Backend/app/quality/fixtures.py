"""Disposable SQLite business fixtures for Kenneth's integration tests.

No configured database, external service, or user data is accessed. Each fixture
uses a fresh temporary file and patches the database manager only within its
context. All dates and expected amounts are explicitly defined test data.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
from unittest.mock import patch

from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine

from app.database.database_manager import database_manager


@dataclass(frozen=True)
class DomainFixture:
    domain: str
    primary_role: str
    primary_table: str
    question_term: str
    tables: tuple[str, ...]
    amount_column: str | None = None


DOMAINS: tuple[DomainFixture, ...] = (
    DomainFixture("retail", "sales", "ventas", "ventas",
                  ("ventas", "productos", "detalle_ventas", "clientes", "inventario"),
                  "total"),
    DomainFixture("education", "enrollments", "inscripciones", "inscripciones",
                  ("estudiantes", "docentes", "cursos", "inscripciones")),
    DomainFixture("healthcare", "appointments", "citas", "citas",
                  ("pacientes", "medicos", "citas", "diagnosticos")),
    DomainFixture("transportation", "trips", "viajes", "viajes",
                  ("vehiculos", "rutas", "viajes", "conductores")),
    DomainFixture("hospitality", "reservations", "reservas", "reservas",
                  ("habitaciones", "reservas", "huespedes", "estadias"), "total"),
    DomainFixture("restaurant", "orders", "pedidos", "pedidos",
                  ("platos", "mesas", "pedidos", "ingredientes"), "total"),
    DomainFixture("professional_services", "invoices", "facturas", "facturas",
                  ("servicios", "clientes", "proyectos", "facturas"), "total"),
    DomainFixture("finance_accounting", "transactions", "transacciones", "transacciones",
                  ("cuentas", "transacciones", "asientos", "libro_mayor"), "monto"),
    DomainFixture("manufacturing", "production_orders", "orden_produccion",
                  "ordenes de produccion",
                  ("orden_produccion", "materiales", "maquinas", "lotes")),
    DomainFixture("human_resources", "payroll", "nomina", "nomina",
                  ("empleados", "nomina", "departamentos", "turnos"), "monto"),
)


def _seed_fixture(engine, fixture: DomainFixture) -> None:
    metadata = MetaData()
    primary: Table | None = None
    tables: dict[str, Table] = {}
    for name in fixture.tables:
        if name == "detalle_ventas":
            continue
        columns = [Column("id", Integer, primary_key=True)]
        if name == fixture.primary_table:
            columns.extend([
                Column("fecha", String(20), nullable=False),
                Column("estado", String(30), nullable=False),
            ])
            if fixture.amount_column:
                columns.append(Column(fixture.amount_column, Integer, nullable=False))
            if fixture.domain == "retail":
                columns.append(Column("cliente_id", Integer, ForeignKey("clientes.id")))
        else:
            columns.append(Column("nombre", String(100), nullable=False))
        table = Table(name, metadata, *columns)
        tables[name] = table
        if name == fixture.primary_table:
            primary = table

    if fixture.domain == "retail":
        tables["detalle_ventas"] = Table(
            "detalle_ventas", metadata,
            Column("id", Integer, primary_key=True),
            Column("venta_id", Integer, ForeignKey("ventas.id"), nullable=False),
            Column("producto_id", Integer, ForeignKey("productos.id"), nullable=False),
            Column("cantidad", Integer, nullable=False),
            Column("subtotal", Integer, nullable=False),
        )

    metadata.create_all(engine)
    if primary is None:
        raise ValueError(f"No primary table for {fixture.domain}")

    with engine.begin() as connection:
        for name, table in tables.items():
            if name in {fixture.primary_table, "detalle_ventas"}:
                continue
            if name == "productos":
                connection.execute(table.insert(), [
                    {"id": 1, "nombre": "Café"},
                    {"id": 2, "nombre": "Pan"},
                ])
            elif name == "clientes" and fixture.domain == "retail":
                connection.execute(table.insert(), [
                    {"id": 1, "nombre": "Ana"},
                    {"id": 2, "nombre": "Luis"},
                ])
            else:
                connection.execute(table.insert(), [
                    {"id": 1, "nombre": f"{name} ficticio 1"},
                    {"id": 2, "nombre": f"{name} ficticio 2"},
                ])

        records = [
            {"id": 1, "fecha": "2026-02-03", "estado": "pendiente"},
            {"id": 2, "fecha": "2026-06-03", "estado": "confirmado"},
            {"id": 3, "fecha": "2026-06-04", "estado": "confirmado"},
        ]
        for row, amount in zip(records, (100, 290, 210)):
            if fixture.amount_column:
                row[fixture.amount_column] = amount
            if fixture.domain == "retail":
                row["cliente_id"] = 1 if row["id"] < 3 else 2
        connection.execute(primary.insert(), records)

        if fixture.domain == "retail":
            connection.execute(tables["detalle_ventas"].insert(), [
                {"id": 1, "venta_id": 1, "producto_id": 1,
                 "cantidad": 1, "subtotal": 100},
                {"id": 2, "venta_id": 2, "producto_id": 1,
                 "cantidad": 3, "subtotal": 290},
                {"id": 3, "venta_id": 3, "producto_id": 2,
                 "cantidad": 2, "subtotal": 210},
            ])


@contextmanager
def connected_fixture(fixture: DomainFixture) -> Iterator[None]:
    """Connect Kenneth to ONLY a throwaway SQLite database in this context.

    No global database is activated or disposed; the previous manager is
    unaffected. No network or Ollama calls are made by this fixture.
    """
    with TemporaryDirectory(prefix=f"kenneth_quality_{fixture.domain}_") as temp:
        database_file = Path(temp) / "fixture.sqlite3"
        engine = create_engine(
            f"sqlite+pysqlite:///{database_file.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        try:
            _seed_fixture(engine, fixture)
            status = {
                "connected": True,
                "provider": "excel",  # SQLite is Kenneth's Excel SQL dialect.
                "database": f"kenneth_fixture_{fixture.domain}",
                "auth": "local",
            }
            with ExitStack() as stack:
                stack.enter_context(patch.object(database_manager, "get_engine",
                                                 return_value=engine))
                stack.enter_context(patch.object(database_manager, "get_connection",
                                                 side_effect=engine.connect))
                stack.enter_context(patch.object(database_manager, "status",
                                                 return_value=status))
                yield
        finally:
            engine.dispose()
