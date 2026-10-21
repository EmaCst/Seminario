# Auditoría funcional del creador de visualizaciones — Fase 3

## Alcance y estado

Revisión de `VisualizationBuilder`, `semantic_catalog`, `visualization_service`, `SavedVisualizations`, `VisualizationResultTable`, el flujo de borradores del chat y la compatibilidad con los informes PDF de la Fase 2.

**Resultado:** implementación ampliada en `feature/conversational-visualization-drafts-phase-3`, asociada al issue #5 y PR #8. Las comprobaciones automatizadas son favorables, pero la fase requiere pruebas manuales con esquemas reales y distintas versiones de SQL Server/PostgreSQL y Excel antes de considerarse completamente validada.

## Capacidades disponibles

- Seis tipos de visualización: indicador KPI, barras, líneas, área, dona y tabla.
- Tablas de dos modalidades: agregación por dimensión y **detalle real** (hasta ocho columnas de la tabla principal o padres con relaciones verificadas); búsqueda, ordenación, paginación en la vista y exportación CSV limitada a las filas cargadas.
- Agregaciones: cantidad de registros, cantidad de valores únicos, suma, promedio, mínimo y máximo, según tipo de dato.
- Agrupaciones: categorías, fechas y períodos diarios, mensuales, trimestrales y anuales. Hay consultas específicas para SQL Server, PostgreSQL y SQLite/Excel.
- Filtros por igualdad, desigualdad, comparación, coincidencia de texto, listas, intervalos, valores nulos y comparaciones entre dos campos numéricos verificados.
- Orden ascendente/descendente por valor o cronológico, y límite configurable de 1 a 100 categorías/filas.
- Selección independiente de destino en Dashboard y Analítica, edición, duplicación y eliminación desde las funciones existentes de la biblioteca.
- Etiquetas contextuales de ejes, incluido el agrupamiento diario.
- Atajos **solo de configuración** por volumen general, evolución mensual y distribución por estado, mostrados únicamente si la entidad tiene las columnas adecuadas. No hay guardado automático.
- Opción de distinguir registros con el mismo nombre mediante claves primarias verificadas: evita fusionar clientes, productos, pacientes y otros individuos homónimos.
- Generación desde Kenneth mediante propuesta de solo lectura, vista previa y apertura del mismo creador para confirmar.

## Compatibilidad con los diez dominios

El catálogo **no depende de un esquema fijo**; inspecciona la fuente actual y presenta solo entidades/campos verificables. Las posibilidades concretas cambian con cada base. Casos representativos:

| Dominio | Entidades típicas | Visualizaciones posibles cuando existen columnas |
|---|---|---|
| Comercio | Ventas, Productos, Clientes, Inventario | Ventas mensuales, valor por cliente, stock crítico |
| Educación | Inscripciones, Alumnos, Cursos | Inscripciones por período, distribución por curso, tablas |
| Salud | Citas, Pacientes, Doctores | Citas por mes y estado, tabla de registros |
| Transporte | Viajes, Rutas, Vehículos | Volumen de viajes por mes o ruta |
| Hotelería | Reservas, Habitaciones, Huéspedes | Reservas mensuales, distribución de estados |
| Restaurantes | Órdenes, Menú, Mesas | Órdenes por día, conteos por estado |
| Servicios profesionales | Facturas, Proyectos, Clientes | Facturación mensual, indicadores por proyecto |
| Finanzas y contabilidad | Transacciones, Cuentas, Asientos | Flujos por período, distribución de cuentas |
| Manufactura | Órdenes de producción, Materiales | Órdenes por estado, actividad por período |
| Recursos humanos | Nómina, Empleados, Turnos | Volumen y distribución temporal, tablas |

Estas son **capacidades condicionadas a las columnas reales**, no una promesa de que cada indicador exista en cualquier esquema. No se inventan importes, relaciones ni fechas.

## Correcciones en esta auditoría

