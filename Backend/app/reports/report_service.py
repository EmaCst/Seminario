from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.analysis.adaptive_analytics_service import get_adaptive_analytics
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.ml.predictive_service import detect_monthly_anomalies, forecast_next_months

REPORT_TYPES = {
    "executive": "Resumen ejecutivo",
    "analytics": "Reporte analítico",
    "predictive": "Reporte predictivo",
    "complete": "Reporte completo",
}

ROLE_LABELS = {
    "sales": "ventas", "sales_details": "detalle de ventas", "customers": "clientes",
    "products": "productos", "payments": "pagos", "inventory": "inventario",
    "students": "estudiantes", "teachers": "docentes", "courses": "cursos",
    "enrollments": "inscripciones", "grades": "calificaciones", "attendance": "asistencia",
    "patients": "pacientes", "doctors": "médicos", "appointments": "citas",
}

BLUE = colors.HexColor("#0F6CBD")
DARK_BLUE = colors.HexColor("#0F4C81")
TEXT = colors.HexColor("#334E68")
MUTED = colors.HexColor("#6B7280")
GRID = colors.HexColor("#D7E1EC")
LIGHT = colors.HexColor("#EEF5FB")
GREEN = colors.HexColor("#16803A")
ORANGE = colors.HexColor("#D97706")
PURPLE = colors.HexColor("#7C3AED")


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{int(value):,}" if value.is_integer() else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _role(role: str | None) -> str:
    if not role:
        return "actividad"
    return ROLE_LABELS.get(role, role.replace("_", " "))


def _safe_ml() -> tuple[dict | None, dict | None]:
    forecast = anomalies = None
    try:
        forecast = forecast_next_months(horizon=3)
    except Exception:
        pass
    try:
        anomalies = detect_monthly_anomalies()
    except Exception:
        pass
    return forecast, anomalies


