import { useContext, useState } from 'react';
import { FileArchive, UploadCloud } from 'lucide-react';

import { DashboardContext } from '../context/DashboardContext';
import { uploadSqlServerBackup } from '../services/api';


export const DatabaseUpload = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);

  const isSpanish = language === 'es';

  const handleUpload = async () => {
    if (!file) {
      setStatus({ type: 'error', message: isSpanish ? 'Selecciona un archivo .bak.' : 'Select a .bak file.' });
      return;
    }

    setLoading(true);
    setResult(null);
    setStatus({ type: 'info', message: isSpanish ? 'Subiendo, restaurando y analizando la base...' : 'Uploading, restoring and analyzing database...' });

    try {
      const response = await uploadSqlServerBackup(file);
      setResult(response);
      setStatus({
        type: 'success',
        message: isSpanish
          ? `Base cargada correctamente como ${response.database}.`
          : `Database loaded successfully as ${response.database}.`,
      });
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
      <div className="flex items-start gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
          <UploadCloud size={21} />
        </div>
        <div>
          <h3 className="text-lg font-bold" style={{ color: colors.text }}>
            {isSpanish ? 'Cargar base de datos' : 'Upload database'}
          </h3>
          <p className="text-sm mt-1" style={{ color: colors.muted }}>
            {isSpanish
              ? 'Primera versión: backups .bak de Microsoft SQL Server. El sistema restaura el archivo, activa la base y la analiza automáticamente.'
              : 'First version: Microsoft SQL Server .bak backups. The system restores, activates and analyzes the database automatically.'}
          </p>
        </div>
      </div>

      <label
        className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-5 text-center"
        style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}
      >
        <FileArchive size={30} style={{ color: theme.primary }} />
        <span className="mt-3 font-bold" style={{ color: colors.text }}>
          {file?.name || (isSpanish ? 'Seleccionar archivo .bak' : 'Select .bak file')}
        </span>
        <span className="mt-1 text-xs" style={{ color: colors.muted }}>
          {isSpanish ? 'Límite actual: 2 GB' : 'Current limit: 2 GB'}
        </span>
        <input
          type="file"
          accept=".bak"
          className="hidden"
          onChange={(event) => {
            setFile(event.target.files?.[0] || null);
            setStatus(null);
            setResult(null);
          }}
        />
      </label>

      <button
        type="button"
        disabled={loading || !file}
        onClick={handleUpload}
        className="mt-4 w-full rounded-xl px-4 py-3 font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50"
        style={{ backgroundColor: theme.primary }}
      >
        <UploadCloud size={18} />
        {loading
          ? (isSpanish ? 'Procesando backup...' : 'Processing backup...')
          : (isSpanish ? 'Cargar y analizar' : 'Upload and analyze')}
      </button>

      {status && (
        <div
          className="mt-4 rounded-xl border px-4 py-3 text-sm font-medium"
          style={{
            backgroundColor: status.type === 'success' ? `${theme.primary}12` : status.type === 'error' ? '#ef444412' : colors.cardSoft,
            borderColor: status.type === 'success' ? `${theme.primary}35` : status.type === 'error' ? '#ef444435' : colors.border,
            color: status.type === 'error' ? '#dc2626' : colors.text,
          }}
        >
          {status.message}
        </div>
      )}

      {result && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{isSpanish ? 'Base activa' : 'Active database'}</div>
            <div className="mt-1 font-extrabold break-all" style={{ color: theme.primary }}>{result.database}</div>
          </div>
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{isSpanish ? 'Dominio' : 'Domain'}</div>
            <div className="mt-1 font-extrabold" style={{ color: colors.text }}>{result.business_domain?.primary || '—'}</div>
          </div>
          <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{isSpanish ? 'Tablas' : 'Tables'}</div>
            <div className="mt-1 text-lg font-extrabold" style={{ color: colors.text }}>{result.tables?.length ?? 0}</div>
          </div>
        </div>
      )}
    </section>
  );
};
