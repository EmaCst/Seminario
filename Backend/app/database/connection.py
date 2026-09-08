from app.database.database_manager import database_manager


def get_engine():
    """Devuelve el engine de la base de datos activa."""
    return database_manager.get_engine()


def get_connection():
    """Abre una conexión contra la base de datos activa."""
    return database_manager.get_connection()
