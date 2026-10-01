import json

from app.database.schema import DatabaseSchema


def schema_to_dict(schema: DatabaseSchema) -> dict:
    """
    Convierte el esquema de la base de datos
    a un diccionario de Python.
    """
    return schema.to_dict()


def schema_to_json(
    schema: DatabaseSchema,
    indent: int = 2
) -> str:
    """
    Convierte el esquema de la base de datos
    a una cadena JSON.
    """
    return json.dumps(
        schema_to_dict(schema),
        ensure_ascii=False,
        indent=indent
    )