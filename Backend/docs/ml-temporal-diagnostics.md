# Kenneth · Fase 1: ML temporal robusto

## Cobertura

El mismo núcleo estadístico se aplica a series mensuales reconocidas en los diez dominios del modelo semántico: comercio, educación, salud, transporte, hospedaje, restaurantes, servicios profesionales, finanzas, manufactura y recursos humanos. El selector conserva el rol, la tabla, la fecha y la métrica solicitados. Solo calcula importes si existen medidas verificadas; por defecto cuenta registros. También admite cantidades producidas (SUM de la columna quantity en órdenes de producción) y promedio de notas (AVG de value en calificaciones), únicamente cuando la pregunta lo solicita y el mapper confirma las columnas.

## Pronóstico y validación

- Se comparan último valor observado, tendencia lineal, mismo mes del año anterior (referencia), tendencia con estacionalidad anual y un estimador estacional con deriva interanual robusta.
- El modelo de mismo mes del año anterior (seasonal_naive) **solo es una referencia de evaluación y no puede seleccionarse como un pronóstico calculado**. El modelo seasonal_drift combina varias observaciones del mismo mes de años distintos, ajustadas mediante la mediana del cambio interanual, para reducir la dependencia de un único año.
- La estacionalidad se habilita con 26 o más meses consecutivos y orígenes de prueba con al menos 24 meses de entrenamiento.
- Backtesting temporal rolling-origin: para cada origen solo se utilizan fechas anteriores; se evalúan horizontes de 1 a 12 meses. Los candidatos comparten los mismos orígenes y objetivos.
- Selección por MAE y desempate con RMSE; evita seleccionar estacionalidad por mejoras inferiores al 3 % frente al mejor modelo sencillo.
- Se muestran MAE, RMSE, WAPE, R² fuera de entrenamiento cuando sea válido, comparaciones con modelos base y calidad de datos.
- Los rangos inferior y superior usan el percentil 80 del error absoluto histórico: son bandas descriptivas, **no intervalos de confianza calibrados**.
- Los meses ausentes no se rellenan con cero. Se comunican explícitamente y desactivan la evaluación estacional.
- Si ninguno de los modelos calculados supera la referencia de copiar el mismo mes del año anterior, Kenneth informa esa limitación en vez de ocultarla.
- Se entrega la fecha del último mes realmente registrado, el primer/último mes estimado y, para cada estimación, la cifra real del mismo mes del año anterior y su diferencia respecto al estimado.
- Las estimaciones empiezan después del último dato disponible, **no necesariamente después del mes actual**. El API y la interfaz distinguen períodos ya transcurridos, mes actual y períodos realmente futuros. Un histórico atrasado no se etiqueta como pronóstico futuro.
- El campo confidence representa evidencia heurística, no probabilidad de acierto.

## Anomalías ajustadas al calendario

Se estima una tendencia robusta usando medianas de variaciones comparables y efectos mensuales mediante medianas de residuales. Las anomalías son desviaciones materiales respecto al valor esperado para su mes, no simples picos sobre el promedio general. Se comunican magnitud, severidad, referencia y advertencias cuando el historial anual es escaso.

La detección es **retrospectiva** y puede utilizar observaciones posteriores al período evaluado; no constituye backtesting de pronósticos ni un juicio causal.

Cuando **no se supera el umbral de anomalía**, la respuesta igualmente devuelve `review_points` con los tres períodos de mayor desviación absoluta, sin reclasificarlos como alertas, junto a `screening` (umbral absoluto derivado de MAD, mínimo relativo del 20 %, meses evaluados y ajuste anual). La interfaz explica esta ausencia de alertas con lenguaje sencillo y muestra fechas, valores observados y esperados de esos períodos para evitar un panel vacío; la tarjeta deja de estirarse verticalmente por la altura de la columna contigua. No modifica silenciosamente los umbrales para producir falsas alarmas.

Cada anomalía incluye el período explícito como mes/año (`period_iso`, `period_label`, `period_granularity=month`) sin fingir una fecha exacta del evento. `explanation` explica en lenguaje natural el valor observado, el nivel esperado y su desviación. `diagnostic_explanation` resume categorías e indicadores observados en períodos de comparación y señala cuándo falta evidencia. `recommendation` orienta una revisión posterior sin afirmar que se haya demostrado causalidad. Si el valor esperado es cero, no se inventa un porcentaje.

En Predicciones, la tarjeta muestra fecha del mes, interpretación, evidencia y próximos pasos por encima de las estadísticas. La lista de «Valores estimados y referencia anual» tiene altura limitada y desplazamiento vertical independiente, conservando el gráfico y la disposición adaptable de la página. Los mensajes del chatbot también utilizan las explicaciones verificables.

## Investigación de cambios por segmentos

El módulo diagnóstico compara hasta cinco períodos anómalos con el mismo mes del año anterior, o con el mes previo si no existe. Solo agrupa por columnas categóricas reconocidas de la **misma tabla**: estado, tipo, método, origen y destino, si están disponibles.

Se restringe a tres dimensiones por anomalía y cuarenta categorías completas por consulta; desgloses truncados se omiten. No se consulta información personal, texto libre ni identificadores de usuarios. Se presentan cambios observados y límites. De forma adicional se comparan los conteos temporales de hasta seis entidades relacionadas por el mismo dominio, cuando tienen fecha y periodos equivalentes; esas coincidencias están identificadas explícitamente como asociaciones, no como relaciones causales. **Ninguna correlación demuestra por sí sola la causa**. Para atribuciones causales reales se requerirán otros datos verificables y análisis posteriores.

## API e interfaz

Se conservan las respuestas de /api/ai/forecast y /api/ai/anomalies y se agregan validación de modelos, calidad de datos, patrones estacionales, valores esperados y desgloses descriptivos. Las respuestas del pronóstico ahora incluyen forecast_basis, prior_year_total, change_vs_prior_year, period_status y value_kind; se presentan también en la vista, el asistente y los informes PDF. El chatbot y la pantalla Predicciones interpretan estos nuevos campos. La lógica sigue adaptándose a SQL Server, PostgreSQL y Excel convertido a SQLite a través del modelo semántico.

## Pruebas

Ejecutar desde Backend:

- python -m unittest discover -s tests -p 'test_robust_ml.py' -v
- python -m unittest discover -s tests -p 'test_anomaly_narrative.py' -v
- python -m unittest discover -s tests -p 'test_seasonal_forecasting.py' -v
- python -m unittest discover -s tests -p 'test_assistant_prediction_domains.py' -v
- python -m app.quality.run --report-dir quality_reports

Los importes de transacciones financieras pueden ser negativos y no se fuerzan a cero. La suite automatizada utiliza SQLite y datos ficticios; no demuestra exactitud con conexiones reales SQL Server/PostgreSQL, efectos externos, cambios de régimen ni calibración probabilística de intervalos.