def _table(data, widths=None, header=True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header and data:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    table.setStyle(TableStyle(commands))
    return table


def _kpi_table(dashboard: dict) -> Table | None:
    kpis = dashboard.get("kpis") or []
    if not kpis:
        return None
    cells = []
    label_style = ParagraphStyle("KpiLabel", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, alignment=TA_CENTER)
    value_style = ParagraphStyle("KpiValue", fontName="Helvetica-Bold", fontSize=18, textColor=DARK_BLUE, alignment=TA_CENTER)
    for item in kpis[:4]:
        cells.append(Table([
            [Paragraph(_role(item.get("role")).title(), label_style)],
            [Paragraph(_fmt(item.get("value")), value_style)],
        ], colWidths=[39 * mm], rowHeights=[8 * mm, 13 * mm]))
    row = Table([cells], colWidths=[41 * mm] * len(cells))
    row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return row


def _trend_chart(points: list[dict], title: str = "Evolución mensual") -> Drawing | None:
    if not points:
        return None
    points = points[-12:]
    labels = [str(point.get("period") or "") for point in points]
    totals = [float(point.get("total") or 0) for point in points]
    rolling = [float(point.get("rolling_average") or 0) for point in points]
    drawing = Drawing(470, 205)
    drawing.add(String(10, 188, title, fontName="Helvetica-Bold", fontSize=11, fillColor=TEXT))
    chart = HorizontalLineChart()
    chart.x, chart.y, chart.width, chart.height = 42, 38, 405, 130
    chart.data = [totals, rolling]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 6.8
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.dy = -7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.gridStrokeColor = GRID
    chart.valueAxis.gridStrokeWidth = 0.4
    chart.lines[0].strokeColor = BLUE
    chart.lines[0].strokeWidth = 2.2
    chart.lines[1].strokeColor = ORANGE
    chart.lines[1].strokeWidth = 1.6
    chart.lines[1].strokeDashArray = [5, 3]
    drawing.add(chart)
    drawing.add(String(300, 184, "Actividad", fontName="Helvetica", fontSize=7.5, fillColor=BLUE))
    drawing.add(String(365, 184, "Prom. móvil 3M", fontName="Helvetica", fontSize=7.5, fillColor=ORANGE))
    return drawing


def _ranking_chart(ranking: dict) -> Drawing | None:
    rows = (ranking.get("data") or [])[:5]
    if not rows:
        return None
    labels = [str(item.get("label") or "-")[:24] for item in rows][::-1]
    values = [float(item.get("value") or 0) for item in rows][::-1]
    drawing = Drawing(470, 190)
    drawing.add(String(10, 174, ranking.get("title") or "Ranking", fontName="Helvetica-Bold", fontSize=11, fillColor=TEXT))
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 105, 28, 335, 125
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7.5
    chart.categoryAxis.labels.boxAnchor = "e"
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.gridStrokeColor = GRID
    chart.valueAxis.gridStrokeWidth = 0.4
    chart.bars[0].fillColor = BLUE
    chart.bars[0].strokeColor = BLUE
    drawing.add(chart)
    return drawing


def _distribution_chart(distribution: dict) -> Drawing | None:
    rows = distribution.get("data") or []
    if not rows or len(rows) > 6:
        return None
    values = [float(item.get("total") or 0) for item in rows]
    if sum(values) <= 0:
        return None
    drawing = Drawing(250, 175)
    drawing.add(String(6, 160, distribution.get("label") or "Distribución", fontName="Helvetica-Bold", fontSize=10, fillColor=TEXT))
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 25, 18, 105, 105
    pie.data = values
    pie.labels = [str(item.get("label") or "-")[:18] for item in rows]
    palette = [BLUE, GREEN, ORANGE, PURPLE, colors.HexColor("#0EA5E9"), colors.HexColor("#DC2626")]
    for index in range(len(values)):
        pie.slices[index].fillColor = palette[index % len(palette)]
        pie.slices[index].strokeColor = colors.white
        pie.slices[index].fontSize = 6.5
    drawing.add(pie)
    return drawing


def _forecast_chart(forecast: dict) -> Drawing | None:
    historical = forecast.get("training_points") or []
    projected = forecast.get("forecast") or []
    if not historical or not projected:
        return None
    historical = historical[-8:]
    labels = [f"{int(item['month']):02d}/{str(item['year'])[-2:]}" for item in historical]
    labels += [f"{int(item['month']):02d}/{str(item['year'])[-2:]}" for item in projected]
    hist_values = [float(item.get("total") or 0) for item in historical]
    last_value = hist_values[-1]
    hist_series = hist_values + [None] * len(projected)
    pred_series = [None] * (len(hist_values) - 1) + [last_value] + [float(item.get("predicted_total") or 0) for item in projected]
    drawing = Drawing(470, 205)
    drawing.add(String(10, 188, "Histórico y proyección", fontName="Helvetica-Bold", fontSize=11, fillColor=TEXT))
    chart = HorizontalLineChart()
    chart.x, chart.y, chart.width, chart.height = 42, 38, 405, 130
    chart.data = [hist_series, pred_series]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -5
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.gridStrokeColor = GRID
    chart.valueAxis.gridStrokeWidth = 0.4
    chart.lines[0].strokeColor = BLUE
    chart.lines[0].strokeWidth = 2.2
    chart.lines[1].strokeColor = PURPLE
    chart.lines[1].strokeWidth = 2
    chart.lines[1].strokeDashArray = [5, 3]
    drawing.add(chart)
    drawing.add(String(315, 184, "Histórico", fontName="Helvetica", fontSize=7.5, fillColor=BLUE))
    drawing.add(String(375, 184, "Proyección", fontName="Helvetica", fontSize=7.5, fillColor=PURPLE))
    return drawing


def _add_title(story, styles, title: str, subtitle: str):
    story.append(Paragraph(title, styles["ReportTitle"]))
    story.append(Paragraph(subtitle, styles["ReportSubtitle"]))
    story.append(Spacer(1, 6 * mm))


def _add_section(story, styles, title: str):
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(title, styles["SectionTitle"]))
    story.append(Spacer(1, 2 * mm))


def _executive_narrative(dashboard: dict, analytics: dict) -> list[str]:
    trend = analytics.get("trend") or {}
    current, previous = trend.get("current") or {}, trend.get("previous") or {}
    change, peak, lowest = trend.get("change_pct"), trend.get("peak") or {}, trend.get("lowest") or {}
    role = _role(trend.get("role"))
    paragraphs = []
    if trend.get("available"):
        if change is not None and previous:
            direction = "creció" if change >= 0 else "disminuyó"
            current_total = float(current.get("total") or 0)
            average = float(trend.get("average") or 0)
            paragraphs.append(
                f"Durante {current.get('period', 'el período más reciente')}, la actividad de {role} alcanzó {_fmt(current_total)} registros y {direction} "
                f"{abs(float(change)):.1f}% frente a {previous.get('period', 'el período anterior')}. El nivel actual se ubica "
                f"{'por encima' if current_total >= average else 'por debajo'} del promedio mensual histórico de {_fmt(average)}."
            )
        if peak and lowest:
            paragraphs.append(
                f"El punto más alto del historial visible ocurrió en {peak.get('period')} con {_fmt(peak.get('total'))}, mientras que el menor nivel se registró "
                f"en {lowest.get('period')} con {_fmt(lowest.get('total'))}. Esta diferencia permite dimensionar la variabilidad operativa del negocio."
            )
    rankings = analytics.get("rankings") or []
    if rankings and rankings[0].get("data"):
        rows = rankings[0]["data"]
        total_top = sum(float(item.get("value") or 0) for item in rows)
        leader = rows[0]
        share = float(leader.get("value") or 0) / total_top * 100 if total_top else 0
        paragraphs.append(
            f"En {rankings[0].get('title', 'el ranking principal').lower()}, {leader.get('label')} ocupa la primera posición con {_fmt(leader.get('value'))}. "
            f"Dentro del top {len(rows)}, concentra aproximadamente {share:.1f}% del valor acumulado."
        )
    return paragraphs


