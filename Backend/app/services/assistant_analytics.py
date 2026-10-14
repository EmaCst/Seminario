"""Verified, read-only business analytics for common conversational questions.

All identifiers come from the database inspector/semantic mapper, never user
text. Parameters carry values; SQL expressions are dialect-aware.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text

from app.analysis.adaptive_dashboard_service import _provider, _quote
from app.analysis.semantic_mapper import inspect_semantic_map
from app.database.connection import get_connection
from app.services.assistant_router import Intent, MONTH_LABELS


def _response(answer: str, rows: list[dict] | None = None) -> dict:
    return {"mode": "analytics", "sql": None, "data": rows or [], "answer": answer}


def _number(value, *, money: bool = False) -> str:
    number = float(value)
    return f"{number:,.2f}" if money else f"{number:,.0f}"


def _query(sql: str, params: dict | None = None) -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute(text(sql), params or {}).mappings().all()]


def _year_expr(column: str) -> str:
    provider = _provider()
    if provider == "excel":
        return f"CAST(strftime('%Y', {column}) AS INTEGER)"
    if provider == "postgresql":
        return f"CAST(EXTRACT(YEAR FROM {column}) AS INTEGER)"
    return f"YEAR({column})"


def _month_expr(column: str) -> str:
    provider = _provider()
    if provider == "excel":
        return f"CAST(strftime('%m', {column}) AS INTEGER)"
    if provider == "postgresql":
        return f"CAST(EXTRACT(MONTH FROM {column}) AS INTEGER)"
    return f"MONTH({column})"


def _sales_model() -> dict:
    return (inspect_semantic_map().get("semantic_map") or {})


def _monthly_series(sales: dict, metric: str) -> list[dict]:
    table, date = sales.get("header_table"), sales.get("date_column")
    amount = sales.get("total_column")
    if not table or not date:
        return []
    if metric == "amount" and not amount:
        return []
    if metric not in {"amount", "count"}:
        return []
    qdate = "s." + _quote(date)
    measure = f"SUM(s.{_quote(amount)})" if metric == "amount" else "COUNT(*)"
    year, month = _year_expr(qdate), _month_expr(qdate)
    sql = (f"SELECT {year} AS year, {month} AS month, {measure} AS total "
           f"FROM {_quote(table)} s WHERE {qdate} IS NOT NULL "
           f"GROUP BY {year}, {month} ORDER BY {year}, {month}")
    rows = _query(sql)
    return [{"year": int(r["year"]), "month": int(r["month"]),
             "total": float(r["total"])} for r in rows
            if r["year"] is not None and r["month"] is not None and r["total"] is not None]


def _period_year(rows: list[dict], months: tuple[int, ...], year: int | None) -> int | None:
    if year is not None:
        return year
    by_year: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        by_year[row["year"]].add(row["month"])
    valid = [y for y, available in by_year.items() if set(months).issubset(available)]
    return max(valid, default=None)


def _monthly_answer(intent: Intent, sales: dict) -> dict:
    if intent.metric == "units":
        return _response("Para conocer unidades vendidas necesito los detalles de ventas y sus cantidades; no equivalen al número de facturas ni al monto monetario.")
    if not sales.get("header_table") or not sales.get("date_column") or (intent.metric == "amount" and not sales.get("total_column")):
        return _response("No pude identificar con seguridad la tabla, fecha y métrica de ventas necesarias en esta base de datos.")
    rows = _monthly_series(sales, intent.metric)
    months = intent.months
    year = _period_year(rows, months, intent.year)
    if year is None:
        return _response("No hay registros suficientes para comparar esos meses en un mismo año." if len(months) == 2
                         else "No encontré registros para ese mes en los datos consultados.")
    totals = {(row["year"], row["month"]): row["total"] for row in rows}
    if any((year, month) not in totals for month in months):
        return _response(f"No encontré datos de todos los meses solicitados en {year}; no asumiré que un mes sin registros equivale a cero.")
    selected = [{"year": year, "month": month, "total": totals[(year, month)],
                 "metric": intent.metric} for month in months]
    money = intent.metric == "amount"
    measure = "monto de ventas" if money else "cantidad de ventas"
    if len(months) == 1:
        month = months[0]
        return _response(f"El {measure} de {MONTH_LABELS[month]} de {year} fue {_number(totals[(year, month)], money=money)}"
                         + ("." if money else " transacciones."), selected)
    first, second = months
    first_total, second_total = totals[(year, first)], totals[(year, second)]
    difference = first_total - second_total
    larger = MONTH_LABELS[first if difference >= 0 else second]
    percentage = ((abs(difference) / second_total) * 100) if second_total else None
    answer = (f"En {MONTH_LABELS[first]} de {year} el {measure} fue {_number(first_total, money=money)} "
              f"y en {MONTH_LABELS[second]} fue {_number(second_total, money=money)}. "
              f"La diferencia absoluta fue {_number(abs(difference), money=money)}; {larger} registró el valor mayor.")
    if percentage is not None:
        answer += f" Frente a {MONTH_LABELS[second]}, la variación fue {difference / second_total * 100:+.2f}%."
    return _response(answer, selected)


def _period_clause(alias: str, column: str, *, month: int | None, year: int | None) -> tuple[str, dict]:
    if month is None:
        return "", {}
    expression = f"{alias}.{_quote(column)}"
    clause = f"{_month_expr(expression)} = :month"
    params = {"month": month}
    if year is not None:
        clause += f" AND {_year_expr(expression)} = :year"
        params["year"] = year
    return " WHERE " + clause, params


def _ranked_sql(sql: str, limit: int) -> str:
    """Apply a bounded TOP/LIMIT without putting untrusted text into SQL."""
    limit = max(1, min(20, int(limit)))
    if _provider() == "sqlserver":
        return sql.replace("SELECT ", f"SELECT TOP {limit} ", 1)
    return sql + f" LIMIT {limit}"


def _product_sql(
    model: dict, *, metric: str, month: int | None, year: int | None,
    limit: int | None = None,
) -> tuple[str, dict] | None:
    sales = model.get("sales") or {}
    products = model.get("products") or {}
    detail = sales.get("detail_table")
    product_table = products.get("table")
    product_name = products.get("name_column")
    product_rel = sales.get("product_relationship")
    detail_rel = sales.get("detail_relationship")
    if not (detail and product_table and product_name and product_rel):
        return None
    if month is not None and not (sales.get("header_table") and sales.get("date_column") and detail_rel):
        return None
    if metric == "units":
        column = sales.get("quantity_column")
        if not column:
            return None
        measure = f"SUM(d.{_quote(column)})"
    else:
        # Historic revenue must come from line totals, not current list prices.
        from app.database.inspector import inspect_database
        detail_schema = inspect_database().tables.get(detail)
        columns = {col.name.lower(): col.name for col in (detail_schema.columns if detail_schema else [])}
        amount = next((columns[key] for key in ("subtotal", "total", "importe", "line_total", "amount")
                       if key in columns), None)
        if amount is None:
            return None
        measure = f"SUM(d.{_quote(amount)})"
    fk, pk = product_rel["from_column"], product_rel["to_column"]
    joins = (f" FROM {_quote(detail)} d "
             f"INNER JOIN {_quote(product_table)} p ON d.{_quote(fk)} = p.{_quote(pk)}")
    where, params = "", {}
    if month is not None:
        dfk, hpk = detail_rel["from_column"], detail_rel["to_column"]
        joins += (f" INNER JOIN {_quote(sales['header_table'])} s "
                  f"ON d.{_quote(dfk)} = s.{_quote(hpk)}")
        where, params = _period_clause("s", sales["date_column"], month=month, year=year)
    label, identifier = f"p.{_quote(product_name)}", f"p.{_quote(pk)}"
    sql = (f"SELECT {identifier} AS entity_id, {label} AS entity, {measure} AS value"
           f"{joins}{where} GROUP BY {identifier}, {label} ORDER BY value DESC")
    return (_ranked_sql(sql, limit) if limit is not None else sql), params


def _top_product(intent: Intent, model: dict) -> dict:
    if len(intent.months) > 1:
        return _response("¿De cuál de esos meses quieres el ranking de productos? También puedo comparar los rankings de ambos.")
    month = intent.months[0] if intent.months else None
    year = intent.year
    if month is not None and year is None:
        series = _monthly_series(model.get("sales") or {}, "count")
        year = _period_year(series, (month,), None)
        if year is None:
            return _response(f"No encontré ventas registradas para {MONTH_LABELS[month]}.")
    built = _product_sql(model, metric=intent.metric, month=month, year=year, limit=intent.limit)
    if built is None:
        return _response("No puedo elaborar un ranking confiable de productos: falta la relación entre productos y detalle de ventas o la métrica solicitada.")
    sql, params = built
    rows = _query(sql, params)
    if not rows:
        return _response("No encontré productos vendidos en el periodo consultado.")
    suffix = f" en {MONTH_LABELS[month]} de {year}" if month is not None else ""
    unit = "unidades" if intent.metric == "units" else "de importe vendido"
    result = [{"product": row["entity"], "product_id": row["entity_id"], "total": float(row["value"])}
              for row in rows]
    if intent.limit == 1:
        best = rows[0]
        answer = (f"El producto más vendido{suffix} fue {best['entity']}, "
                  f"con {_number(best['value'], money=intent.metric == 'amount')} {unit}.")
    else:
        ranked = "; ".join(f"{index}. {row['entity']}: {_number(row['value'], money=intent.metric == 'amount')} {unit}"
                           for index, row in enumerate(rows, 1))
        answer = f"Ranking de productos{suffix} por {'unidades' if intent.metric == 'units' else 'importe'}: {ranked}."
    return _response(answer, result)


def _customer_rank(intent: Intent, model: dict) -> dict:
    if len(intent.months) > 1:
        return _response("¿En cuál de los meses mencionados quieres ordenar los clientes?")
    sales = model.get("sales") or {}
    customers = model.get("customers") or {}
    relationship = sales.get("customer_relationship")
    table, total = sales.get("header_table"), sales.get("total_column")
    customer_table, name = customers.get("table"), customers.get("name_column")
    if not all((relationship, table, customer_table, name)) or (intent.metric == "amount" and not total):
        return _response("No puedo identificar al mejor cliente con seguridad: falta una relación verificable entre clientes y ventas o el importe de las compras.")
    month = intent.months[0] if intent.months else None
    if month is not None and not sales.get("date_column"):
        return _response("No encontré una fecha de venta confiable para filtrar el ranking de clientes por mes.")
    year = intent.year
    if month is not None and year is None:
        year = _period_year(_monthly_series(sales, "count"), (month,), None)
        if year is None:
            return _response(f"No encontré ventas registradas para {MONTH_LABELS[month]}.")
    measure = "COUNT(*)" if intent.metric == "count" else f"SUM(s.{_quote(total)})"
    filter_sql, params = _period_clause("s", sales["date_column"], month=month, year=year) if month is not None else ("", {})
    identifier, label = f"c.{_quote(relationship['to_column'])}", f"c.{_quote(name)}"
    sql = (f"SELECT {identifier} AS entity_id, {label} AS entity, {measure} AS value "
           f"FROM {_quote(table)} s INNER JOIN {_quote(customer_table)} c "
           f"ON s.{_quote(relationship['from_column'])} = {identifier} "
           f"{filter_sql} GROUP BY {identifier}, {label} ORDER BY value DESC")
    rows = _query(_ranked_sql(sql, intent.limit), params)
    if not rows:
        return _response("No encontré compras asociadas a clientes en el periodo consultado.")
    suffix = f" en {MONTH_LABELS[month]} de {year}" if month is not None else ""
    unit = "transacciones" if intent.metric == "count" else "en importe de compras"
    result = [{"customer": row["entity"], "customer_id": row["entity_id"], "total": float(row["value"])}
              for row in rows]
    if intent.limit == 1:
        first = rows[0]
        answer = (f"El cliente con {'más compras' if intent.metric == 'count' else 'mayor importe de compras'}{suffix} "
                  f"es {first['entity']}, con {_number(first['value'], money=intent.metric == 'amount')} {unit}.")
    else:
        ranked = "; ".join(f"{index}. {row['entity']}: {_number(row['value'], money=intent.metric == 'amount')} {unit}"
                           for index, row in enumerate(rows, 1))
        answer = f"Ranking de clientes{suffix}: {ranked}."
    return _response(answer, result)


def _product_attribution(intent: Intent, model: dict) -> dict:
    if len(intent.months) != 2:
        return _response("¿Qué dos meses deseas comparar para identificar los productos que contribuyeron a la diferencia?")
    sales = model.get("sales") or {}
    series = _monthly_series(sales, "amount")
    year = _period_year(series, intent.months, intent.year)
    if year is None:
        return _response("No hay datos de ambos meses en un mismo año para analizar la diferencia por producto.")
    values = {}
    for month in intent.months:
        built = _product_sql(model, metric="amount", month=month, year=year)
        if built is None:
            return _response("No puedo atribuir la diferencia monetaria a productos: necesito el detalle con importes históricos, sus relaciones con productos y ventas, y la fecha de venta.")
        sql, params = built
        values[month] = {str(row["entity"]): float(row["value"]) for row in _query(sql, params)}
    first, second = intent.months
    all_products = set(values[first]) | set(values[second])
    if not all_products:
        return _response("No encontré ventas detalladas por producto para esos meses.")
    deltas = [{"product": name, "first": values[first].get(name, 0.0),
               "second": values[second].get(name, 0.0),
               "difference": values[first].get(name, 0.0) - values[second].get(name, 0.0)}
              for name in all_products]
    deltas.sort(key=lambda row: abs(row["difference"]), reverse=True)
    biggest = deltas[0]
    direction = "mayor" if biggest["difference"] >= 0 else "menor"
    answer = (f"Al comparar el importe por producto entre {MONTH_LABELS[first]} y {MONTH_LABELS[second]} de {year}, "
              f"{biggest['product']} registró la mayor variación absoluta: "
              f"{_number(abs(biggest['difference']), money=True)} ({direction} en {MONTH_LABELS[first]}). "
              "Es una contribución observada en el detalle de ventas, no una causa demostrada de la variación total.")
    return _response(answer, deltas[:10])


def run_verified_analytics(intent: Intent) -> dict | None:
    """Return None for unhandled intent; known analytic requests never invent SQL."""
    if intent.kind not in {"monthly_total", "monthly_compare", "product_top",
                           "product_attribution", "customer_top"}:
        return None
    model = _sales_model()
    if intent.kind in {"monthly_total", "monthly_compare"}:
        return _monthly_answer(intent, model.get("sales") or {})
    if intent.kind == "product_top":
        return _top_product(intent, model)
    if intent.kind == "customer_top":
        return _customer_rank(intent, model)
    return _product_attribution(intent, model)
