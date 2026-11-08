import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.database_manager import database_manager
from app.database.inspector import inspect_database


def source_with_table(table_name):
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY, nombre TEXT)'
        )
        connection.exec_driver_sql(
            f'INSERT INTO "{table_name}" (id, nombre) VALUES (1, ?)', ("Ejemplo",)
        )
    return engine


class SemanticCacheIntegrationTests(unittest.TestCase):
    def test_schema_and_domain_cached_until_source_switch(self):
        engine_a = source_with_table("clientes")
        queries = []
        event.listen(engine_a, "before_cursor_execute",
                     lambda *args: queries.append(args[2]))
        try:
            database_manager.configure_excel(
                engine_a, "a.xlsx", ["clientes"], 1, "/test/a.sqlite"
            )
            first = inspect_semantic_model()
            first_count = len(queries)
            self.assertGreater(first_count, 0)
            self.assertEqual(inspect_semantic_model(), first)
            self.assertEqual(len(queries), first_count)
            self.assertEqual(
                inspect_database().tables.keys(), {"clientes"}
            )
            self.assertEqual(len(queries), first_count)

            engine_b = source_with_table("productos")
            database_manager.configure_excel(
                engine_b, "b.xlsx", ["productos"], 1, "/test/b.sqlite"
            )
            second = inspect_semantic_model()
            self.assertIn("productos", inspect_database().tables)
            self.assertNotEqual(first["semantic_model"], second["semantic_model"])
        finally:
            # Tests don't modify the active connection outside their process.
            engine_a.dispose()


if __name__ == "__main__":
    unittest.main()
