from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.analysis.adaptive_analytics_service import get_adaptive_analytics
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.ml.predictive_service import detect_monthly_anomalies, forecast_next_months


REPORT_TYPES = {
    "executive": "Resumen ejecutivo",
    "analytics": "Reporte analitico",
    "predictive": "Reporte predictivo",
    "complete": "Reporte completo",
}


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _safe_ml() -> tuple[dict | None, dict | None]:
    forecast = None
    anomalies = None
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
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7E1EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header and data:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F6CBD")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    table.setStyle(TableStyle(commands))
    return table


def _add_title(story, styles, title: str, subtitle: str):
    story.append(Paragraph(title, styles["ReportTitle"]))
    story.append(Paragraph(subtitle, styles["ReportSubtitle"]))
    story.append(Spacer(1, 8 * mm))


def _add_section(story, styles, title: str):
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(title, styles["SectionTitle"]))
    story.append(Spacer(1, 2 * mm))


def _add_executive(story, styles, dashboard: dict, analytics: dict):
    _add_section(story, styles, "Resumen ejecutivo")
    source_rows = [
        ["Base de datos", dashboard.get("database") or "-"],
        ["Motor", dashboard.get("provider") or "-"],
        ["Dominio", dashboard.get("domain") or "generic"],
        ["Confianza", _fmt(dashboard.get("domain_confidence"))],
    ]
    story.append(_table([["Campo", "Valor"], *source_rows], widths=[45 * mm, 120 * mm]))
    story.append(Spacer(1, 5 * mm))

    kpis = dashboard.get("kpis") or []
    if kpis:
        story.append(Paragraph("Indicadores principales", styles["SubsectionTitle"]))
        rows = [["Indicador", "Valor", "Tabla"]]
        rows.extend([[str(item.get("role", "")).replace("_", " ").title(), _fmt(item.get("value")), item.get("table") or "-"] for item in kpis])
        story.append(_table(rows, widths=[60 * mm, 35 * mm, 70 * mm]))
        story.append(Spacer(1, 5 * mm))

    trend = analytics.get("trend") or {}
    if trend.get("available"):
        story.append(Paragraph("Comportamiento reciente", styles["SubsectionTitle"]))
        rows = [
            ["Metrica", "Valor"],
            ["Periodo actual", (trend.get("current") or {}).get("period") or "-"],
            ["Actividad actual", _fmt((trend.get("current") or {}).get("total"))],
            ["Cambio vs. periodo anterior", f"{_fmt(trend.get('change_pct'))}%" if trend.get("change_pct") is not None else "-"],
            ["Promedio mensual", _fmt(trend.get("average"))],
            ["Mejor periodo", f"{(trend.get('peak') or {}).get('period', '-')} - {_fmt((trend.get('peak') or {}).get('total'))}"],
            ["Menor periodo", f"{(trend.get('lowest') or {}).get('period', '-')} - {_fmt((trend.get('lowest') or {}).get('total'))}"],
        ]
        story.append(_table(rows, widths=[80 * mm, 85 * mm]))

    insights = analytics.get("insights") or []
    if insights:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Hallazgos automaticos", styles["SubsectionTitle"]))
        for insight in insights[:6]:
            story.append(Paragraph(f"<b>{insight.get('title', 'Insight')}:</b> {insight.get('text', '')}", styles["BodyTextReport"]))
            story.append(Spacer(1, 1.5 * mm))