1. Se añadió la agrupación **por día** y se verificó sobre registros horarios reales en SQLite, más la generación de SQL compatible con SQL Server/PostgreSQL.
2. Se añadieron atajos a los análisis comunes basados en catálogo. Cuando hay dos o más métricas numéricas plausibles, el atajo utiliza conteo en lugar de seleccionar un importe arbitrariamente.
3. Se evita ofrecer SUM/AVG sobre métricas de una tabla padre relacionada con cada registro de la tabla principal, ya que duplicaría importes.
4. Se rechaza MIN/MAX de texto cuando se pretende representarlo en un gráfico numérico o KPI; se permite en tablas cuando el resultado es significativo.
5. Se añadió acceso directo para crear filtros de rango de fechas sobre una columna temporal inequívoca, conservando la edición de sus dos extremos.
6. Se mejoró la validación previa de condiciones BETWEEN y se respetaron los filtros de valores nulos que no necesitan dato adicional.
7. El filtro «contiene» ahora trata `%` y `_` como caracteres literales, no como comodines SQL.
8. Se añadió el control explícito para evitar sumar entidades distintas con el mismo nombre en una sola barra.
9. Se añadió cobertura de regresión de diez dominios empresariales, intervalos temporales, porcentajes en cadenas y combinaciones peligrosas de métricas/relaciones, sobre Python 3.11/3.12.

## Invariantes de confiabilidad

- Kenneth nunca guarda una visualización desde el chat sin la confirmación explícita en el creador.
- Los datos de vista previa se vuelven a validar cuando se guarda.
- Las uniones automáticas siguen rutas **muchos-a-uno** con claves verificadas; rechazar una consulta insegura es preferible a una suma incorrecta.
- Las visualizaciones antiguas no requieren `time_granularity=day`, ni campos nuevos, para seguir cargando.
- Los filtros construidos desde el formulario utilizan campos del catálogo y validación del backend.
- Una vista previa con límite de filas es una muestra acotada; la exportación CSV de esa vista no representa necesariamente el total histórico.

## Límites y comprobaciones pendientes

- No se pueden agregar a ciegas existencias de varias bodegas, convertir importes entre monedas o resolver causas de anomalías; requieren reglas semánticas específicas del negocio.
- El motor no construye uniones genéricas uno-a-muchos porque pueden multiplicar indicadores; deben modelarse desde la tabla de hechos apropiada.
- Las visualizaciones cubren medidas únicas por gráfico; gráficos con dos escalas, dispersión de dos métricas, mapas geográficos o pivotes multidimensionales requieren contratos nuevos y pruebas adicionales.
- La previsualización está limitada a 100 grupos/filas por configuración y su CSV exporta las filas cargadas. La exploración paginada puede acceder a más filas de tablas según el endpoint.
- El administrador de conexiones global de Kenneth sigue siendo un límite arquitectónico previo a la Fase 4; no deben publicarse vistas bajo otra fuente.
- Las pruebas automatizadas con SQLite y generación de SQL por dialecto no equivalen a una prueba end-to-end con una instancia real de SQL Server o PostgreSQL.

## Pruebas

```bash
cd Backend
python -m unittest discover -s tests -p 'test_visualization_engine_domains.py' -v
python -m unittest discover -s tests -p 'test_visualization_builder_enhancements.py' -v
python -m unittest discover -s tests -p 'test_conversational_visualizations.py' -v
python -m unittest discover -s tests -p 'test_inventory_critical_phase3.py' -v
```

También pasan las puertas de calidad y las verificaciones de `npm run lint` y `npm run build` del frontend en GitHub Actions.

La revisión manual debería verificar como mínimo: una serie mensual por cada dominio representado en la base, una tabla de detalle con búsqueda y CSV, una consulta con uniones a entidades relacionadas, un filtro de rango de fechas, una visualización con nombres duplicados y su persistencia en ambos destinos.