def _analytics_narrative(analytics: dict) -> list[str]:
    paragraphs = []
    trend = analytics.get("trend") or {}
    if trend.get("available"):
        current, peak = trend.get("current") or {}, trend.get("peak") or {}
        average = float(trend.get("average") or 0)
        current_total = float(current.get("total") or 0)
        if average:
            deviation = ((current_total - average) / average) * 100
            paragraphs.append(
                f"El último período analizado ({current.get('period')}) cerró con {_fmt(current_total)} registros, "
                f"{abs(deviation):.1f}% {'por encima' if deviation >= 0 else 'por debajo'} del promedio mensual de {_fmt(average)}. "
                f"El máximo observado fue {peak.get('period')} con {_fmt(peak.get('total'))}."
            )
    for ranking in (analytics.get("rankings") or [])[:2]:
        rows = ranking.get("data") or []
        if len(rows) >= 2:
            first, second = float(rows[0].get("value") or 0), float(rows[1].get("value") or 0)
            gap = first - second
            extra = f", una brecha de {(gap / second * 100):.1f}% respecto al segundo lugar" if second else ""
            paragraphs.append(
                f"En “{ranking.get('title')}”, {rows[0].get('label')} lidera con {_fmt(first)} y supera a {rows[1].get('label')} por {_fmt(gap)}{extra}."
            )
    for distribution in (analytics.get("distributions") or [])[:2]:
        rows = distribution.get("data") or []
        if rows:
            total = sum(float(item.get("total") or 0) for item in rows)
            leader = rows[0]
            share = float(leader.get("total") or 0) / total * 100 if total else 0
            paragraphs.append(
                f"La distribución de {str(distribution.get('label') or 'categorías').lower()} está encabezada por {leader.get('label')}, "
                f"con {share:.1f}% de los registros considerados."
            )
    return paragraphs[:5]


def _quality_label(r2) -> str:
    if not isinstance(r2, (int, float)):
        return "no evaluada"
    if r2 >= 0.75:
        return "alta"
    if r2 >= 0.50:
        return "media"
    if r2 >= 0.25:
        return "baja"
    return "muy baja"


def _predictive_narrative(forecast: dict | None, anomalies: dict | None) -> list[str]:
    paragraphs = []
    if forecast and forecast.get("forecast"):
        projected = forecast["forecast"]
        first, last = projected[0], projected[-1]
        r2 = forecast.get("r2_score")
        paragraphs.append(
            f"El modelo de regresión lineal proyecta {_fmt(first.get('predicted_total'))} para {int(first['month']):02d}/{first['year']} y "
            f"{_fmt(last.get('predicted_total'))} para {int(last['month']):02d}/{last['year']}. La calidad de ajuste es {_quality_label(r2)}"
            + (f" (R²={float(r2):.2f})" if isinstance(r2, (int, float)) else "")
            + ", por lo que la proyección debe interpretarse como una tendencia orientativa y no como una certeza."
        )
    if anomalies:
        rows = anomalies.get("anomalies") or []
        if rows:
            strongest = max(rows, key=lambda item: abs(float(item.get("pct_vs_average") or 0)))
            paragraphs.append(
                f"Se detectaron {len(rows)} período(s) atípico(s). El caso más relevante fue {int(strongest['month']):02d}/{strongest['year']}, "
                f"con {_fmt(strongest.get('total'))} registros, {abs(float(strongest.get('pct_vs_average') or 0)):.1f}% "
                f"{'por encima' if float(strongest.get('pct_vs_average') or 0) >= 0 else 'por debajo'} del promedio habitual. "
                f"Su severidad fue {strongest.get('severity') or 'no determinada'}."
            )
            if strongest.get("reason"):
                paragraphs.append(str(strongest.get("reason")))
        else:
            paragraphs.append("El detector de anomalías no identificó meses que se alejen de forma relevante del patrón histórico disponible.")
    return paragraphs