def _add_analytics(story, styles, analytics: dict):
    _add_section(story, styles, "Analitica del negocio")

    trend = analytics.get("trend") or {}
    points = trend.get("data") or []
    if points:
        story.append(Paragraph("Detalle temporal", styles["SubsectionTitle"]))
        rows = [["Periodo", "Actividad", "Prom. movil 3M", "Acumulado"]]
        for point in points[-12:]:
            rows.append([
                point.get("period") or "-",
                _fmt(point.get("total")),
                _fmt(point.get("rolling_average")),
                _fmt(point.get("cumulative")),
            ])
        story.append(_table(rows, widths=[38 * mm, 42 * mm, 42 * mm, 43 * mm]))
        story.append(Spacer(1, 5 * mm))

    rankings = analytics.get("rankings") or []
    for ranking in rankings:
        story.append(Paragraph(ranking.get("title") or "Ranking", styles["SubsectionTitle"]))
        rows = [["Posicion", "Entidad", "Valor"]]
        for index, item in enumerate(ranking.get("data") or [], start=1):
            rows.append([index, item.get("label") or "-", _fmt(item.get("value"))])
        story.append(_table(rows, widths=[25 * mm, 95 * mm, 45 * mm]))
        story.append(Spacer(1, 4 * mm))

    distributions = analytics.get("distributions") or []
    for distribution in distributions[:4]:
        story.append(Paragraph(f"Distribucion: {distribution.get('label', '-')}", styles["SubsectionTitle"]))
        rows = [["Categoria", "Cantidad"]]
        rows.extend([[item.get("label") or "-", _fmt(item.get("total"))] for item in distribution.get("data") or []])
        story.append(_table(rows, widths=[115 * mm, 50 * mm]))
        story.append(Spacer(1, 4 * mm))

    numeric = analytics.get("numeric_metrics") or []
    if numeric:
        story.append(Paragraph("Metricas secundarias", styles["SubsectionTitle"]))
        rows = [["Entidad", "Metrica", "Total", "Promedio", "Minimo", "Maximo"]]
        for item in numeric[:8]:
            rows.append([
                str(item.get("role", "")).replace("_", " ").title(),
                item.get("metric") or "-",
                _fmt(item.get("total")),
                _fmt(item.get("average")),
                _fmt(item.get("minimum")),
                _fmt(item.get("maximum")),
            ])
        story.append(_table(rows, widths=[35 * mm, 28 * mm, 27 * mm, 27 * mm, 24 * mm, 24 * mm]))


def _add_predictive(story, styles, forecast: dict | None, anomalies: dict | None):
    _add_section(story, styles, "Analisis predictivo")

    if forecast:
        story.append(Paragraph("Pronostico - Regresion lineal", styles["SubsectionTitle"]))
        rows = [["Serie", "Tabla", "Meses entrenamiento", "R2"]]
        rows.append([
            forecast.get("role") or "-",
            forecast.get("table") or "-",
            _fmt(forecast.get("training_months")),
            _fmt(forecast.get("r2_score")),
        ])
        story.append(_table(rows, widths=[45 * mm, 50 * mm, 40 * mm, 30 * mm]))
        story.append(Spacer(1, 3 * mm))
        projection_rows = [["Periodo", "Valor proyectado"]]
        projection_rows.extend([
            [f"{int(item['month']):02d}/{int(item['year'])}", _fmt(item.get("predicted_total"))]
            for item in forecast.get("forecast") or []
        ])
        story.append(_table(projection_rows, widths=[70 * mm, 95 * mm]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(forecast.get("warning") or "", styles["NoteText"]))
    else:
        story.append(Paragraph("No hay suficientes datos para generar un pronostico confiable.", styles["BodyTextReport"]))

    story.append(Spacer(1, 5 * mm))
    if anomalies:
        story.append(Paragraph("Deteccion de anomalias - Isolation Forest", styles["SubsectionTitle"]))
        anomaly_rows = [["Periodo", "Valor", "Severidad", "% vs promedio", "% vs anterior"]]
        for item in anomalies.get("anomalies") or []:
            anomaly_rows.append([
                f"{int(item['month']):02d}/{int(item['year'])}",
                _fmt(item.get("total")),
                item.get("severity") or "-",
                _fmt(item.get("pct_vs_average")),
                _fmt(item.get("pct_vs_previous")),
            ])
        if len(anomaly_rows) == 1:
            anomaly_rows.append(["-", "-", "Sin anomalias relevantes", "-", "-"])
        story.append(_table(anomaly_rows, widths=[32 * mm, 32 * mm, 35 * mm, 33 * mm, 33 * mm]))
    else:
        story.append(Paragraph("No hay suficientes datos para ejecutar la deteccion de anomalias.", styles["BodyTextReport"]))


def generate_report_pdf(report_type: str) -> tuple[bytes, str]:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Tipo de reporte no valido: {report_type}")

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
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="AI Business Assistant",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=27,
        textColor=colors.HexColor("#0F4C81"),
        alignment=TA_CENTER,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5D6B7A"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0F4C81"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SubsectionTitle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#243B53"),
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextReport",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334E68"),
    ))
    styles.add(ParagraphStyle(
        name="NoteText",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#6B7280"),
    ))

    story = []
    _add_title(
        story,
        styles,
        title,
        f"AI Business Assistant | {database} | Generado {generated_at:%d/%m/%Y %H:%M}",
    )

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
        "Reporte generado automaticamente a partir de la base de datos activa. Las predicciones son exploratorias y no constituyen una garantia de resultados futuros.",
        styles["NoteText"],
    ))

    doc.build(story)
    return buffer.getvalue(), filename
