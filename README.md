# Kenneth — AI Business Assistant

Sistema de análisis empresarial con **FastAPI**, **React/Vite**, bases de datos SQL Server/PostgreSQL, importación de Excel y asistente local con **Ollama (Gemma 3 4B)**.

## Requisitos

- **Git**
- **Python 3** y `pip` (recomendado: Python 3.11 o 3.12)
- **Node.js** compatible con Vite 8 (recomendado: Node.js 22.12+)
- **Ollama** instalado y en ejecución, para usar Kenneth
- **Una fuente de datos**: SQL Server, PostgreSQL o un archivo Excel
- Si usas **SQL Server**: instalar **Microsoft ODBC Driver 18 for SQL Server**. En Windows, el acceso con autenticación integrada requiere permisos apropiados.

> No necesitas instalar SQL Server ni PostgreSQL si solo vas a importar Excel. Sin embargo, las funciones de análisis requieren una fuente de datos activa.

## 1. Clonar el proyecto

Abre PowerShell o una terminal:

```powershell
git clone https://github.com/EmaCst/Seminario.git
cd Seminario
git checkout feature/custom-visualization-engine
```

> Esta rama contiene las funcionalidades de desarrollo actuales. Para trabajar con otra rama, cambia el nombre en `git checkout`.

## 2. Instalar e iniciar el backend

En una **primera terminal**, desde la carpeta del repositorio:

```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

En macOS/Linux, activa el entorno con `source .venv/bin/activate` en lugar del comando de PowerShell.

Backend: **http://127.0.0.1:8000**  
Documentación interactiva: **http://127.0.0.1:8000/docs**

Si PowerShell bloquea la activación del entorno, puedes ejecutar directamente `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` y `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.

### Conexión SQL Server opcional al iniciar

Puedes crear un archivo `Backend/.env`:

```dotenv
DB_SERVER=localhost
DB_DATABASE=NombreDeTuBase
DB_USERNAME=
DB_PASSWORD=
DB_DRIVER=ODBC Driver 18 for SQL Server
```

Con `DB_USERNAME` vacío, el backend intenta autenticación integrada de Windows. También puedes iniciar **sin .env** y conectar la base de datos desde la interfaz. **No subas contraseñas ni archivos .env a Git.**

## 3. Preparar Ollama (Kenneth)

Instala Ollama desde [ollama.com](https://ollama.com/), inicia el servicio y descarga el modelo:

```powershell
ollama pull gemma3:4b
```

En instalaciones donde Ollama no esté ejecutándose como servicio, inicia `ollama serve` en otra terminal.

> El modelo configurado en el código es `gemma3:4b`. Sin Ollama o sin el modelo descargado, las funciones del asistente de IA no podrán responder correctamente.

## 4. Instalar e iniciar el frontend

Abre una **segunda terminal** en el repositorio:

```powershell
cd Frontend
npm install
npm run dev
```

Abre **http://localhost:5173/** en el navegador.

El frontend está configurado para comunicarse con el backend en `http://127.0.0.1:8000`. Mantén ambas terminales abiertas mientras usas el sistema.

## 5. Conectar tus datos

Desde la interfaz, entra a **Configuración** y elige una fuente:

- **SQL Server:** servidor, base de datos y credenciales (o autenticación integrada).
- **PostgreSQL:** host, puerto (predeterminado 5432), base de datos, usuario y contraseña.
- **Excel:** carga un libro compatible para que el sistema lo importe como fuente de datos local.
- **Respaldo SQL Server (.bak):** requiere un servidor SQL Server activo y permisos de restauración.

Una vez conectada la fuente, explora **Dashboard**, **Analítica**, **Predicciones**, el **Creador de visualizaciones** y el asistente **Kenneth**. Las visualizaciones dependen de las tablas y campos disponibles.

## 6. Volver a iniciar el sistema

En usos posteriores no es necesario reinstalar dependencias.

**Terminal 1 — Backend**

```powershell
cd Seminario\Backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

**Terminal 2 — Frontend**

```powershell
cd Seminario\Frontend
npm run dev
```

Comprueba también que Ollama esté ejecutándose si vas a utilizar Kenneth.

## 7. Actualizar el código

Desde la raíz del repositorio:

```powershell
git checkout feature/custom-visualization-engine
git pull origin feature/custom-visualization-engine
```

Si cambian las dependencias, ejecuta nuevamente `python -m pip install -r requirements.txt` dentro de `Backend` y `npm install` dentro de `Frontend`.

## Solución de problemas

| Problema | Qué revisar |
| --- | --- |
| El frontend no carga | Que `npm run dev` esté activo y no haya errores de Vite |
| El frontend no conecta con la API | Que FastAPI esté activo en el puerto **8000** |
| Kenneth no responde | Que Ollama esté activo y exista el modelo `gemma3:4b` |
| Error `pyodbc` o conexión SQL Server | ODBC Driver 18, nombre del servidor, permisos y credenciales |
| Error al conectar PostgreSQL | Servidor activo, puerto, usuario, contraseña y acceso de red |
| No aparecen estadísticas | Conectar o importar primero una fuente de datos compatible |
| `npm install` falla por versión de Node | Actualizar Node.js a una versión compatible con Vite 8 |

## Tecnologías principales

- **Frontend:** React 19, Vite 8, Tailwind CSS, Recharts y Lucide.
- **Backend:** Python, FastAPI, SQLAlchemy y Uvicorn.
- **Datos:** SQL Server, PostgreSQL y Excel (importado a SQLite).
- **IA:** Ollama con Gemma 3 4B.
- **Análisis predictivo:** scikit-learn.

---

**Proyecto académico — Universidad Mariano Gálvez de Guatemala.**
