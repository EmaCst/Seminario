from app.database.inspector import inspect_database
from app.database.serializer import schema_to_json


def get_database_context() -> str:
    """
    Inspecciona la base de datos actual y devuelve
    su estructura en formato JSON.
    """

    schema = inspect_database()

    return schema_to_json(schema)