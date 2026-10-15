# Kenneth: motor conversacional y análisis verificado

## Orden de ejecución

1. `assistant_router.route_request` clasifica el mensaje actual y, solo para referencias explícitas, recupera contexto de preguntas anteriores del usuario.
2. Saludos y agradecimientos se responden sin tocar la base de datos ni llamar al modelo.
3. El servicio detecta el dominio mediante `assistant_domain_analytics` y bloquea atajos de comercio si el dominio no es retail. Conteos, importes, estados y series mensuales verificables se atienden con el modelo semántico de ese dominio. Las preguntas comerciales específicas usan `assistant_analytics.run_verified_analytics` solo en retail.
4. Predicciones y anomalías seleccionan explícitamente la entidad y métrica solicitadas mediante sus servicios especializados.
5. Las demás preguntas pasan por Gemma con el esquema real; la consulta se valida como solo lectura antes de ejecutarse y admite un intento de reparación.
6. Si falta información para una métrica verificada, Kenneth devuelve una limitación concreta en lugar de presentar un valor estimado como real.

## Cobertura por dominio (fase verificada)

El enrutamiento utiliza el dominio detectado a partir del esquema (`semantic_mapper_v2`), antes de activar cálculos comerciales. La ruta `assistant_domain_analytics.py` reconoce diez dominios:

| Dominio | Entidades representativas | Análisis deterministas |
| --- | --- | --- |
| Comercio (`retail`) | Ventas, productos, clientes, inventario, pagos | Ventas monetarias, transacciones, unidades, rankings y contribuciones; conteos generales y mensuales |
| Educación (`education`) | Estudiantes, docentes, cursos, inscripciones, notas, asistencia | Conteos, series y comparaciones de registros de inscripciones/asistencia |
| Salud (`healthcare`) | Pacientes, médicos, citas, diagnósticos, tratamientos, admisiones | Conteos de registros y series de citas/admisiones cuando existe fecha |
| Transporte (`transportation`) | Vehículos, conductores, viajes, rutas, boletos | Conteos mensuales, comparación de viajes e importes registrados de boletos si están mapeados |
| Hotelería (`hospitality`) | Habitaciones, huéspedes, reservas, estadías | Conteos y comparaciones de reservas, importes registrados si existe total |
| Restaurantes (`restaurant`) | Platos, mesas, pedidos, ingredientes | Conteos de pedidos, comparaciones e importes de pedidos |
| Servicios profesionales (`professional_services`) | Clientes, servicios, citas, proyectos, facturas, pagos | Conteos, comparaciones, importes de facturas y pagos |
| Finanzas (`finance_accounting`) | Cuentas, transacciones, asientos | Conteos de movimientos e importes de transacciones registrados |
| Manufactura (`manufacturing`) | Productos, materiales, máquinas, órdenes de producción | Conteos y comparaciones de órdenes y otros registros identificados |
| Recursos humanos (`human_resources`) | Empleados, departamentos, asistencia, nómina | Conteos, series e importes de nómina registrados |

Operaciones generales: conteos de entidades, total de importes **solo donde hay columnas compatibles explícitas**, series por mes, diferencias entre meses, estados por mes, picos con mes calendario anterior y pronósticos/anomalías sobre el rol solicitado. Todas requieren una entidad detectada sin ambigüedad. Los totales por estado, período y rol se expresan como conteos de **registros**, no como personas únicas, ingresos o hechos clínicos.

**No equivalen a cobertura universal del lenguaje natural.** Tasas, promedios específicos, ocupación hotelera, diagnósticos, relaciones de múltiples entidades y rankings complejos requieren consultas más elaboradas. Se derivan a planificación SQL con el esquema real, y no se convierten silenciosamente en totales simples. Si no existe la métrica o una relación verificable, Kenneth debe indicarlo.

## Predicciones y anomalías

La serie se elige por la entidad nombrada en la pregunta (o por prioridad del dominio si no se nombra ninguna), **no por escoger una tabla distinta que tenga más meses**. El modelo diferencia conteos e importes; si el importe se solicita y no existe un campo monetario mapeado, informa que falta evidencia. Se requieren al menos tres meses para la regresión lineal y cuatro para detectar anomalías. Estas predicciones son exploratorias, no garantías ni interpretaciones clínicas.

## Semántica de métricas

- **Importe vendido**: suma de los importes registrados en la cabecera de ventas.
- **Cantidad de ventas**: número de transacciones registradas, `COUNT(*)`.
- **Unidades vendidas**: suma de cantidades en el detalle de ventas, relacionadas con sus cabeceras.
- **Producto más vendido**: por defecto, unidades. Si se pide expresamente dinero/importe, se usan los importes históricos en las líneas de venta. No se sustituyen por precios actuales de catálogo.
- **Mejor cliente**: por defecto, importe total de compras; si se pregunta quién compra más veces, se cuentan transacciones.
- **Contribución por producto**: se comparan importes históricos de cada producto en los dos meses. Se verifica el signo del cambio y se advierte si la suma de líneas no cuadra con el total de cabeceras.
- **Año no indicado**: se utiliza el último año que tenga registros del mes solicitado; para comparar meses, el último año con registros de ambos. No se interpreta ausencia de registros como cero.

## Compatibilidad y seguridad

Los SQL de la ruta verificada utilizan identificadores obtenidos mediante `inspect_semantic_map`, escapados conforme al proveedor, y valores ligados mediante parámetros. SQL Server, PostgreSQL y SQLite (Excel) tienen expresiones de fecha adaptadas. Las relaciones faltantes impiden atribuciones o rankings que no pueden verificarse.

## Pruebas

Desde la carpeta `Backend`:

```bash
python -m pip install -r requirements.txt
python -m compileall -q app tests
python -m unittest discover -s tests -p 'test_assistant*.py' -v
```

El flujo `.github/workflows/kenneth-assistant-tests.yml` ejecuta estas pruebas en los cambios del backend. La suite usa SQLite en memoria y no requiere una base de datos de producción ni Ollama.

**Limitación**: la suite incluye casos por los diez dominios, ejemplos de esquemas, selección de series temporales y métricas con datos sintéticos; no sustituye pruebas de integración contra esquemas reales y los tres proveedores ni una evaluación continua de las consultas libres que genera Gemma.

## Casos de regresión mínimos

- `hola keneth` → saludo sin SQL.
- `ventas de junio` → importe de ventas, no ranking.
- `cuántas ventas hubo en junio` → cantidad de transacciones.
- `unidades vendidas en junio` → suma de cantidades del detalle.
- `producto más vendido de junio` → producto y cantidad, no importe agregado del mes.
- `nuestro meyor cliente` → ranking de clientes por monto, tolerando el error ortográfico.
- `diferencia entre junio y febrero` seguida de `qué producto marcó esa diferencia` → contribución monetaria a la diferencia, no repetición de totales.
- `y en febrero` después de un ranking de productos → mismo tipo de ranking en el nuevo mes.
- `top 2 clientes` → dos clientes, no uno.
- Sin relación o columna verificable → explicación específica, sin valores inventados.
