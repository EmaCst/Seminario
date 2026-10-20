"""Professional PDF rendering of a prepared, auditable report snapshot."""
from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
import re

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.reports.report_configuration import ReportConfiguration, prepare_report, SECTION_NAMES
from app.reports.report_service import (
    BLUE, DARK_BLUE, GRID, MUTED, PURPLE, TEXT,
    _add_analytics, _add_executive, _add_predictive,
    _add_section, _fmt, _page_footer, _ranking_chart,
    _distribution_chart, _table,
)


def _safe(value, max_length: int = 400) -> str:
    return escape(str(value if value is not None else "-")[:max_length])


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"], fontSize=25, leading=30,
        fontName="Helvetica-Bold", textColor=DARK_BLUE, alignment=TA_CENTER,
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontSize=20, leading=25,
        fontName="Helvetica-Bold", textColor=DARK_BLUE, alignment=TA_CENTER,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontSize=10, leading=15,
        textColor=MUTED, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=15, leading=20, textColor=DARK_BLUE, spaceAfter=6, keepWithNext=1,
    ))
    styles.add(ParagraphStyle(
        name="SubsectionTitle", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11, leading=15, textColor=TEXT, spaceAfter=6, keepWithNext=1,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextReport", parent=styles["BodyText"], fontSize=9.3,
        leading=14.5, textColor=TEXT, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="NoteText", parent=styles["BodyText"], fontSize=8.3, leading=12,
        textColor=MUTED, spaceAfter=3,
    ))
    return styles


def _paragraph(story, styles, content, style="BodyTextReport"):
    story.append(Paragraph(_safe(content, 1600), styles[style]))


def _saved_line(rows: list[dict], title: str) -> Drawing | None:
    values, labels = [], []
    for row in rows[:12]:
        try:
            values.append(float(row["value"]))
            labels.append(str(row.get("dimension", "-"))[:13])
        except (ValueError, TypeError, KeyError):
            continue
    if not values:
        return None
    drawing = Drawing(470, 184)
    drawing.add(String(10, 173, str(title)[:75], fontName="Helvetica-Bold",
                       fontSize=11, fillColor=TEXT))
    chart = HorizontalLineChart()
    chart.x, chart.y, chart.width, chart.height = 54, 35, 385, 118
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -7
    chart.valueAxis.valueMin = min(0, min(values))
    chart.valueAxis.valueMax = max(max(values), 1)
    chart.valueAxis.labels.fontSize = 7
    chart.lines[0].strokeColor = BLUE
    chart.lines[0].strokeWidth = 2.2
    drawing.add(chart)
    return drawing


def _add_visualizations(story, styles, items: list[dict]):
    _add_section(story, styles, "Visualizaciones guardadas")
    if not items:
        _paragraph(story, styles, "No se incluyeron visualizaciones disponibles para esta selección.")
        return
    for item in items:
        title = str(item["title"])[:100]
        _paragraph(story, styles, title, "SubsectionTitle")
        definition = item["definition"]
        metric = definition.get("metric")
        aggregation = definition.get("aggregation", "count")
        y_label = ("Cantidad de registros" if aggregation == "count"
                   else f"{aggregation.upper()} de {metric or 'valor'}")
        x_label = definition.get("group_by") or "Categoría"
        rows = item["data"]
        chart_type = item["type"]
        if chart_type == "kpi":
            _paragraph(story, styles, f"Resultado: {_fmt(rows[0].get('value')) if rows else '-'}")
        elif chart_type == "table":
            headings = ["Dimensión", "Valor"] if "dimension" in rows[0] else ["Valor"]
            cells = [headings]
            for row in rows[:30]:
                if "dimension" in row:
                    cells.append([str(row.get("dimension", "-"))[:65], _fmt(row.get("value"))])
                else:
                    cells.append([_fmt(row.get("value"))])
            story.append(_table(cells, widths=[110 * mm, 55 * mm] if len(headings) == 2 else [165 * mm]))
        else:
            chart = None
            if chart_type == "line":
                chart = _saved_line(rows, title)
            elif chart_type == "bar":
                chart = _ranking_chart({
                    "title": title,
                    "data": [{"label": str(row.get("dimension", "-")),
                              "value": row.get("value", 0)} for row in rows[:10]],
                }) if all(float(row.get("value") or 0) >= 0 for row in rows) else None
            elif chart_type == "donut":
                chart = _distribution_chart({
                    "label": title,
                    "data": [{"label": row.get("dimension", "-"),
                              "total": row.get("value", 0)} for row in rows[:6]],
                })
            if chart is not None:
                story.append(chart)
            else:
                _paragraph(
                    story, styles,
                    "No fue posible mostrar esta gráfica sin distorsionar los valores. "
                    "Los datos pueden examinarse en la vista de Kenneth.",
                    "NoteText",
                )
        if chart_type == "bar":
            _paragraph(story, styles, f"Eje X: {y_label}  |  Eje Y: {x_label}", "NoteText")
            if len(rows) > 5:
                _paragraph(story, styles,
                           f"La gráfica muestra las primeras 5 de {len(rows)} categorías consultadas.",
                           "NoteText")
        elif chart_type == "line":
            _paragraph(story, styles, f"Eje X: {x_label}  |  Eje Y: {y_label}", "NoteText")
            if len(rows) > 12:
                _paragraph(story, styles,
                           f"La gráfica muestra los primeros 12 de {len(rows)} puntos consultados.",
                           "NoteText")
        elif chart_type == "donut":
            _paragraph(story, styles, f"Categoría: {x_label}  |  Valor: {y_label}", "NoteText")
            if len(rows) > 6:
                _paragraph(story, styles,
                           f"La distribución muestra las primeras 6 de {len(rows)} categorías consultadas.",
                           "NoteText")
        filters = definition.get("filters") or []
        if filters:
            _paragraph(story, styles,
                       f"Filtros aplicados: {len(filters)} (incluido el período si se seleccionó).",
                       "NoteText")
        story.append(Spacer(1, 5 * mm))


