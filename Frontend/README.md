# Dashboard UMG – versión modificada

Dashboard en React + Vite con cuatro paletas visuales, modo claro/oscuro e interfaz bilingüe español/inglés.

## Funciones agregadas

- 4 paletas: Azul Profesional, Verde Tecnológico, Morado Elegante y Naranja + Gris.
- Modo claro y modo oscuro.
- Detección inicial automática del modo del sistema mediante `prefers-color-scheme`.
- Detección inicial automática de español/inglés según el idioma del navegador.
- Cambio manual de idioma ES/EN desde el encabezado y Configuración.
- Persistencia de color, modo e idioma usando `localStorage`.
- Diseño responsivo y consistente en Dashboard, menú lateral y Configuración.
- Gráficas y tabla con colores adaptados a cada tema.

## Ejecutar

```bash
npm install
npm run dev
```

Para generar la versión de producción:

```bash
npm run build
```


## Configuración de base de datos desde el frontend

La sección **Configuración → Conexión a base de datos** solicita `DB_SERVER`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` y `DB_DRIVER`.

El frontend envía los datos al backend mediante:

- `POST /api/database/config` para guardar/aplicar la configuración.
- `POST /api/database/test` para probar la conexión.

El frontend no guarda las credenciales en `localStorage`. El backend debe recibirlas y manejar la conexión con SQL Server/ODBC. No se recomienda conectar el navegador directamente a la base de datos.

## Chatbot

Se agregó un botón flotante de chatbot disponible en todas las vistas. La interfaz permite abrir/cerrar el chat y enviar mensajes; para respuestas reales con IA, conecta `src/components/Chatbot.jsx` con el endpoint de tu backend o proveedor de IA.
