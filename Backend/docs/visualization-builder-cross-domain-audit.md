# Fase 3 · Auditoría transversal del creador de visualizaciones

Rama de trabajo: `feature/conversational-visualization-drafts-phase-3`. Pull request en borrador: #8. Issue: #5.

## Propósito

Asegurar que la creación **manual y asistida por Kenneth** utilice el mismo motor
de visualización, preservando los campos reales, filtros, cálculos y relaciones
de los distintos modelos empresariales. El chat prepara una propuesta; **solo
el usuario decide guardarla** en Dashboard, Analítica o ambos.

## Modelos de negocio

El catálogo se construye inspeccionando la base de datos activa y el modelo
semántico. No existen columnas obligatorias llamadas exactamente `ventas`,
`pacientes` o `salario`: las tablas y campos proceden del esquema real.

| Dominio | Ejemplos que cubre el motor |
| --- | --- |
| Retail / comercio | Ventas por cliente o mes; stock bajo vs mínimo; productos |
| Educación | Inscripciones por curso, notas promedio, asistencia |
| Salud | Citas por médico, pacientes únicos, procedimientos por fecha |
| Transporte | Viajes por conductor/ruta, ingresos, reservas |
| Hotelería | Reservas por habitación, estadías, fechas |
| Restaurantes | Órdenes por mesa, consumos por período, productos |
| Servicios profesionales | Facturas por cliente, proyectos, cobros |
| Finanzas y contabilidad | Transacciones, balances, cuentas, agrupaciones |
| Manufactura | Órdenes y unidades producidas, máquinas, inventario |
| Recursos humanos | Nómina, empleados únicos, asistencia, departamentos |

Estas son **capacidades condicionadas por columnas y relaciones existentes**,
no promesas de que cualquier base de datos contenga todas esas métricas.

## Tipos de salida

- **KPI:** un indicador sin dimensión agrupada; conteo de registros, conteo
  de valores únicos, suma, promedio, mínimo o máximo.
- **Barras:** comparación entre categorías con orden por valor ascendente o descendente.
- **Línea:** evolución cronológica o distribución sobre una dimensión.
- **Área:** evolución acumulada visualmente sobre una línea (no transforma los
  valores en sumas acumuladas; el área solo es una presentación).
- **Dona:** partes de un conjunto. Se impiden valores negativos o
  distribuciones de suma cero, pues serían engañosas.
- **Tabla agregada:** dimensión, medida y agregación; límites seguros.
- **Tabla detallada:** entre 1 y 8 columnas de registros reales, combinando
  campos de la tabla de hechos y sus tablas padre relacionadas; orden configurable.

Se permiten **agrupaciones por fecha sin transformación, mes, trimestre o
año**. Se conserva el orden cronológico de las fechas. La traducción temporal
utiliza expresiones específicas para SQL Server, PostgreSQL y SQLite/Excel.

## Filtros y calidad de consultas

El motor valida cada tabla y columna contra el esquema activo; la interfaz
solo expone entidades relacionadas en dirección de una tabla de hechos hacia
una tabla padre cuyo destino sea clave primaria.

Los filtros soportados son igualdad y desigualdad, rangos, contenido de texto,
lista de valores, nulos/no nulos y comparaciones de dos columnas numéricas.
Los cruces de columnas entre Inventario y Productos solo se aceptan con una
relación directa, única y comprobada.

Los errores de cardinalidad se tratan como errores semánticos:
- Se **rechazan** cruces padre → varios hijos que multiplicarían filas y
  alterarían sumas.
- Se **rechazan** rutas múltiples igualmente plausibles hacia una tabla.
- No se suman ni promedian medidas de una tabla padre repetida por cada
  fila de una tabla hija.
- Si dos clientes o productos tienen el mismo nombre, se utiliza su
  identificador verificado para no fusionarlos en un único elemento.
- Los nombres de columnas y relaciones se validan antes de construir SQL;
  los filtros numéricos no permiten expresiones SQL arbitrarias.
- No se inventan resultados cuando una previsualización queda vacía.

Esto no reemplaza el endurecimiento general del validador SQL ni el aislamiento
de conexiones por usuario previstos para la Fase 4.

## Tablas y exploración

La muestra de un gráfico o tabla está limitada a un máximo de 100
agrupaciones/filas. La exploración de tablas solicita las páginas **al servidor**
(25 registros por página), con búsqueda sobre las columnas seleccionadas y
ordenamiento por campos permitidos; no descarga toda la tabla a memoria en
el navegador.

Las tablas de previsualización y las tablas guardadas comparten encabezados
explícitos, búsqueda y paginación de las filas cargadas. Su botón CSV exporta
**solo los resultados de la muestra**, no el total de la base. Los textos
peligrosos que parecen fórmulas de hoja de cálculo se neutralizan al exportar.

## Compatibilidad con lo existente

Las definiciones anteriores conservan los valores predeterminados:
`table_mode='aggregate'`, `time_granularity='raw'`,
`sort_direction='desc'`, `time_direction='asc'`, sin columnas detalladas.
No se sobrescriben las visualizaciones de los usuarios ni cambia el
contrato de confirmación del creador.

Los reportes profesionales de la Fase 2 pueden incluir nuevas tablas
detalladas y visualizar las series de área como líneas equivalentes,
indicándolo expresamente en el PDF.

## Validación

La CI comprueba el frontend con lint y build y el backend con Python 3.11 y
3.12. Nuevas baterías de prueba:

```bash
cd Backend
python -m unittest discover -s tests -p "test_visualization_engine_domains.py" -v
python -m unittest discover -s tests -p "test_conversational_related_domains.py" -v
python -m unittest discover -s tests -p "test_inventory_critical_phase3.py" -v
python -m unittest discover -s tests -p "test_conversational_visualizations.py" -v
```

Las pruebas usan SQLite con datos sintéticos, ejemplos del modelo semántico
de los diez dominios y validación del SQL generado para SQL Server y
PostgreSQL. Incluyen comprobación de no duplicación, conteos distintos,
relaciones ausentes/ambiguas, fechas, filtros, exploración paginada, nombre
repetido de clientes y datos insuficientes.

## Limitaciones pendientes

- La **prueba interactiva con bases empresariales reales** en SQL Server,
  PostgreSQL y Excel se debe realizar antes de cerrar la Fase 3.
- El motor no calcula automáticamente todos los indicadores compuestos
  posibles (por ejemplo, márgenes, ratios financieros, tasa de ocupación,
  tasas clínicas). Esos requieren definiciones de negocio explícitas y
  fórmulas auditables; sería incorrecto inferirlas de cualquier columna.
- Las relaciones **uno-a-muchos** se evitan para métricas del padre: deben
  formularse desde la tabla hija o mediante una consulta agregada específica.
- Las tablas detalladas permiten hasta ocho columnas y las muestras hasta
  cien filas; el explorador puede navegar más registros sin descargarlos todos.
- El almacenamiento del motor de visualizaciones sigue siendo local y
  particionado por proveedor/base de datos, no por usuario o instancia:
  revisar en la Fase 4 junto con aislamiento, permisos y despliegue.
