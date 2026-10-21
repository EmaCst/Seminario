# Kenneth — Fase 4 / Incremento 1: aislamiento al cambiar de fuente

## Objetivo

Evitar cualquier reutilización accidental de información de una base anterior cuando Kenneth activa una conexión nueva, cambia de proveedor o importa un archivo. El comportamiento es el mismo para SQL Server, PostgreSQL, respaldos SQL/PG y Excel/SQLite.

Esta entrega **no significa que la Fase 4 esté terminada**: la capa actual de conexión sigue siendo global al proceso. El aislamiento total por usuario/sesión, autorización y configuración para producción están pendientes.

## Dos identificadores distintos

`GET /api/database/status` incorpora dos campos:

- `revision`: valor aleatorio nuevo **en cada activación exitosa**, incluso cuando se reconecta la misma base. Es una generación temporal para detectar si una petición o una vista pertenece a una conexión anterior.
- `source_identity`: huella no secreta y estable del origen físico. Distingue, por ejemplo, `ventas` en host A frente a `ventas` en host B y dos Excel cargados de forma distinta. Nunca se deriva de la contraseña. Permite guardar diseños asociados a una fuente sin mezclarlos con otra.

Ambos son identificadores de consistencia, **no credenciales ni tokens de autenticación**.

## Backend

El `DatabaseManager` rota la revisión al activar un motor, después de comprobar la conexión. Si el intento falla, no cambia la revisión ni reemplaza el motor anterior.

La capa `source_guard` revisa las rutas que consultan datos empresariales (`/api/*` y `/ask-db`), exceptuando las rutas que prueban o activan la conexión.

- El frontend envía `X-Kenneth-Source-Revision` en las consultas.
- Si la revisión del cliente ya no corresponde a la activa, responde HTTP **409** con `code=SOURCE_CHANGED`.
- Si la fuente cambia **mientras se calcula** una respuesta, esta se descarta y devuelve el mismo HTTP 409. No se entrega silenciosamente la respuesta elaborada con la revisión anterior.
- Las respuestas empresariales incluyen `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache` y, cuando existe una conexión, la revisión actual en una cabecera accesible al navegador.
- Clientes API anteriores sin la cabecera siguen funcionando temporalmente, pero no cuentan con el rechazo anticipado de revisiones obsoletas. Se conserva la detección de cambios durante su procesamiento para compatibilidad.

**Límite conocido:** una comprobación después de la ejecución impide entregar resultados antiguos, pero no proporciona aislamiento transaccional perfecto entre peticiones concurrentes. Especialmente, las modificaciones o restauraciones de fuentes requieren un administrador por sesión y permisos. El objetivo del resto de Fase 4 es terminar ese rediseño.

## Frontend

La capa `services/api.js` centraliza las peticiones, la generación activa y la respuesta a errores 409. Al activar una conexión se consulta siempre el estado de la fuente, **incluso si falla el análisis semántico posterior**.

`DashboardProvider` consulta el estado al iniciar el navegador y periódicamente, y recibe avisos directos tras activaciones o cambios en otras pestañas (BroadcastChannel).

En cada generación nueva se desmontan y reconstruyen los componentes vinculados a los datos:

- conversación, aclaraciones pendientes y borradores de gráficas en Kenneth;
- indicadores de Dashboard/Analítica, previsualizaciones y exploraciones de tablas;
- pronósticos y anomalías;
- opciones y vista previa de reportes;
- formularios de conexión y análisis de la fuente anterior.

El estado de las tarjetas y el orden del Dashboard se guardan bajo `source_identity`, de modo que nunca se reutiliza el orden/layout de otra fuente. Las preferencias **personales** (idioma, colores, nombre de perfil, logotipo) se mantienen.

El navegador invalida respuestas rezagadas que hayan comenzado con otra generación. Se mantiene el estado de conexión visible en Configuración después de limpiar los formularios anteriores.

## Visualizaciones persistidas

El almacén `~/.kenneth/visualizations.json` continúa siendo el mismo y no se borra. Cada visualización nueva se asocia a una clave que incluye el identificador de la fuente física. Se impide leer/modificar/borrar desde otra fuente, aunque el nombre de la base sea igual.

**Compatibilidad de elementos antiguos:** las entradas creadas con la clave histórica `provider:database` se conservan en el archivo, pero dejan de asignarse automáticamente a una fuente física porque no es posible demostrar a qué servidor pertenecían. Una migración solo debería hacerse con aprobación explícita y después de verificar el origen.

## Configuración de API

Frontend: `VITE_API_URL` es opcional; su valor predeterminado para desarrollo local es `http://127.0.0.1:8000`.

Ejemplo en `Frontend/.env.local` (no subir credenciales):
```
VITE_API_URL=http://localhost:8000
```

Las claves de entornos de producción y secretos del servidor deben administrarse fuera del repositorio.

## Pruebas automatizadas

```bash
cd Backend
python -m unittest discover -s tests -p 'test_source_isolation_phase4.py' -v
```

Incluidas en GitHub Actions para Python 3.11 y 3.12. Comprueban:
- reconectar la misma base → identidad igual, revisión distinta;
- mismo nombre de base en servidores distintos → identidades distintas;
- subir Excel distinto → identidades distintas;
- fallo al conectar → se conserva la conexión y revisión previas;
- petición con revisión caducada y cambio durante la petición → 409;
- ausencia de caché HTTP en resultados;
- visualizaciones guardadas aisladas por origen, incluyendo claves antiguas.

La CI también comprueba las pruebas de ML, informes, visualizaciones y compilación del frontend.

## Checklist de validación manual

1. Conecta SQL Server, pregunta algo a Kenneth y prepara una gráfica sin guardarla.
2. Cambia a PostgreSQL: el chat debe comenzar de cero, las métricas se recalculan y las gráficas antiguas no se muestran.
3. Importa un Excel: confirma que ni gráficos, ni análisis, ni borradores de las bases anteriores aparezcan.
4. Abre dos pestañas: cambia la fuente en una y comprueba que la otra limpie el contexto.
5. Repite la conexión con la misma base: debe reiniciar estado en memoria; los diseños guardados para **esa misma fuente física** pueden permanecer disponibles, sin mostrar los de otra.
6. Comprueba bases con el mismo nombre en dos servidores y archivos Excel con el mismo nombre pero distinto contenido.
7. Inicia una consulta larga antes de cambiar la conexión: debe terminar con conflicto en lugar de mostrar datos de otra fuente.
8. Confirma que cambiar el tema, idioma u otras preferencias personales no borre esas elecciones.
9. Verifica que la UI comunica errores de conectividad y activaciones fallidas sin atribuirlos a una base recién cargada.

### Trabajo posterior

- Sustituir `DatabaseManager` global por contextos de fuente aislados por usuario/sesión con autorización para fuentes y operaciones.
- Mejorar auditoría/AST de SQL y establecer roles de sólo lectura, timeouts y máximos de filas.
- Descomponer `app/main.py` en routers y servicios, tipar respuestas, perfilar consultas y endurecer la configuración de despliegue.
- Incorporar pruebas de integración reales para los tres proveedores, cambios concurrentes y aislamiento entre sesiones.