def _add_narrative(story, styles, paragraphs: list[str], title: str):
    if not paragraphs:
        return
    story.append(Paragraph(title, styles["SubsectionTitle"]))
    for text in paragraphs:
        story.append(Paragraph(text, styles["BodyTextReport"]))
        story.append(Spacer(1, 2 * mm))


def _add_executive(story, styles, dashboard: dict, analytics: dict):
    _add_section(story, styles, "Resumen ejecutivo")
    story.append(Paragraph(
        f"Este reporte resume el comportamiento de la base <b>{dashboard.get('database') or '-'}</b>, identificada como dominio "
        f"<b>{dashboard.get('domain') or 'generic'}</b> sobre <b>{dashboard.get('provider') or '-'}</b>. El objetivo es explicar qué está ocurriendo "
        "en el negocio y complementar los indicadores con una lectura ejecutiva.",
        styles["BodyTextReport"],
    ))
    story.append(Spacer(1, 4 * mm))
    kpi = _kpi_table(dashboard)
    if kpi:
        story.append(kpi)
        story.append(Spacer(1, 5 * mm))
    _add_narrative(story, styles, _executive_narrative(dashboard, analytics), "Interpretación general")
    chart = _trend_chart((analytics.get("trend") or {}).get("data") or [])
    if chart:
        story.append(chart)
    insights = analytics.get("insights") or []
    if insights:
        story.append(Paragraph("Hallazgos destacados", styles["SubsectionTitle"]))
        for insight in insights[:5]:
            story.append(Paragraph(f"<b>{insight.get('title', 'Insight')}:</b> {insight.get('text', '')}", styles["BodyTextReport"]))
            story.append(Spacer(1, 1.5 * mm))


def _add_analytics(story, styles, analytics: dict):
    _add_section(story, styles, "Analítica del negocio")
    _add_narrative(story, styles, _analytics_narrative(analytics), "Qué muestran los datos")
    trend = analytics.get("trend") or {}
    points = trend.get("data") or []
    chart = _trend_chart(points, "Actividad mensual y promedio móvil")
    if chart:
        story.append(chart)
        story.append(Spacer(1, 4 * mm))
    rankings = analytics.get("rankings") or []
    if rankings:
        story.append(Paragraph("Rankings principales", styles["SubsectionTitle"]))
        for ranking in rankings[:2]:
            rank_chart = _ranking_chart(ranking)
            if rank_chart:
                story.append(rank_chart)
            rows = ranking.get("data") or []
            if rows:
                total_top = sum(float(item.get("value") or 0) for item in rows)
                leader = rows[0]
                share = float(leader.get("value") or 0) / total_top * 100 if total_top else 0
                story.append(Paragraph(
                    f"<b>{leader.get('label')}</b> lidera este ranking con {_fmt(leader.get('value'))} y representa aproximadamente {share:.1f}% "
                    f"del valor acumulado dentro del top {len(rows)}.", styles["BodyTextReport"]
                ))
                story.append(Spacer(1, 3 * mm))
    distributions = analytics.get("distributions") or []
    drawings = [chart for item in distributions[:4] if (chart := _distribution_chart(item)) is not None][:2]
    if drawings:
        story.append(Paragraph("Composición de datos", styles["SubsectionTitle"]))
        chart_table = Table([drawings], colWidths=[82 * mm] * len(drawings), hAlign="LEFT")
        chart_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(chart_table)
        story.append(Spacer(1, 3 * mm))
    numeric = analytics.get("numeric_metrics") or []
    if numeric:
        story.append(Paragraph("Indicadores numéricos complementarios", styles["SubsectionTitle"]))
        rows = [["Indicador", "Total", "Promedio", "Mínimo", "Máximo"]]
        for item in numeric[:6]:
            rows.append([
                f"{_role(item.get('role')).title()} · {item.get('metric') or '-'}",
                _fmt(item.get("total")), _fmt(item.get("average")), _fmt(item.get("minimum")), _fmt(item.get("maximum")),
            ])
        story.append(_table(rows, widths=[55 * mm, 30 * mm, 30 * mm, 25 * mm, 25 * mm]))
        story.append(Spacer(1, 4 * mm))
    if points:
        story.append(Paragraph("Detalle histórico", styles["SubsectionTitle"]))
        rows = [["Período", "Actividad", "Prom. móvil 3M", "Acumulado"]]
        for point in points[-12:]:
            rows.append([point.get("period") or "-", _fmt(point.get("total")), _fmt(point.get("rolling_average")), _fmt(point.get("cumulative"))])
        story.append(_table(rows, widths=[38 * mm, 42 * mm, 42 * mm, 43 * mm]))


