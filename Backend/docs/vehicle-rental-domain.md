# Dominio: alquiler de vehículos (`vehicle_rental`)

El dominio trabaja sobre el esquema físico actual; no presupone que exista una tabla literal `Ventas` ni renombra los datos de los usuarios. Comparte la infraestructura de dashboards, analítica, predicción, asistente y visualizaciones de los otros diez dominios.

## Detección y roles

Reconocimiento por nombres de tablas y columnas con señales de renta, reserva, flota, tarifas, clientes y mantenimiento. Cuando no hay evidencia suficiente se conserva el comportamiento de dominio ambiguo/no identificado, en vez de imponer una clasificación.

| Rol | Tablas de ejemplo | Columnas |
|---|---|---|
| `rentals` | Reservas_y_Rentas, rentas, rental_agreements | ID de reserva, ID de cliente y vehículo, fecha de inicio/fin, días, tarifa, total general, estado |
| `vehicles` | Flota_Vehiculos, vehículos, fleet | ID, placa, modelo, marca, categoría, tarifa diaria, estado |
| `customers` | Clientes, customers | ID, nombre, registro |
| `maintenance` | Mantenimiento, maintenance | ID, vehículo, fecha, costo, tipo de servicio, taller, estado |
| `payments` (opcional) | pagos, payments | ID, monto, fecha, estado |

Los cinco roles están en `semantic_mapper_v2.py`. La ausencia de un rol opcional no interrumpe los demás; las visualizaciones muestran solo datos verificables.

## Capacidades disponibles

- **Dashboard:** total de rentas, vehículos, clientes y mantenimientos; evolución por mes y distribución por estado usando las tablas pertinentes en vez de inventar fechas en `Clientes`.
- **Analítica:** resúmenes numéricos de importes, tarifas y costos; distribución categórica, tendencias, variaciones mensuales y hallazgos básicos.
- **Rankings con relaciones verificables de esquema:** clientes por ingresos de renta, vehículos por cantidad de rentas y vehículos por costo de mantenimiento. Si no se puede identificar una relación, se omite el ranking antes que sumar tablas desconectadas.
- **Asistente:** preguntas de rentas, vehículos, clientes, mantenimientos y pagos; cálculos de cantidad o importes sin confundir precio de lista con facturación.
- **Predicciones y anomalías:** series mensuales verificadas de reservas/rentas (conteo) e ingresos de rentas cuando se dispone de una columna `total`; se aplican los mismos mínimos de observaciones que en los otros dominios.
- **Constructor de visualizaciones:** catálogo semántico con tablas, métricas, dimensiones y filtros del esquema; gráficas KPI, barras, líneas, áreas, dona y tablas.
- **Motores:** SQL Server, PostgreSQL y Excel importado a SQLite usan la misma detección y las capacidades disponibles en los componentes genéricos.

### Mejoras al importar Excel

1. El motor de fórmulas del PR #11 calcula importes en vez de leer cachés inexistentes.
2. Las fechas ISO `AAAA-MM-DD` almacenadas como texto se reconocen como fechas reales únicamente cuando toda la columna tiene valores compatibles (ignorando nulos).
3. Los identificadores `id_*`/`*_id` completos y únicos se materializan como PK; el inspector detecta relaciones no ambiguas, incluso con tablas como `Flota_Vehiculos`.
4. Las filas de pie `Total General` o `Gasto Total` sin identificador se omiten para no duplicar totales o distorsionar conteos.
5. Las consultas de agrupación y clasificación utilizan `LIMIT` cuando la fuente es SQLite, nunca `TOP`.

**No se ha modificado la estructura del Excel original**. La importación crea una fuente SQLite temporal; el archivo y sus fórmulas permanecen intactos.

## Pruebas de regresión

```bash
cd Backend
python -m unittest discover -s tests -p 'test_vehicle_rental_domain.py' -v
python -m unittest discover -s tests -p 'test_visualization_engine_domains.py' -v
python -m app.quality.run --report-dir quality_reports
```

El test `test_vehicle_rental_domain.py` crea un libro XLSX *sintético* con el mismo esquema de cuatro hojas principales del archivo de renta de vehículos, sin datos personales del usuario. Comprueba importación y fórmulas, esquema SQLite, PK/FK, dominio, roles, dashboards, distribuciones, rankings, consultas, pronósticos y catálogo de visualizaciones. La matriz de calidad cubre ahora los **11 dominios**, manteniendo el orden previo de fixtures para compatibilidad.

## Límites

- `Panel_Resumen` es una hoja de presentación, no una tabla normalizada. El importador puede conservarla como datos auxiliares; no se usa como entidad principal del dominio.
- La detección de relaciones por nombres y PK es **inferida**, no equivale a una FK validada contra todos los valores. Se priorizan relaciones reales cuando la base proporciona FKs.
- Los pronósticos requieren suficiente historial mensual verificable. Con menos puntos se devuelve la advertencia existente, no una curva fabricada.
- Ninguna capa asume que una reserva es necesariamente un ingreso cobrado; los totales suman el campo de reserva y se deben filtrar estados para contabilidad real de cobros si el negocio lo requiere.
- No se ha verificado una conexión a SQL Server real: los tests de integración se ejecutan sobre SQLite de prueba. Debe ensayarse el Excel en la aplicación local y comprobar la conexión activa.
- Si la interfaz todavía indica `SQL Server` debajo del dominio, la fuente actual es SQL Server, no el archivo Excel. Activar el archivo desde la pantalla de importación si se pretende analizarlo.
