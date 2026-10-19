"""Strict report configuration and data assembly for trustworthy PDF exports.

A month selection represents whole calendar months. Scope comparisons and KPIs
to those months; NEVER rebrand global rankings or all-time totals as filtered.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.analysis.adaptive_analytics_service import _trend_analysis, get_adaptive_analytics
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary, _quote
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.connection import get_connection
from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.ml.predictive_service import detect_monthly_anomalies, forecast_next_months
from app.visualizations.visualization_service import (
    VisualizationDefinition, VisualizationFilter, preview_visualization, _column_kind,
)
from app.visualizations.visualization_store import list_saved_visualizations, _source_key


SECTION_NAMES = {
    "executive": "Resumen ejecutivo",
    "analytics": "Tendencias y analítica",
    "predictive": "Pronósticos y anomalías",
    "visualizations": "Visualizaciones guardadas",
    "methodology": "Metodología y limitaciones",
}
TEMPLATE_SECTIONS = {
    "executive": ["executive", "methodology"],
    "analytics": ["analytics", "methodology"],
    "predictive": ["predictive", "methodology"],
    "complete": ["executive", "analytics", "predictive", "methodology"],
    "custom": ["executive", "analytics", "methodology"],
}


def _parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("El período debe tener formato AAAA-MM.") from exc
    return parsed.year, parsed.month


class ReportConfiguration(BaseModel):
    report_type: Literal["executive", "analytics", "predictive", "complete", "custom"] = "complete"
    title: str = Field(default="Informe empresarial", min_length=3, max_length=120)
    start_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    sections: list[Literal["executive", "analytics", "predictive", "visualizations", "methodology"]] | None = None
    visualization_ids: list[str] = Field(default_factory=list, max_length=8)
    horizon: int = Field(default=3, ge=1, le=12)
    source_key: str | None = None

    @model_validator(mode="after")
    def validate_options(self):
        if (self.start_month is None) != (self.end_month is None):
            raise ValueError("Selecciona ambos extremos del período o ninguno.")
        if self.start_month:
            beginning = _parse_month(self.start_month)
            end = _parse_month(self.end_month)
            count = (end[0] - beginning[0]) * 12 + end[1] - beginning[1] + 1
            if not 1 <= count <= 120:
                raise ValueError("El período debe abarcar entre 1 y 120 meses en orden cronológico.")
        if self.sections is not None and (not self.sections or len(self.sections) != len(set(self.sections))):
            raise ValueError("Selecciona al menos una sección sin duplicados.")
        if len(self.visualization_ids) != len(set(self.visualization_ids)):
            raise ValueError("Hay visualizaciones seleccionadas más de una vez.")
        if self.visualization_ids and "visualizations" not in self.enabled_sections:
            raise ValueError("Activa la sección de visualizaciones para incluir las gráficas seleccionadas.")
        return self

    @property
    def enabled_sections(self) -> list[str]:
        return list(self.sections) if self.sections is not None else list(TEMPLATE_SECTIONS[self.report_type])

    @property
    def period_bounds(self) -> tuple[str, str] | None:
        if not self.start_month:
            return None
        first = f"{self.start_month}-01"
        year, month = _parse_month(self.end_month)
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        return first, f"{next_year:04d}-{next_month:02d}-01"


def get_report_options() -> dict:
    status = database_manager.status()
    if not status.get("connected"):
        raise ValueError("Conecta primero una fuente de datos para generar informes.")
    saved = list_saved_visualizations()
    # A session may switch between servers using the same database name.
    # The browser must not re-use a preview from a different active instance.
    identity = "|".join(str(status.get(key) or "") for key in (
        "provider", "database", "server", "host", "port", "filename",
    ))
    source_token = f"{_source_key()}:{sha256(identity.encode('utf-8')).hexdigest()[:12]}"
    return {
        "source": {"key": source_token, "database": status.get("database"),
                   "provider": status.get("provider")},
        "templates": list(TEMPLATE_SECTIONS),
        "sections": SECTION_NAMES,
        "saved_visualizations": [
            {"id": item["id"], "title": item["definition"].get("title", "Sin título"),
             "type": item["definition"].get("visualization")}
            for item in saved
        ],
        "period_granularity": "month",
        "period_limit_months": 120,
    }


def _active_source(config: ReportConfiguration) -> dict:
    options = get_report_options()
    source = options["source"]
    if config.source_key and config.source_key != source["key"]:
        raise ValueError("La fuente activa cambió: vuelve a previsualizar el informe antes de descargarlo.")
    return source


def _within(point: dict, start: str, end: str) -> bool:
    try:
        month = f"{int(point['year']):04d}-{int(point['month']):02d}"
    except (ValueError, TypeError, KeyError):
        return False
    return start <= month <= end


def _monthly_kpis(dashboard: dict, start: str, end_exclusive: str) -> tuple[list[dict], list[str]]:
    """Time-bounded KPIs: only mapped tables with a verified date column."""
    model = (inspect_semantic_model().get("semantic_model") or {})
    entities = model.get("entities") or {}
    kpis, skipped = [], []
    for item in dashboard.get("kpis") or []:
        role = item.get("role")
        entity = entities.get(role) or {}
        table_name = entity.get("table")
        date_column = (entity.get("columns") or {}).get("date")
        if not table_name or not date_column or entity.get("ambiguous"):
            skipped.append(str(role))
            continue
        statement = text(
            f"SELECT COUNT(*) AS total FROM {_quote(table_name)} "
            f"WHERE {_quote(date_column)} >= :start AND {_quote(date_column)} < :end"
        )
        try:
            with get_connection() as conn:
                count = conn.execute(statement, {
                    "start": date.fromisoformat(start),
                    "end": date.fromisoformat(end_exclusive),
                }).scalar()
        except Exception:
            # No verified value is better than a false all-time figure.
            skipped.append(str(role))
            continue
        kpis.append({"role": role, "table": table_name, "value": int(count or 0),
                     "unit": "records", "period_filtered": True})
    return kpis, skipped


def _scope_analytics(dashboard: dict, analytics: dict, config: ReportConfiguration, warnings: list[str]):
    if not config.start_month:
        return dashboard, analytics
    scoped_dashboard, scoped_analytics = dict(dashboard), dict(analytics)
    trend = analytics.get("trend") or {}
    filtered_points = [
        item for item in trend.get("data") or []
        if _within(item, config.start_month, config.end_month)
    ]
    scoped_analytics["trend"] = _trend_analysis({
        "available": bool(filtered_points), "role": trend.get("role"),
        "data": filtered_points,
    })
    scoped_dashboard["trend"] = {
        "available": bool(filtered_points), "role": trend.get("role"),
        "data": filtered_points,
    }
    if not filtered_points:
        warnings.append("No hay registros temporales verificables en el rango seleccionado.")
    start, end_exclusive = config.period_bounds
    scoped_dashboard["kpis"], skipped = _monthly_kpis(dashboard, start, end_exclusive)
    if skipped:
        warnings.append(
            "Se omitieron KPIs sin columna de fecha verificable: " + ", ".join(skipped) + "."
        )
    # These aggregate the WHOLE database, so do not present as date-filtered.
    scoped_analytics["rankings"] = []
    scoped_analytics["distributions"] = []
    scoped_analytics["numeric_metrics"] = []
    scoped_analytics["insights"] = []
    warnings.append(
        "Rankings, distribuciones e indicadores globales se omiten porque su consulta "
        "original no admite filtrar de forma verificable por meses."
    )
    return scoped_dashboard, scoped_analytics


def _period_visualization(definition: VisualizationDefinition,
                          config: ReportConfiguration) -> VisualizationDefinition:
    """Scope an existing graph only if all its fields refer to a single table."""
    if not config.start_month:
        return definition
    base = definition.table
    if any(table != base for table in (
        definition.metric_table or base, definition.group_by_table or base,
        *(entry.table or base for entry in definition.filters),
    )):
        raise ValueError("El gráfico mezcla tablas: no se puede aplicar el período de manera inequívoca.")
    schema = inspect_database()
    table = schema.tables.get(base)
    if table is None:
        raise ValueError("La tabla de la visualización no existe en la fuente activa.")
    date_columns = [col.name for col in table.columns if _column_kind(col.type) == "date"]
    # Excel imports can store ISO date strings as TEXT, so use an unambiguous
    # date verified by the same semantic mapper as the rest of Kenneth.
    semantic = (inspect_semantic_model().get("semantic_model") or {}).get("entities") or {}
    semantic_dates = {
        mapped.get("columns", {}).get("date") for mapped in semantic.values()
        if mapped.get("table") == base and not mapped.get("ambiguous")
        and (mapped.get("columns") or {}).get("date")
    }
    known_columns = {col.name for col in table.columns}
    candidates = sorted(set(date_columns) | (semantic_dates & known_columns))
    if len(candidates) != 1:
        raise ValueError("Se necesita exactamente una columna de fecha verificable en la tabla.")
    start, end = config.period_bounds
    return definition.model_copy(update={"filters": [
        *definition.filters,
        VisualizationFilter(table=base, column=candidates[0], operator="gte", value=start),
        VisualizationFilter(table=base, column=candidates[0], operator="lt", value=end),
    ]})


def _selected_visualizations(config: ReportConfiguration, warnings: list[str]) -> list[dict]:
    if not config.visualization_ids or "visualizations" not in config.enabled_sections:
        return []
    indexed = {item["id"]: item for item in list_saved_visualizations()}
    absent = [id for id in config.visualization_ids if id not in indexed]
    if absent:
        raise ValueError("Una o más visualizaciones guardadas no pertenecen a la fuente activa.")
    result = []
    for visual_id in config.visualization_ids:
        record = indexed[visual_id]
        try:
            definition = _period_visualization(
                VisualizationDefinition.model_validate(record["definition"]), config
            )
            preview = preview_visualization(definition)
            if not preview.get("data"):
                warnings.append(f"«{definition.title}» no tiene registros para el período solicitado.")
                continue
            result.append({
                "id": visual_id, "title": definition.title,
                "type": definition.visualization, "data": preview["data"],
                "definition": definition.model_dump(),
                "period_filtered": bool(config.start_month),
            })
        except ValueError as exc:
            warnings.append(f"Se omitió «{record['definition'].get('title', 'Visualización')}»: {exc}")
    return result


def prepare_report(config: ReportConfiguration) -> dict:
    source = _active_source(config)
    warnings: list[str] = []
    dashboard = get_adaptive_dashboard_summary()
    analytics = get_adaptive_analytics()
    dashboard, analytics = _scope_analytics(dashboard, analytics, config, warnings)
    forecast = anomalies = None
    if "predictive" in config.enabled_sections:
        # A forecast is trained on the FULL timeline; restricting training to
        # the report's descriptive date filter would change its meaning.
        try:
            forecast = forecast_next_months(horizon=config.horizon)
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"No fue posible calcular el pronóstico: {exc}")
        try:
            anomalies = detect_monthly_anomalies()
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"No fue posible identificar anomalías: {exc}")
        if config.start_month and anomalies:
            anomalies = {
                **anomalies,
                "anomalies": [
                    row for row in anomalies.get("anomalies") or []
                    if _within(row, config.start_month, config.end_month)
                ],
                "review_points": [
                    row for row in anomalies.get("review_points") or []
                    if _within(row, config.start_month, config.end_month)
                ],
            }
            warnings.append(
                "La detección de anomalías usa el historial completo para ajustar "
                "el modelo; solo se muestran alertas dentro del período solicitado."
            )
        if config.start_month and forecast:
            warnings.append(
                "El pronóstico utiliza el historial completo disponible y comienza tras "
                "el último dato real, independientemente del rango descriptivo del informe."
            )
    visualizations = _selected_visualizations(config, warnings)
    # Reject mixed-source documents if the process switched connections while
    # assembling multiple sections of the report.
    if _active_source(config)["key"] != source["key"]:
        raise ValueError("La fuente activa cambió durante la generación. Vuelve a intentarlo.")
    return {
        "configuration": config.model_dump(),
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard": dashboard,
        "analytics": analytics,
        "forecast": forecast,
        "anomalies": anomalies,
        "visualizations": visualizations,
        "warnings": warnings,
        "sections": config.enabled_sections,
        "period": {"from": config.start_month, "to": config.end_month,
                   "kind": "calendar_months"} if config.start_month else None,
    }


def preview_report(config: ReportConfiguration) -> dict:
    report = prepare_report(config)
    trend = report["analytics"].get("trend") or {}
    return {
        "title": config.title,
        "source": report["source"], "period": report["period"],
        "sections": report["sections"], "warnings": report["warnings"],
        "kpis": report["dashboard"].get("kpis") or [],
        "trend": {"role": trend.get("role"), "periods": trend.get("periods", 0),
                  "current": trend.get("current"), "previous": trend.get("previous"),
                  "average": trend.get("average"), "change_pct": trend.get("change_pct")},
        "forecast": {"model": (report["forecast"] or {}).get("model"),
                     "confidence": (report["forecast"] or {}).get("confidence"),
                     "samples": ((report["forecast"] or {}).get("validation") or {}).get("samples"),
                     "first": ((report["forecast"] or {}).get("forecast") or [None])[0]},
        "anomaly_count": len((report["anomalies"] or {}).get("anomalies") or []),
        "visualizations": [
            {"id": item["id"], "title": item["title"], "type": item["type"],
             "rows": len(item["data"])} for item in report["visualizations"]
        ],
        "generated_at": report["generated_at"],
        "preview_is_live": True,
    }
