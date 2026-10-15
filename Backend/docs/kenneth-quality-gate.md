# Kenneth — pruebas de integración y puerta de calidad

## Alcance y seguridad

La suite recorre FastAPI `/ask-db`, la detección de dominio, el modelo semántico, SQLAlchemy y respuestas reales sobre **bases SQLite temporales con datos ficticios**. No accede a bases externas ni modifica información de usuarios. El modo de calidad impide la conexión automática desde `DB_SERVER`.

Los dominios cubiertos son: comercio, educación, salud, transporte, hotelería, restaurantes, servicios profesionales, finanzas, manufactura y recursos humanos.

### Datos conocidos

| Período | Registros | Importe sintético (cuando corresponde) |
| --- | ---: | ---: |
| Febrero de 2026 | 1 | 100 |
| Junio de 2026 | 2 | 500 |
| Diferencia junio - febrero | 1 | 400 |

En comercio, Café tiene 3 unidades vendidas en junio; Pan tiene 2. Ana tiene compras acumuladas por 390 y Luis por 210. Pan contribuye 210 al aumento monetario entre febrero y junio, frente a 190 de Café. Estos datos no pertenecen a ninguna empresa real.

## Ejecutar en Windows (PowerShell)

Desde la carpeta `Backend` con el entorno virtual activo:

```powershell
git pull origin feature/custom-visualization-engine
python -m compileall -q app tests
python -m app.quality.run
```

Solo la integración real de FastAPI y SQLite:

```powershell
python -m app.quality.run --suite integration
```

Los reportes se guardan en `Backend/quality_reports/report.json` y `Backend/quality_reports/report.md`. El directorio está excluido de Git. El comando devuelve código de salida 1 cuando hay fallos. GitHub Actions ejecuta la versión sin Ollama y conserva ambos informes como artefactos `kenneth-quality-report-py3.11` y `kenneth-quality-report-py3.12`.

## Ollama/Gemma — ejecución manual opcional

Si Ollama está ejecutándose y el modelo `gemma3:4b` está disponible:

```powershell
python -m app.quality.run --with-ollama
```

Esto invoca **Gemma real** con una pregunta sobre productos de la base ficticia. Verifica que el SQL generado sea ejecutable y de solo lectura, que devuelva los productos conocidos y que la explicación los mencione. Si Ollama no está disponible, la comprobación fallará explícitamente. No se invoca en GitHub Actions por defecto.

## Qué comprueba

- Detección semántica real para los diez dominios mediante tablas y columnas generadas en SQLite.
- Conteos, seguimientos y diferencias mensuales por el endpoint HTTP `/ask-db`.
- Importes solo cuando existe una columna monetaria realmente mapeada.
- Conversación completa de comercio: saludo, monto de ventas, transacciones, unidades, producto, cliente y atribución.
- Rechazo de SQL de escritura y referencias a tablas inexistentes.
- Evitar que se descarten filtros de día, estado o cliente en rutas analíticas rápidas.
- Aislamiento de la conexión a datos, registro de fallos de subpruebas y generación del reporte.

## Límites de validación

**Automatizado:** SQLite temporal, equivalente al motor empleado para los libros de Excel. **Comprobado sintácticamente:** expresiones de fecha para SQL Server y PostgreSQL por pruebas existentes. **No probado contra servidores reales:** PostgreSQL ni SQL Server. No se crean ni destruyen bases remotas automáticamente: esas pruebas requieren instancias aisladas y autorización específica.

Un estado `PASS` significa que pasan los casos definidos, no que todas las preguntas posibles estén resueltas. Cuando se encuentre una regresión, se añade un caso reproducible al conjunto de pruebas antes de corregirla.