def _add_methodology(story, styles, snapshot: dict):
    _add_section(story, styles, "Metodología y limitaciones")
    source = snapshot["source"]
    period = snapshot["period"]
    _paragraph(story, styles,
               f"Origen de datos: {source['provider']} / {source['database']}.")
    if period:
        _paragraph(story, styles,
                   f"Período descriptivo: de {period['from']} a {period['to']} "
                   "(meses calendario completos e inclusivos).")
    else:
        _paragraph(story, styles, "Período descriptivo: historial disponible sin filtro temporal.")
    _paragraph(story, styles,
               "Los indicadores se calculan con las tablas y columnas verificadas del "
               "modelo semántico activo. Los datos ausentes no se sustituyen con cifras inventadas.")
    if "predictive" in snapshot["sections"]:
        _paragraph(story, styles,
                   "Los pronósticos se entrenan sobre el historial disponible y "
                   "se contrastan con modelos de referencia mediante validación temporal. "
                   "No son datos observados ni garantías futuras. Las anomalías se "
                   "evalúan retrospectivamente; las coincidencias por categorías no prueban causalidad.")
    for warning in snapshot["warnings"]:
        _paragraph(story, styles, f"Advertencia: {warning}", "NoteText")


def render_report_snapshot(snapshot: dict) -> tuple[bytes, str]:
    """Render exactly one prepared source snapshot; tests can inject synthetic data."""
    config = ReportConfiguration.model_validate(snapshot["configuration"])
    styles = _styles()
    generated = datetime.fromisoformat(snapshot["generated_at"])
    source = snapshot["source"]
    safe_db = re.sub(r"[^a-zA-Z0-9_-]", "_", str(source.get("database") or "fuente"))[:55]
    filename = f"kenneth_{config.report_type}_{safe_db}_{generated:%Y%m%d_%H%M}.pdf"
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=config.title, author=config.author_name.strip() or "Kenneth - AI Business Assistant",
    )
    story = []
    cover = []
    cover.append(Spacer(1, 48 * mm))
    _paragraph(cover, styles, "KENNETH / BUSINESS INTELLIGENCE", "ReportSubtitle")
    cover.append(Spacer(1, 8 * mm))
    _paragraph(cover, styles, config.title, "CoverTitle")
    if config.author_name.strip():
        cover.append(Spacer(1, 4 * mm))
        _paragraph(cover, styles, f"Elaborado por: {config.author_name.strip()}", "ReportSubtitle")
    _paragraph(cover, styles, f"{source.get('database')} | {source.get('provider')}", "ReportSubtitle")
    period = snapshot.get("period")
    _paragraph(cover, styles,
               f"Período: {period['from']} a {period['to']}" if period else "Período: historial disponible",
               "ReportSubtitle")
    cover.append(Spacer(1, 15 * mm))
    _paragraph(cover, styles, f"Generado: {generated:%d/%m/%Y %H:%M} UTC", "ReportSubtitle")
    cover.append(Spacer(1, 20 * mm))
    _paragraph(cover, styles,
               "Contenido: " + " · ".join(SECTION_NAMES.get(section, section)
                                         for section in snapshot["sections"]), "NoteText")
    # Keep the entire cover on one sheet even when a title or author wraps.
    # Otherwise an overflow followed by an explicit PageBreak can produce
    # a nearly empty intervening sheet.
    story.append(KeepInFrame(165 * mm, 225 * mm, cover, mode="shrink", hAlign="CENTER"))
    story.append(PageBreak())

    sections = snapshot["sections"]
    if "executive" in sections:
        _add_executive(story, styles, snapshot["dashboard"], snapshot["analytics"])
    if "analytics" in sections:
        # Avoid unconditional PageBreak: when the preceding section already
        # reached a page boundary, another break can create an empty page.
        # CondPageBreak only advances if the next heading/content cannot fit.
        story.append(CondPageBreak(80 * mm))
        _add_analytics(story, styles, snapshot["analytics"])
    if "predictive" in sections:
        if any(item in sections for item in ("executive", "analytics")):
            story.append(CondPageBreak(80 * mm))
        _add_predictive(story, styles, snapshot["forecast"], snapshot["anomalies"])
    if "visualizations" in sections:
        if any(item in sections for item in ("executive", "analytics", "predictive")):
            story.append(CondPageBreak(80 * mm))
        _add_visualizations(story, styles, snapshot["visualizations"])
    if "methodology" in sections:
        _add_methodology(story, styles, snapshot)
    if "methodology" not in sections and snapshot["warnings"]:
        _add_section(story, styles, "Advertencias de alcance")
        for warning in snapshot["warnings"]:
            _paragraph(story, styles, warning, "NoteText")

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue(), filename


def generate_configured_report(config: ReportConfiguration) -> tuple[bytes, str]:
    return render_report_snapshot(prepare_report(config))
