# Kenneth · Fase 2 — Reportes profesionales (issue #4)

## Estado

Primera entrega funcional, desarrollada en `feature/professional-reporting-phase-2`. No implica el cierre del issue: faltan evaluación manual de PDFs en varios navegadores, bases reales (SQL Server/PostgreSQL/Excel), opciones avanzadas de personalización y revisión de diseños con muchos registros.

## Endpoints

- `GET /api/reports/options`: devuelve la fuente activa, plantillas, secciones y visualizaciones guardadas disponibles en esa fuente.
- `POST /api/reports/preview`: presenta la composición del informe, KPIs, tendencia, anomalías y advertencias. La vista previa consulta los datos en ese momento.
- `POST /api/reports/generate`: devuelve un PDF descargable generado con los datos actuales y la misma configuración.
- Se conserva `GET /api/reports/pdf?type=...` para compatibilidad con clientes anteriores.

### Ejemplo de configuración

```json
{
  "report_type": "custom",
  "title": "Resultados de operaciones · 2025",
  "start_month": "2025-01",
  "end_month": "2025-12",
  "sections": ["executive", "analytics", "predictive", "visualizations", "methodology"],
  "visualization_ids": [],
  "horizon": 3,
  "source_key": "<usar exactamente el valor de GET /api/reports/options>"
}
```

Los tipos de reporte admitidos son `executive`, `analytics`, `predictive`, `complete` y `custom`. Las secciones se activan por separado. Si se omite `sections`, se utiliza la composición predeterminada del tipo escogido.

Los campos `start_month` y `end_month` representan meses completos e inclusivos, formato `AAAA-MM`; deben enviarse ambos o ninguno. Se permite un máximo de 120 meses por selección y hasta 8 visualizaciones. El horizonte predictivo es de 1 a 12 meses. El `source_key` evita reutilizar una configuración si se cambia a otra fuente activa.

## Integridad de cifras y períodos

En informes con período, los KPIs solo se computan a partir de entidades cuyo campo de fecha está reconocido por el modelo semántico. Para las consultas por fecha se utiliza el intervalo semiabierto `[primer día del mes inicial, primer día del mes siguiente al final)`, compatible con datos con horas.

La tendencia también se filtra y se recalculan sus indicadores (promedio, máximo, variación, total). Los rankings, distribuciones e indicadores numéricos de la analítica anterior son **globales**; como sus consultas no implementan alcance de fechas, se omiten en un informe filtrado con una advertencia, nunca se presentan como si fuesen datos de ese período.

Las anomalías utilizan el historial completo para aprender una referencia estacional pero, cuando se escoge un rango descriptivo, solo se incluyen alertas dentro de los meses escogidos. Los pronósticos también se entrenan sobre todo el historial verificable y empiezan después del último dato real; se explicita que no dependen del rango descriptivo.

## Gráficas guardadas

El sistema recupera exclusivamente visualizaciones asociadas a la fuente activa. Mantiene la definición validada (tipo, tabla, métrica, agregación, dimensión y filtros) y obtiene una instantánea de sus datos al generar el informe. En un informe con rango, solo agrega filtros de fecha cuando puede identificar una columna de fecha inequívoca en la tabla y la visualización no mezcla entidades cuya relación temporal sería dudosa. En los demás casos, se omite la gráfica con una advertencia específica.

Se admiten KPIs, barras, líneas, distribución tipo dona y tablas; se incluyen aclaraciones de ejes X/Y. La versión actual conserva los primeros registros de la consulta de vista previa, hasta los límites seguros del motor de visualizaciones.

## Interpretación responsable

Una cifra observada, una referencia del año anterior y una proyección no son equivalentes. Las conclusiones derivan de KPIs y tendencias verificadas. No se infieren causas por simple correlación. La página de metodología registra fuente, períodos y advertencias.

**Limitaciones conocidas**: la conexión activa sigue estando administrada globalmente (refactorización prevista para Fase 4); aún no hay transacciones de lectura consistentes entre todas las consultas de un informe, ni selección de otra fuente diferente de la activa. La previsualización y la descarga pueden reflejar instantes distintos y se indican como consultas en vivo. No se ofrecen diagnósticos causales.

## Pruebas

Desde `Backend`:

```bash
python -m unittest discover -s tests -p 'test_professional_reports.py' -v
python -m app.quality.run --report-dir quality_reports
```

La CI también valida el frontend mediante `npm run lint` y `npm run build`, y mantiene la batería ML de la Fase 1. Las pruebas del nuevo módulo usan ejemplos sintéticos y SQLite para cubrir validación de configuraciones, fechas, fuentes y visualizaciones, múltiples dominios semánticos y la construcción de un PDF válido. Antes de cerrar la fase deben realizarse pruebas visuales y funcionales con fuentes reales.
