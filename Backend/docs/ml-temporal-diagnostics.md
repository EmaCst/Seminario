# Kenneth · Fase 1: ML temporal robusto

## Cobertura

El mismo núcleo estadístico se aplica a series mensuales reconocidas en los diez dominios del modelo semántico: comercio, educación, salud, transporte, hospedaje, restaurantes, servicios profesionales, finanzas, manufactura y recursos humanos. El selector conserva el rol, la tabla, la fecha y la métrica solicitados. Solo calcula importes si existen medidas verificadas; por defecto cuenta registros. También admite cantidades producidas (SUM de la columna quantity en órdenes de producción) y promedio de notas (AVG de value en calificaciones), únicamente cuando la pregunta lo solicita y el mapper confirma las columnas.

## Pronóstico y validación

- Compiten modelos de último valor observado, tendencia lineal, mismo mes del año anterior y tendencia con estacionalidad anual.
- La estacionalidad se habilita con 26 o más meses consecutivos y orígenes de prueba con al menos 24 meses de entrenamiento.
- Backtesting temporal rolling-origin: para cada origen solo se utilizan fechas anteriores; se evalúan horizontes de 1 a 12 meses. Los candidatos comparten los mismos orígenes y objetivos.
- Selección por MAE y desempate con RMSE; evita seleccionar estacionalidad por mejoras inferiores al 3 % frente al mejor modelo sencillo.
- Se muestran MAE, RMSE, WAPE, R² fuera de entrenamiento cuando sea válido, comparaciones con modelos base y calidad de datos.
- Los rangos inferior y superior usan el percentil 80 del error absoluto histórico: son bandas descriptivas, **no intervalos de confianza calibrados**.
- Los meses ausentes no se rellenan con cero. Se comunican explícitamente y desactivan la evaluación estacional.
- El campo confidence representa evidencia heurística, no probabilidad de acierto.

## Anomalías ajustadas al calendario

Se estima una tendencia robusta usando medianas de variaciones comparables y efectos mensuales mediante medianas de residuales. Las anomalías son desviaciones materiales respecto al valor esperado para su mes, no simples picos sobre el promedio general. Se comunican magnitud, severidad, referencia y advertencias cuando el historial anual es escaso.

La detección es **retrospectiva** y puede utilizar observaciones posteriores al período evaluado; no constituye backtesting de pronósticos ni un juicio causal.

## Investigación de cambios por segmentos

El módulo diagnóstico compara hasta cinco períodos anómalos con el mismo mes del año anterior, o con el mes previo si no existe. Solo agrupa por columnas categóricas reconocidas de la **misma tabla**: estado, tipo, método, origen y destino, si están disponibles.

Se restringe a tres dimensiones por anomalía y cuarenta categorías completas por consulta; desgloses truncados se omiten. No se consulta información personal, texto libre ni identificadores de usuarios. Se presentan cambios observados y límites. De forma adicional se comparan los conteos temporales de hasta seis entidades relacionadas por el mismo dominio, cuando tienen fecha y periodos equivalentes; esas coincidencias están identificadas explícitamente como asociaciones, no como relaciones causales. **Ninguna correlación demuestra por sí sola la causa**. Para atribuciones causales reales se requerirán otros datos verificables y análisis posteriores.

## API e interfaz

Se conservan las respuestas de /api/ai/forecast y /api/ai/anomalies y se agregan validación de modelos, calidad de datos, patrones estacionales, valores esperados y desgloses descriptivos. El chatbot y la pantalla Predicciones interpretan estos nuevos campos. La lógica sigue adaptándose a SQL Server, PostgreSQL y Excel convertido a SQLite a través del modelo semántico.

## Pruebas

Ejecutar desde Backend:

- python -m unittest discover -s tests -p 'test_robust_ml.py' -v
- python -m unittest discover -s tests -p 'test_seasonal_forecasting.py' -v
- python -m unittest discover -s tests -p 'test_assistant_prediction_domains.py' -v
- python -m app.quality.run --report-dir quality_reports

Los importes de transacciones financieras pueden ser negativos y no se fuerzan a cero. La suite automatizada utiliza SQLite y datos ficticios; no demuestra exactitud con conexiones reales SQL Server/PostgreSQL, efectos externos, cambios de régimen ni calibración probabilística de intervalos.
