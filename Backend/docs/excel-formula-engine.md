# Motor seguro de fórmulas Excel para Datalyx

## Qué cambió
La importación anterior abría cada Excel con `data_only=True`, lo que **no evalúa fórmulas** y devuelve `NULL` cuando el archivo no contiene resultados en caché.

Ahora se abre el libro con las fórmulas originales, se construye un evaluador local y se resuelven las dependencias **antes de inspeccionar y crear las tablas SQLite**. El mismo cálculo se usa en la vista previa y en la importación real. No se modifica el archivo original.

`formula_diagnostics` aparece en las respuestas de inspección e importación:
```json
{
  "formulas_detected": 71,
  "formulas_calculated": 71,
  "formulas_unresolved": 0,
  "errors": [],
  "truncated_errors": 0
}
```
Cuando una función es desconocida, una referencia no existe, hay un ciclo o el cálculo excede límites, el valor afectado se importa como `NULL` y la columna y hoja muestran un aviso. **No se inventan resultados**. Se exponen como máximo 60 errores detallados.

## Funciones soportadas
- Operaciones `+ - * / ^ %`, comparaciones, concatenación, celdas y rangos incluso de otras hojas.
- `SUM`, `MIN`, `MAX`, `AVERAGE`, `COUNT`, `COUNTA`, `COUNTIF`, `COUNTIFS`, `SUMIF`, `SUMIFS`, `AVERAGEIF`.
- `IF` (evaluación selectiva de rama), `IFERROR`, `AND`, `OR`, `NOT`, `ROUND`, `ROUNDUP`, `ROUNDDOWN`, `ABS`, `INT`, `MOD`.
- `DATEVALUE` (ISO `AAAA-MM-DD`), `DATE`, `YEAR`, `MONTH`, `DAY`, `LEN`, `LEFT`, `RIGHT`, `CONCAT`, `CONCATENATE`.

Las fechas creadas con `DATEVALUE` se representan mediante su **número de serie Excel** para que la resta de fechas produzca días, como en el libro de alquiler de vehículos.

## Seguridad y límites
- No se usa `eval`, `exec`, VBA, macros, motores de cálculo que puedan ejecutar comandos, ni accesos a red.
- Solo se aceptan referencias a celdas/rangos del mismo archivo. Se rechazan enlaces externos, referencias estructuradas y funciones desconocidas; no se ejecutan funciones que acceden a contenido externo.
- Límites de profundidad de dependencias (80), celdas evaluadas (30 000), tamaño de rangos (30 000) y longitud de fórmula (10 000 caracteres).
- Detección explícita de referencias circulares y divisiones entre cero.
- El importador original conserva el límite máximo de 25 MB de archivo, y los datos siguen pasando por los mismos controles de fuente.

**Compatibilidad:** esto cubre fórmulas deterministas usuales, pero **no pretende replicar el 100 % de Excel**. Fórmulas volátiles, macros, matrices dinámicas, funciones de complementos, tablas estructuradas y enlaces externos se identifican como no compatibles. Si se necesita compatibilidad completa, deberá integrarse un motor externo aislado con controles adicionales.

## Pruebas
```bash
cd Backend
python -m unittest discover -s tests -p 'test_excel_formulas.py' -v
```
Se verifican fórmulas típicas de reservas y rentas, las referencias entre hojas, `COUNTIF`/`AVERAGEIF`, condiciones que evitan una división entre cero, celdas circulares y la vista previa del Excel importado.

Para revisar el caso manual, sube `Base_de_Datos_Renta_de_Carros-v2.xlsx` y comprueba `Reservas_y_Rentas`: F2=4 días, H2=180 y K2=220. En `Panel_Resumen`, H6=8420. Para ese archivo, el evaluador local resolvió sus 71 fórmulas.

Esto **no resuelve por sí solo** otras limitaciones del importador, como detectar hojas que son dashboards, inferir claves foráneas o tipificar fechas que originalmente vienen como texto. Son mejoras independientes.
