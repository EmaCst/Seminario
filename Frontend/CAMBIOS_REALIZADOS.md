# Cambios realizados

## Apariencia
- Se agregaron cuatro temas intercambiables:
  1. Azul Profesional
  2. Verde Tecnológico
  3. Morado Elegante
  4. Naranja + Gris
- Cada paleta adapta menú lateral, encabezados, gráficas, botones, estados y tarjetas.
- Se mejoró la distribución responsiva para escritorio, tablet y móvil.

## Modo claro / oscuro
- Se agregó selector manual desde el encabezado y desde Configuración.
- La primera vez, el sistema detecta automáticamente `prefers-color-scheme` del equipo.
- La elección queda guardada en `localStorage`.

## Español / inglés
- Se agregó selector ES/EN desde el encabezado y Configuración.
- La primera vez, el idioma se detecta desde `navigator.language`.
- Menú, títulos, configuración, gráficas, tabla y estados se traducen.
- La elección queda guardada en `localStorage`.

## Dashboard
- Se reemplazó el espacio de productos por una tabla funcional visual.
- Las gráficas usan automáticamente el color del tema seleccionado.
- Los nombres de meses cambian según el idioma.
- Se corrigió la navegación interna de Analytics/Analítica.

## Verificación
- Código revisado con ESLint sin errores.
- Archivos JSX validados con el parser de Babel.

## Ejecución
```bash
npm install
npm run dev
```

Para producción:
```bash
npm run build
```
