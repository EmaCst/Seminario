# Kenneth: motor conversacional y análisis verificado

## Orden de ejecución

1. `assistant_router.route_request` clasifica el mensaje actual y, solo para referencias explícitas, recupera contexto de preguntas anteriores del usuario.
2. Saludos y agradecimientos se responden sin tocar la base de datos ni llamar al modelo.
3. Preguntas frecuentes de ventas, rankings de productos/clientes y contribuciones entre meses pasan por `assistant_analytics.run_verified_analytics`.
4. Predicciones y anomalías mantienen sus servicios especializados.
5. Las demás preguntas pasan por Gemma con el esquema real; la consulta se valida como solo lectura antes de ejecutarse y admite un intento de reparación.
6. Si falta información para una métrica verificada, Kenneth devuelve una limitación concreta en lugar de presentar un valor estimado como real.

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

**Limitación**: la suite verifica el enrutamiento y los cálculos principales con datos de prueba; no sustituye pruebas de integración contra esquemas reales y los tres proveedores ni una evaluación continua de las consultas libres que genera Gemma.

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
