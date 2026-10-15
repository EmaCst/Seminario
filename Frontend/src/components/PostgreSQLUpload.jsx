import { useContext, useEffect, useState } from 'react';
import { AlertTriangle, FileArchive, UploadCloud } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { getPostgreSQLBackupSettings, setPostgreSQLBackupEnabled, uploadPostgreSQLBackup } from '../services/api';

const ALLOWED_EXTENSIONS = ['.backup', '.dump', '.tar'];
const MAX_BYTES = 2 * 1024 * 1024 * 1024;

export const PostgreSQLUpload = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [permission, setPermission] = useState(null);
  const [settingLoading, setSettingLoading] = useState(false);
  const [settingError, setSettingError] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const es = language === 'es';

  useEffect(() => {
    let mounted = true;
    getPostgreSQLBackupSettings()
      .then((data) => { if (mounted) setPermission(data); })
      .catch((error) => { if (mounted) setSettingError(error.message); });
    return () => { mounted = false; };
  }, []);

  const changePermission = async (enabled) => {
    setSettingLoading(true);
    setSettingError('');
    try {
      const updated = await setPostgreSQLBackupEnabled(enabled);
      setPermission(updated);
    } catch (error) {
      setSettingError(error.message);
      // Keep the checkbox in sync with the backend, even after a failed write.
      try { setPermission(await getPostgreSQLBackupSettings()); } catch { /* preserve original error */ }
    } finally {
      setSettingLoading(false);
    }
  };

  const chooseFile = (selected) => {
    setResult(null);
    if (selected && !ALLOWED_EXTENSIONS.some(ext => selected.name.toLowerCase().endsWith(ext))) {
      setFile(null);
      setStatus({ type: 'error', message: es
        ? 'Selecciona un archivo .backup, .dump (Custom) o .tar. Los .sql no están admitidos.'
        : 'Select a .backup, .dump (Custom) or .tar archive. Plain .sql is unsupported.' });
      return;
    }
    if (selected && selected.size > MAX_BYTES) {
      setFile(null);
      setStatus({ type: 'error', message: es ? 'El archivo supera los 2 GB.' : 'File is larger than 2 GB.' });
      return;
    }
    setFile(selected || null);
    setStatus(null);
  };

  const upload = async () => {
    if (!file || loading || !permission?.enabled) return;
    setLoading(true);
    setResult(null);
    setStatus({ type: 'info', message: es
      ? 'Subiendo y restaurando en una base nueva; puede tardar varios minutos...'
      : 'Uploading and restoring into a new database; this may take several minutes...' });
    try {
      const response = await uploadPostgreSQLBackup(file);
      setResult(response);
      setStatus(response.analysis_warning
        ? { type: 'info', message: es
          ? 'Base restaurada y activada: ' + response.database + '. ' + response.analysis_warning
          : 'Database restored and activated: ' + response.database + '. Analysis pending: ' + response.analysis_warning }
        : { type: 'success', message: es
          ? 'Base restaurada y activada correctamente: ' + response.database
          : 'Database restored and activated: ' + response.database });
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
      <div className="flex items-start gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
          <UploadCloud size={21} />
        </div>
        <div>
          <h3 className="text-lg font-bold" style={{ color: colors.text }}>
            {es ? 'Cargar respaldo PostgreSQL' : 'Upload PostgreSQL backup'}
          </h3>
          <p className="text-sm mt-1" style={{ color: colors.muted }}>
            {es
              ? 'Conecta primero PostgreSQL arriba. Después carga un respaldo Custom (.backup/.dump) o TAR (.tar). Kenneth creará una base nueva, restaurará y analizará sus datos.'
              : 'Connect PostgreSQL above first. Then upload a Custom (.backup/.dump) or TAR (.tar) archive. Kenneth creates a new database and analyzes it.'}
          </p>
        </div>
      </div>
      <div className="flex items-start gap-2 rounded-xl border px-4 py-3 mb-5 text-sm"
        style={{ borderColor: colors.border, backgroundColor: colors.cardSoft, color: colors.muted }}>
        <AlertTriangle size={18} className="shrink-0 mt-0.5" />
        <span>{es
          ? 'Solo respaldos confiables. Requiere pg_restore y permiso CREATEDB. Habilita la carga con la casilla de abajo; como alternativa, usa PG_BACKUP_UPLOAD_ENABLED=1 en Backend/.env. No sobrescribe la base actual.'
          : 'Trusted backups only. Requires pg_restore and CREATEDB. Enable restores with the checkbox below, or use PG_BACKUP_UPLOAD_ENABLED=1 in Backend/.env. Never overwrites the active database.'}</span>
      </div>
      <div className="mb-5 rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
        <label className="flex items-start gap-3" style={{ color: colors.text }}>
          <input type="checkbox" className="mt-1 h-5 w-5 shrink-0"
            aria-label={es ? 'Habilitar carga de respaldos PostgreSQL' : 'Enable PostgreSQL backup uploads'}
            checked={Boolean(permission?.enabled)}
            disabled={settingLoading || loading || !permission?.manageable}
            onChange={(event) => changePermission(event.target.checked)}
            style={{ accentColor: theme.primary }} />
          <span>
            <strong className="block text-sm">{es ? 'Habilitar carga de respaldos PostgreSQL' : 'Enable PostgreSQL backup uploads'}</strong>
            <span className="block mt-1 text-xs" style={{ color: colors.muted }}>
              {es
                ? 'Equivale a PG_BACKUP_UPLOAD_ENABLED=1 durante esta sesión del backend. El cambio desde aquí es temporal y solo está permitido en localhost.'
                : 'Equivalent to PG_BACKUP_UPLOAD_ENABLED=1 for this backend session. Changes here are temporary and only available on localhost.'}
            </span>
          </span>
        </label>
        {!permission?.manageable && permission && (
          <p className="mt-3 text-xs" style={{ color: colors.muted }}>
            {es ? 'Control remoto bloqueado. El administrador puede habilitarlo en Backend/.env.' : 'Remote control blocked. An administrator may enable it in Backend/.env.'}
          </p>
        )}
        {permission === null && !settingError && (
          <p className="mt-3 text-xs" style={{ color: colors.muted }}>{es ? 'Consultando permiso...' : 'Checking permission...'}</p>
        )}
        {settingError && <p role="alert" className="mt-3 text-xs text-red-600">{settingError}</p>}
      </div>
      <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-5 text-center"
        style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
        <FileArchive size={30} style={{ color: theme.primary }} />
        <span className="mt-3 font-bold break-all" style={{ color: colors.text }}>
          {file?.name || (es ? 'Seleccionar .backup, .dump o .tar' : 'Select .backup, .dump or .tar')}
        </span>
        <span className="mt-1 text-xs" style={{ color: colors.muted }}>
          {es ? 'Límite: 2 GB · siempre restaura en una base nueva' : 'Limit: 2 GB · always restores to a new database'}
        </span>
        <input type="file" accept=".backup,.dump,.tar" disabled={loading} className="hidden"
          onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
      </label>
      <button type="button" disabled={loading || !file || !permission?.enabled} onClick={upload}
        className="mt-4 w-full rounded-xl px-4 py-3 font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50"
        style={{ backgroundColor: theme.primary }}>
        <UploadCloud size={18} />
        {loading
          ? (es ? 'Restaurando respaldo...' : 'Restoring backup...')
          : (es ? 'Cargar, restaurar y analizar' : 'Upload, restore and analyze')}
      </button>
      {status && (
        <div role="status" aria-live="polite" className="mt-4 rounded-xl border px-4 py-3 text-sm font-medium"
          style={{
            backgroundColor: status.type === 'success' ? theme.primary + '12' : status.type === 'error' ? '#ef444412' : colors.cardSoft,
            borderColor: status.type === 'success' ? theme.primary + '35' : status.type === 'error' ? '#ef444435' : colors.border,
            color: status.type === 'error' ? '#dc2626' : colors.text,
          }}>{status.message}</div>
      )}
      {result && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{es ? 'Base activa' : 'Active database'}</div>
            <div className="mt-1 font-extrabold break-all" style={{ color: theme.primary }}>{result.database}</div>
          </div>
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{es ? 'Dominio' : 'Domain'}</div>
            <div className="mt-1 font-extrabold" style={{ color: colors.text }}>{result.business_domain?.primary || '—'}</div>
          </div>
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{es ? 'Tablas' : 'Tables'}</div>
            <div className="mt-1 text-lg font-extrabold" style={{ color: colors.text }}>{result.tables?.length ?? result.restore?.table_count ?? 0}</div>
          </div>
        </div>
      )}
    </section>
  );
};