def _add_predictive(story, styles, forecast: dict | None, anomalies: dict | None):
    _add_section(story, styles, "Análisis predictivo")
    _add_narrative(story, styles, _predictive_narrative(forecast, anomalies), "Interpretación del modelo")
    if forecast:
        chart = _forecast_chart(forecast)
        if chart:
            story.append(chart)
            story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Proyección de próximos períodos", styles["SubsectionTitle"]))
        rows = [["Período", "Valor proyectado"]]
        rows += [[f"{int(item['month']):02d}/{int(item['year'])}", _fmt(item.get("predicted_total"))] for item in forecast.get("forecast") or []]
        story.append(_table(rows, widths=[70 * mm, 95 * mm]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Calidad de ajuste: <b>{_quality_label(forecast.get('r2_score')).title()}</b> · R² = {_fmt(forecast.get('r2_score'))}. "
            f"{forecast.get('warning') or ''}", styles["NoteText"]
        ))
    else:
        story.append(Paragraph("No hay suficientes datos para generar un pronóstico confiable.", styles["BodyTextReport"]))
    story.append(Spacer(1, 5 * mm))
    if anomalies:
        story.append(Paragraph("Períodos atípicos detectados", styles["SubsectionTitle"]))
        rows = [["Período", "Valor", "Severidad", "% vs promedio", "% vs anterior"]]
        rows += [[f"{int(item['month']):02d}/{int(item['year'])}", _fmt(item.get("total")), item.get("severity") or "-", _fmt(item.get("pct_vs_average")), _fmt(item.get("pct_vs_previous"))] for item in anomalies.get("anomalies") or []]
        if len(rows) == 1:
            rows.append(["-", "-", "Sin anomalías relevantes", "-", "-"])
        story.append(_table(rows, widths=[32 * mm, 32 * mm, 35 * mm, 33 * mm, 33 * mm]))
    else:
        story.append(Paragraph("No hay suficientes datos para ejecutar la detección de anomalías.", styles["BodyTextReport"]))


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRID)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "AI Business Assistant · Reporte automático")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def generate_report_pdf(report_type: str) -> tuple[bytes, str]:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Tipo de reporte no válido: {report_type}")
    dashboard = get_adaptive_dashboard_summary()
    analytics = get_adaptive_analytics()
    forecast = anomalies = None
    if report_type in {"predictive", "complete"}:
        forecast, anomalies = _safe_ml()
    buffer = BytesIO()
    generated_at = datetime.now().astimezone()
    title = REPORT_TYPES[report_type]
    database = dashboard.get("database") or "database"
    filename = f"{report_type}_{str(database).replace(' ', '_')}_{generated_at:%Y%m%d_%H%M}.pdf"
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm, title=title, author="AI Business Assistant",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], fontSize=9.5, leading=13, textColor=MUTED, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=DARK_BLUE, spaceAfter=4))
    styles.add(ParagraphStyle(name="SubsectionTitle", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#243B53"), spaceAfter=5))
    styles.add(ParagraphStyle(name="BodyTextReport", parent=styles["BodyText"], fontSize=9.5, leading=14.5, textColor=TEXT, spaceAfter=2))
    styles.add(ParagraphStyle(name="NoteText", parent=styles["BodyText"], fontSize=8.3, leading=12, textColor=MUTED))
    story = []
    _add_title(story, styles, title, f"AI Business Assistant | {database} | Generado {generated_at:%d/%m/%Y %H:%M}")
    if report_type in {"executive", "complete"}:
        _add_executive(story, styles, dashboard, analytics)
    if report_type == "complete":
        story.append(PageBreak())
    if report_type in {"analytics", "complete"}:
        _add_analytics(story, styles, analytics)
    if report_type == "complete":
        story.append(PageBreak())
    if report_type in {"predictive", "complete"}:
        _add_predictive(story, styles, forecast, anomalies)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Este documento fue generado automáticamente a partir de la base de datos activa. Los análisis describen patrones observados en los datos disponibles; "
        "las predicciones son exploratorias y no constituyen una garantía de resultados futuros.", styles["NoteText"]
    ))
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue(), filename
