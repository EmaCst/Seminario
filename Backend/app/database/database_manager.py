import os
from threading import RLock

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL


load_dotenv()


class DatabaseManager:
    """Administra la fuente de datos activa en tiempo de ejecución."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._engine: Engine | None = None
        self._config: dict | None = None

        env_config = {
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_DATABASE"),
            "username": os.getenv("DB_USERNAME"),
            "password": os.getenv("DB_PASSWORD"),
            "driver": os.getenv("DB_DRIVER") or "ODBC Driver 18 for SQL Server",
        }

        if env_config["server"] and env_config["database"]:
            self.configure(**env_config)

    @staticmethod
    def _build_sqlserver_engine(
        server: str,
        database: str,
        username: str | None = None,
        password: str | None = None,
        driver: str = "ODBC Driver 18 for SQL Server",
        autocommit: bool = False,
    ) -> Engine:
        query = {
            "driver": driver,
            "TrustServerCertificate": "yes",
        }

        if username:
            connection_url = URL.create(
                "mssql+pyodbc",
                username=username,
                password=password,
                host=server,
                database=database,
                query=query,
            )
        else:
            query["Trusted_Connection"] = "yes"
            connection_url = URL.create(
                "mssql+pyodbc",
                host=server,
                database=database,
                query=query,
            )

        connect_args = {"autocommit": True} if autocommit else {}

        return create_engine(
            connection_url,
            pool_size=5,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

    @staticmethod
    def _build_postgresql_engine(
        host: str,
        database: str,
        username: str,
        password: str | None = None,
        port: int = 5432,
        sslmode: str = "prefer",
    ) -> Engine:
        connection_url = URL.create(
            "postgresql+psycopg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
            query={"sslmode": sslmode},
        )

        return create_engine(
            connection_url,
            pool_size=5,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )

    # Compatibilidad con el flujo SQL Server existente.
    _build_engine = _build_sqlserver_engine

    def test_connection(
        self,
        server: str,
        database: str,
        username: str | None = None,
        password: str | None = None,
        driver: str = "ODBC Driver 18 for SQL Server",
    ) -> dict:
        temp_engine = self._build_sqlserver_engine(
            server=server,
            database=database,
            username=username,
            password=password,
            driver=driver,
        )

        try:
            with temp_engine.connect() as connection:
                row = connection.exec_driver_sql(
                    "SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name"
                ).mappings().first()

                return {
                    "ok": True,
                    "provider": "sqlserver",
                    "database": row["database_name"] if row else database,
                    "server": row["server_name"] if row else server,
                }
        finally:
            temp_engine.dispose()

    def test_postgresql_connection(
        self,
        host: str,
        database: str,
        username: str,
        password: str | None = None,
        port: int = 5432,
        sslmode: str = "prefer",
    ) -> dict:
        temp_engine = self._build_postgresql_engine(
            host=host,
            database=database,
            username=username,
            password=password,
            port=port,
            sslmode=sslmode,
        )

        try:
            with temp_engine.connect() as connection:
                row = connection.exec_driver_sql(
                    "SELECT current_database() AS database_name, "
                    "current_user AS current_user, "
                    "inet_server_addr()::text AS server_address"
                ).mappings().first()

                return {
                    "ok": True,
                    "provider": "postgresql",
                    "database": row["database_name"] if row else database,
                    "host": row["server_address"] if row and row["server_address"] else host,
                    "port": port,
                    "user": row["current_user"] if row else username,
                }
        finally:
            temp_engine.dispose()

    def configure(
        self,
        server: str,
        database: str,
        username: str | None = None,
        password: str | None = None,
        driver: str = "ODBC Driver 18 for SQL Server",
    ) -> dict:
        new_engine = self._build_sqlserver_engine(
            server=server,
            database=database,
            username=username,
            password=password,
            driver=driver,
        )

        with new_engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name"
            ).mappings().first()

        with self._lock:
            old_engine = self._engine
            self._engine = new_engine
            self._config = {
                "provider": "sqlserver",
                "server": server,
                "database": row["database_name"] if row else database,
                "username": username,
                "password": password,
                "driver": driver,
                "auth": "sql" if username else "windows",
            }

            if old_engine is not None:
                old_engine.dispose()

        return self.status()

    def configure_postgresql(
        self,
        host: str,
        database: str,
        username: str,
        password: str | None = None,
        port: int = 5432,
        sslmode: str = "prefer",
    ) -> dict:
        new_engine = self._build_postgresql_engine(
            host=host,
            database=database,
            username=username,
            password=password,
            port=port,
            sslmode=sslmode,
        )

        with new_engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT current_database() AS database_name, current_user AS current_user"
            ).mappings().first()

        with self._lock:
            old_engine = self._engine
            self._engine = new_engine
            self._config = {
                "provider": "postgresql",
                "host": host,
                "port": port,
                "database": row["database_name"] if row else database,
                "username": username,
                "password": password,
                "sslmode": sslmode,
                "auth": "password",
            }

            if old_engine is not None:
                old_engine.dispose()

        return self.status()

    def get_engine(self) -> Engine:
        with self._lock:
            if self._engine is None:
                raise RuntimeError(
                    "No hay una base de datos activa. Configura una conexión primero."
                )
            return self._engine

    def get_connection(self):
        return self.get_engine().connect()

    def get_active_config(self) -> dict:
        """Devuelve una copia privada de la configuración activa, incluida la clave."""
        with self._lock:
            if self._config is None:
                raise RuntimeError("No hay una fuente de datos activa configurada.")
            return dict(self._config)

    def create_system_engine(self, database: str = "master") -> Engine:
        """Crea un engine administrativo SQL Server para operaciones como RESTORE."""
        config = self.get_active_config()
        if config.get("provider") != "sqlserver":
            raise RuntimeError(
                "La restauración .bak solo está disponible cuando la fuente activa es SQL Server."
            )

        return self._build_sqlserver_engine(
            server=config["server"],
            database=database,
            username=config.get("username"),
            password=config.get("password"),
            driver=config.get("driver") or "ODBC Driver 18 for SQL Server",
            autocommit=True,
        )

    def status(self) -> dict:
        with self._lock:
            if self._engine is None or self._config is None:
                return {
                    "connected": False,
                    "provider": None,
                    "database": None,
                    "server": None,
                    "host": None,
                    "port": None,
                    "driver": None,
                    "auth": None,
                }

            provider = self._config.get("provider", "sqlserver")
            return {
                "connected": True,
                "provider": provider,
                "database": self._config["database"],
                "server": self._config.get("server"),
                "host": self._config.get("host"),
                "port": self._config.get("port"),
                "driver": self._config.get("driver"),
                "sslmode": self._config.get("sslmode"),
                "auth": self._config.get("auth"),
            }


database_manager = DatabaseManager()
