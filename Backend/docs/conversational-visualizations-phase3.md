# Kenneth · Fase 3: visualizaciones conversacionales (issue #5)

## Decisión de arquitectura

**Un solo chat de Kenneth** es el punto de entrada: no se implementa un chatbot paralelo en el creador. El motor conversacional propone una definición y obtiene una vista previa contra el modelo semántico; luego el usuario pulsa **Revisar y editar en el creador**. El constructor visual existente conserva toda la responsabilidad de editar, validar y persistir la visualización.

Este flujo evita duplicar lógica, mantiene una única conversación y conserva la confirmación humana, solicitada explícitamente para esta fase.

## Flujo verificable

1. Usuario: `Crea una gráfica de barras con las ventas por mes de 2026 y agrégala al dashboard`.
2. `POST /ask-db` reconoce la creación de visualizaciones antes de ejecutar preguntas generales o generar SQL libre.
3. `conversational_drafts.interpret_visualization_request` identifica una tabla y columnas reales del catálogo semántico; si hay más de una medida posible, requiere aclaración en vez de inventar un campo.
4. El motor devuelve el objeto `visualization_draft` con `definition`, `preview`, `placement`, `axes`, `source`, `notes` y `status`.
5. El chat presenta un gráfico o tabla provisional con sus ejes, la fuente y el destino previsto. **Todavía no está guardado.**
6. El botón de revisión abre `VisualizationBuilder` con el borrador ya cargado, incluida la agrupación mensual, rango del año y casillas de Dashboard/Analítica.
7. El usuario puede cambiar métricas, grupos, filtros, título, tipo de gráfica, límite de registros y destinos. Al pulsar **Guardar**, el constructor vuelve a consultar y validar; rechaza resultados vacíos y fuentes incompatibles antes de guardar.
8. Cuando la operación de guardado responde con éxito, el chatbot confirma la ubicación y se actualiza la vista correspondiente.

## Agrupación real por período

El motor de visualizaciones admite un nuevo campo opcional `time_granularity` con valores `raw`, `month` y `year`. Se implementó de forma compatible con:
- SQL Server: `CONVERT(VARCHAR(7), fecha, 120)` para meses.
- PostgreSQL: `TO_CHAR(fecha, 'YYYY-MM')`.
- SQLite/Excel: `strftime('%Y-%m', fecha)`.

Los valores `AAAA-MM` se ordenan cronológicamente. La agrupación temporal se autoriza **solo** sobre columnas con tipo fecha o reconocidas como fecha por el modelo semántico. El campo es opcional y el valor predeterminado `raw` conserva las visualizaciones anteriores.

Para filtrar `2026`, se utilizan los límites `fecha >= '2026-01-01'` y `fecha < '2027-01-01'`, de modo que se incluyen todos los registros con fecha y hora del año solicitado.

## Reglas de seguridad / interpretación

- No se genera SQL libre a partir de la solicitud; las consultas pasan por el validador del constructor ya existente.
- No se inventan columnas, métricas, entidades, datos ni fechas. Si el catálogo muestra más de una medida monetaria plausible, Kenneth pide aclaración.
- El enfoque inicial interpreta entidades verificadas de una tabla a la vez; los cruces entre tablas requieren diseño semántico adicional para evitar multiplicaciones de importes.
- La vista previa no crea registros en el almacén de visualizaciones.
- El usuario confirma el guardado; puede cancelar sin efectos.
- Se revalida la vista al guardar y se comprueba que la fuente física activa coincida con la del borrador.
- Las gráficas vacías se muestran como borradores editables, pero no pueden guardarse hasta obtener registros válidos.

## Estado de desarrollo

Primera integración funcional en `feature/conversational-visualization-drafts-phase-3`, PR #8 abierto en **borrador**. Este incremento cubre creación mediante el chat, previsualización y confirmación desde el constructor. La parte conversacional para **editar, duplicar o eliminar** visualizaciones previamente guardadas aún no está implementada y no debería invocarse automáticamente; siguen disponibles los controles de la biblioteca existente.

Pruebas:
```bash
cd Backend
python -m unittest discover -s tests -p "test_conversational_visualizations.py" -v
python -m app.quality.run --report-dir quality_reports
```

La CI incluye lint/build del frontend y pruebas en Python 3.11 y 3.12. Antes de cerrar el issue #5 hace falta prueba manual con datos reales y revisar la interpretación de solicitudes complejas o que impliquen relaciones entre entidades.
