# Carga de backups PostgreSQL en Kenneth

## Qué implementa

En Configuración → PostgreSQL se puede conectar primero a una base PostgreSQL existente y después cargar archivos de respaldo de `pg_dump`.

Formatos **admitidos**:

- `.backup` y `.dump` cuando son archivos **Custom** de `pg_dump -Fc` (cabecera `PGDMP`).
- `.tar` cuando se generó con `pg_dump -Ft`.

**No se admiten** `.bak` (propio de SQL Server), `.sql` de texto, directorios de `pg_dump -Fd` ni respaldos físicos/base backups de PostgreSQL. Un archivo llamado `.dump` que contenga texto SQL no se puede importar desde esta pantalla. No cambies solamente la extensión: conviértelo a uno de los formatos admitidos.

### Requisitos en Windows

1. Instalar PostgreSQL Client Tools para tener `pg_restore`. Comprobar en PowerShell: `pg_restore --version`.
2. Si el ejecutable no está en el PATH, definir `PG_RESTORE_BIN` con la ruta absoluta al `pg_restore.exe` correspondiente a la versión de PostgreSQL del respaldo.
3. Agregar a `Backend/.env`:

```dotenv
PG_BACKUP_UPLOAD_ENABLED=1
# Opcional, si PostgreSQL/bin no está en PATH del backend:
# PG_RESTORE_BIN=C:\Program Files\PostgreSQL\17\bin\pg_restore.exe
```

4. Reiniciar FastAPI para leer las variables de entorno.
5. En Configuración → PostgreSQL, conectar una base **ya existente** del servidor destino; el usuario necesita permiso `CREATEDB` y permisos suficientes para restaurar los objetos. También debe poder conectarse a la nueva base. Si el respaldo contiene extensiones que requieren privilegios elevados, la restauración puede fallar.
6. En la sección **Cargar respaldo PostgreSQL**, seleccionar el archivo y pulsar **Cargar, restaurar y analizar**.

La carga usa la conexión PostgreSQL activa para conocer **host, puerto, usuario, contraseña y SSL**. `pg_restore` es invocado en el backend, sin shell ni contraseña en los argumentos. El límite actual es **2 GB** por carga; para archivos grandes el proceso puede tardar minutos.

### Crear un respaldo de prueba

```powershell
pg_dump -h localhost -p 5432 -U postgres -F c -f tienda.backup tienda
# Alternativa TAR:
pg_dump -h localhost -p 5432 -U postgres -F t -f tienda.tar tienda
```

Sube únicamente un respaldo que hayas generado y controles tú mismo. Aunque el archivo de tipo Custom se inspecciona antes de restaurar, PostgreSQL ejecutará definiciones SQL del respaldo con los privilegios del usuario conectado. No habilites la función en un backend público sin autenticación/autorización.

## Comportamiento de la importación

1. Comprueba la extensión y la habilitación administrativa `PG_BACKUP_UPLOAD_ENABLED=1`.
2. Exige una conexión PostgreSQL activa, nunca crea otra a partir del archivo.
3. Guarda el archivo en una carpeta temporal privada del backend y limita el tamaño.
4. Verifica la cabecera Custom cuando corresponde y consulta el contenido con `pg_restore --list` **antes de crear la base**.
5. Crea un nombre único `upload_<archivo>_<identificador>` y ejecuta `CREATE DATABASE ... TEMPLATE template0` en el mismo servidor; no usa `--clean` ni `--create` de pg_restore.
6. Restaura con `--no-owner --no-privileges --no-tablespaces --single-transaction --exit-on-error`.
7. Verifica que exista al menos una tabla visible en `public` y que el usuario pueda abrir la nueva base.
8. **Solo después del éxito** activa la base restaurada y ejecuta detección de dominio, modelo semántico y dashboard automático.
9. Si falla antes de activar, intenta eliminar **solo** la nueva base que creó para esa carga, y conserva intacta la conexión anterior. Los archivos temporales se borran al terminar.

Nota: la base restaurada permanece en el servidor después de activarse; Kenneth no la elimina al cerrar el navegador. La opción de activación es explícita y no restaura encima de otra base.

## API y respuesta

`POST /api/database/upload/postgresql-backup`, cuerpo `multipart/form-data` con campo `file`.

Al completar devuelve `uploaded: true`, `engine: postgresql`, metadatos `restore`, `database`, `tables`, `business_domain`, `semantic_model_v2` y `dashboard`, similar a la carga `.bak` de SQL Server.

Los errores de formato, configuración no habilitada o fuente incorrecta se devuelven como HTTP 422; los errores de cliente PostgreSQL/privilegios/restauración como HTTP 400. Los errores del dashboard no revierten una restauración válida.

## Pruebas

Desde `Backend`:

```powershell
python -m unittest tests.test_assistant_postgresql_backup -v
python -m app.quality.run
```

Las pruebas nuevas usan simulaciones para **no crear ni borrar ninguna base PostgreSQL real**. Los tests verifican formato, permisos, nombres aleatorios, ausencia de sobreescritura, limpieza, control de errores, y respuesta HTTP. Para confirmar el funcionamiento de `pg_restore` de extremo a extremo todavía hace falta un servidor PostgreSQL **aislado de pruebas** con un respaldo generado para ese entorno; no se ha ejecutado aquí contra una instancia real.
