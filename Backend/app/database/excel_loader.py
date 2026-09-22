from __future__ import annotations

import re
import tempfile
from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from openpyxl import load_workbook
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, create_engine, insert

from app.database.database_manager import database_manager


MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_PREVIEW_ROWS = 8
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}


def _slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^0-9A-Za-zÀ-ÿ_]+", "_", str(value).strip()).strip("_").lower()
    if value and value[0].isdigit():
        value = f"col_{value}"
    return value or fallback


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _infer_type(values: list[Any]) -> str:
    clean = [value for value in values if value not in (None, "")]
    if not clean:
        return "empty"
    if all(isinstance(value, bool) for value in clean):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in clean):
        return "integer"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in clean):
        return "number"
    if all(isinstance(value, (datetime, date)) for value in clean):
        return "date"
    return "text"


def _normalize_sheet(sheet) -> dict:
    rows = list(sheet.iter_rows(values_only=True))
    non_empty = [row for row in rows if any(value not in (None, "") for value in row)]
    if not non_empty:
        return {"name": sheet.title, "table_name": _slug(sheet.title, "sheet"), "headers": [], "data_rows": [], "schema": [], "warnings": ["La hoja está vacía."]}

    header_row = list(non_empty[0])
    width = max(len(row) for row in non_empty)
    headers: list[str] = []
    used: set[str] = set()
    warnings: list[str] = []

    for index in range(width):
        raw = header_row[index] if index < len(header_row) else None
        base = _slug(raw, f"column_{index + 1}") if raw not in (None, "") else f"column_{index + 1}"
        name = base
        suffix = 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        if raw in (None, ""):
            warnings.append(f"La columna {index + 1} no tiene encabezado; se interpretó como {name}.")
        used.add(name)
        headers.append(name)

    data_rows = [list(row) + [None] * (width - len(row)) for row in non_empty[1:]]
    schema = []
    for index, header in enumerate(headers):
        values = [row[index] for row in data_rows]
        non_null = sum(value not in (None, "") for value in values)
        schema.append({
            "name": header,
            "source_header": _json_value(header_row[index]) if index < len(header_row) else None,
            "type": _infer_type(values),
            "non_null": non_null,
            "nulls": len(values) - non_null,
            "unique_values": len({str(value) for value in values if value not in (None, "")}),
        })
    return {"name": sheet.title, "table_name": _slug(sheet.title, "sheet"), "headers": headers, "data_rows": data_rows, "schema": schema, "warnings": warnings}


def _public_profile(sheet: dict) -> dict:
    preview = [{sheet["headers"][i]: _json_value(row[i]) for i in range(len(sheet["headers"]))} for row in sheet["data_rows"][:MAX_PREVIEW_ROWS]]
    return {"name": sheet["name"], "table_name": sheet["table_name"], "rows": len(sheet["data_rows"]), "columns": len(sheet["headers"]), "headers": sheet["headers"], "schema": sheet["schema"], "preview": preview, "warnings": sheet["warnings"]}


async def _read_workbook(file: UploadFile) -> tuple[str, bytes, list[dict]]:
    filename = file.filename or "workbook.xlsx"
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato no compatible. Usa un archivo .xlsx o .xlsm.")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise ValueError("El archivo Excel está vacío.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("El archivo Excel supera el límite de 25 MB.")
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        sheets = [_normalize_sheet(sheet) for sheet in workbook.worksheets]
        workbook.close()
    except Exception as exc:
        raise ValueError(f"No se pudo leer el libro de Excel: {exc}") from exc
    return filename, content, sheets


async def inspect_excel_upload(file: UploadFile) -> dict:
    filename, content, sheets = await _read_workbook(file)
    profiles = [_public_profile(sheet) for sheet in sheets]
    populated = [sheet for sheet in profiles if sheet["rows"] > 0]
    total_rows = sum(sheet["rows"] for sheet in populated)
    return {
        "uploaded": True, "source_type": "excel", "filename": filename, "size_bytes": len(content),
        "sheet_count": len(profiles), "populated_sheets": len(populated), "total_data_rows": total_rows,
        "total_columns": sum(sheet["columns"] for sheet in populated), "sheets": profiles,
        "interpretation": {"summary": f"Se detectaron {len(populated)} hojas con datos y {total_rows} filas.", "ready_to_import": bool(populated)},
    }


def _sql_type(kind: str):
    return {"boolean": Boolean, "integer": Integer, "number": Float, "date": DateTime}.get(kind, String)


def _db_value(value: Any, kind: str) -> Any:
    if value in (None, ""):
        return None
    if kind == "date":
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        return str(value)
    if kind == "text" or kind == "empty":
        return str(value)
    return value


async def activate_excel_upload(file: UploadFile) -> dict:
    """Convierte un Excel en SQLite local y lo activa como la fuente SQL del sistema."""
    filename, content, sheets = await _read_workbook(file)
    populated = [sheet for sheet in sheets if sheet["data_rows"] and sheet["headers"]]
    if not populated:
        raise ValueError("El libro no contiene hojas con filas de datos utilizables.")

    temp_dir = Path(tempfile.gettempdir()) / "kenneth_excel_sources"
    temp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _slug(Path(filename).stem, "excel")
    db_path = temp_dir / f"{safe_name}.sqlite3"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(f"sqlite:///{db_path}")
    metadata = MetaData()
    tables: dict[str, Table] = {}
    used_tables: set[str] = set()

    for sheet_index, sheet in enumerate(populated, start=1):
        base = sheet["table_name"] or f"sheet_{sheet_index}"
        table_name = base
        suffix = 2
        while table_name in used_tables:
            table_name = f"{base}_{suffix}"
            suffix += 1
        used_tables.add(table_name)
        sheet["table_name"] = table_name
        columns = [Column(item["name"], _sql_type(item["type"]), nullable=True) for item in sheet["schema"]]
        tables[table_name] = Table(table_name, metadata, *columns)

    metadata.create_all(engine)
    with engine.begin() as connection:
        for sheet in populated:
            table = tables[sheet["table_name"]]
            records = []
            for row in sheet["data_rows"]:
                records.append({item["name"]: _db_value(row[index], item["type"]) for index, item in enumerate(sheet["schema"])})
            if records:
                connection.execute(insert(table), records)

    total_rows = sum(len(sheet["data_rows"]) for sheet in populated)
    status = database_manager.configure_excel(engine=engine, filename=filename, tables=list(tables), rows=total_rows, database_path=str(db_path))
    return {
        "uploaded": True,
        "activated": True,
        "source_type": "excel",
        "connection": status,
        "filename": filename,
        "size_bytes": len(content),
        "tables": [_public_profile(sheet) for sheet in populated],
        "total_data_rows": total_rows,
    }
