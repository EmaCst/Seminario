from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from openpyxl import load_workbook


MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_PREVIEW_ROWS = 8
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}


def _slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^0-9A-Za-zÀ-ÿ_]+", "_", str(value).strip()).strip("_").lower()
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
    if all(hasattr(value, "year") and hasattr(value, "month") for value in clean):
        return "date"
    return "text"


def _sheet_profile(sheet) -> dict:
    rows = list(sheet.iter_rows(values_only=True))
    non_empty = [row for row in rows if any(value not in (None, "") for value in row)]
    if not non_empty:
        return {
            "name": sheet.title,
            "table_name": _slug(sheet.title, "sheet"),
            "rows": 0,
            "columns": 0,
            "headers": [],
            "schema": [],
            "preview": [],
            "warnings": ["La hoja está vacía."],
        }

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
        unique = len({str(value) for value in values if value not in (None, "")})
        schema.append({
            "name": header,
            "source_header": _json_value(header_row[index]) if index < len(header_row) else None,
            "type": _infer_type(values),
            "non_null": non_null,
            "nulls": len(values) - non_null,
            "unique_values": unique,
        })

    preview = []
    for row in data_rows[:MAX_PREVIEW_ROWS]:
        preview.append({headers[index]: _json_value(row[index]) for index in range(width)})

    return {
        "name": sheet.title,
        "table_name": _slug(sheet.title, "sheet"),
        "rows": len(data_rows),
        "columns": width,
        "headers": headers,
        "schema": schema,
        "preview": preview,
        "warnings": warnings,
    }


async def inspect_excel_upload(file: UploadFile) -> dict:
    filename = file.filename or "workbook.xlsx"
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato no compatible. Usa un archivo .xlsx o .xlsm.")

    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise ValueError("El archivo Excel está vacío.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("El archivo Excel supera el límite de 25 MB.")

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"No se pudo leer el libro de Excel: {exc}") from exc

    sheets = [_sheet_profile(sheet) for sheet in workbook.worksheets]
    workbook.close()

    populated = [sheet for sheet in sheets if sheet["rows"] > 0]
    total_rows = sum(sheet["rows"] for sheet in populated)
    total_columns = sum(sheet["columns"] for sheet in populated)

    return {
        "uploaded": True,
        "source_type": "excel",
        "filename": filename,
        "size_bytes": len(content),
        "sheet_count": len(sheets),
        "populated_sheets": len(populated),
        "total_data_rows": total_rows,
        "total_columns": total_columns,
        "sheets": sheets,
        "interpretation": {
            "summary": (
                f"Se detectaron {len(populated)} hojas con datos, {total_rows} filas de datos "
                f"y {total_columns} columnas en total."
            ),
            "next_step": (
                "Este perfil ya permite mostrar al usuario cómo se interpretará cada hoja. "
                "El siguiente paso es convertir las hojas seleccionadas en una fuente SQL temporal "
                "para reutilizar Semantic Mapper, Dashboard, Analítica, Kenneth y Machine Learning."
            ),
        },
    }
