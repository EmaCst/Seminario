import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


load_dotenv()


DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DRIVER = os.getenv("DB_DRIVER")


connection_url = URL.create(
    "mssql+pyodbc",
    username=DB_USERNAME,
    password=DB_PASSWORD,
    host=DB_SERVER,
    database=DB_DATABASE,
    query={
        "driver": DB_DRIVER,
        "TrustServerCertificate": "yes",
    },
)


engine = create_engine(
    connection_url,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)


def get_connection():
    return engine.connect()