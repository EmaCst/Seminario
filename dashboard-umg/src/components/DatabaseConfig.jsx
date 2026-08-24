import { useContext, useState } from 'react';
import { Database, Eye, EyeOff, Save, TestTube2 } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';

const initialConfig = {
  server: '',
  database: '',
  username: '',
  password: '',
  driver: '',
};

export const DatabaseConfig = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [config, setConfig] = useState(initialConfig);
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState(null);

  const isSpanish = language === 'es';

  const updateField = (field) => (event) => {
    setConfig((prev) => ({ ...prev, [field]: event.target.value }));
    setStatus(null);
  };

  const payload = {
    DB_SERVER: config.server,
    DB_DATABASE: config.database,
    DB_USERNAME: config.username,
    DB_PASSWORD: config.password,
    DB_DRIVER: config.driver,
  };

  const handleSave = async () => {
    if (Object.values(config).some((value) => !value.trim())) {
      setStatus({ type: 'error', message: isSpanish ? 'Completa todos los campos.' : 'Complete all fields.' });
      return;
    }

    try {
      const response = await fetch('/api/database/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error('Request failed');

      setStatus({
        type: 'success',
        message: isSpanish ? 'Configuración enviada correctamente.' : 'Configuration sent successfully.',
      });
    } catch {
      setStatus({
        type: 'error',
        message: isSpanish
          ? 'No se pudo contactar al backend. Verifica que /api/database/config esté disponible.'
          : 'The backend could not be reached. Verify that /api/database/config is available.',
      });
    }
  };

  const handleTest = async () => {
    if (Object.values(config).some((value) => !value.trim())) {
      setStatus({ type: 'error', message: isSpanish ? 'Completa todos los campos.' : 'Complete all fields.' });
      return;
    }

    setStatus({ type: 'info', message: isSpanish ? 'Probando conexión...' : 'Testing connection...' });

    try {
      const response = await fetch('/api/database/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error('Connection failed');

      setStatus({ type: 'success', message: isSpanish ? 'Conexión exitosa.' : 'Connection successful.' });
    } catch {
      setStatus({ type: 'error', message: isSpanish ? 'No fue posible probar la conexión.' : 'The connection test failed.' });
    }
  };

  const fields = [
    { key: 'server', label: 'DB_SERVER', placeholder: 'Ej. localhost\\SQLEXPRESS' },
    { key: 'database', label: 'DB_DATABASE', placeholder: 'Nombre de la base de datos' },
    { key: 'username', label: 'DB_USERNAME', placeholder: 'Usuario de la base de datos' },
    { key: 'driver', label: 'DB_DRIVER', placeholder: 'Ej. ODBC Driver 17 for SQL Server' },
  ];

  return (
    <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
      <div className="flex items-start gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
          <Database size={20} />
        </div>
        <div>
          <h3 className="text-lg font-bold" style={{ color: colors.text }}>
            {isSpanish ? 'Conexión a base de datos' : 'Database connection'}
          </h3>
          <p className="text-sm mt-1" style={{ color: colors.muted }}>
            {isSpanish
              ? 'Ingresa los valores que normalmente se definirían como variables DB_.'
              : 'Enter the values normally defined as DB_ environment variables.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fields.slice(0, 3).map((field) => (
          <label key={field.key} className="space-y-1.5">
            <span className="text-sm font-semibold" style={{ color: colors.text }}>{field.label}</span>
            <input
              value={config[field.key]}
              onChange={updateField(field.key)}
              placeholder={field.placeholder}
              className="w-full rounded-xl border px-4 py-3 outline-none transition focus:ring-2"
              style={{
                backgroundColor: colors.cardSoft,
                borderColor: colors.border,
                color: colors.text,
                '--tw-ring-color': `${theme.primary}55`,
              }}
            />
          </label>
        ))}

        <label className="space-y-1.5">
          <span className="text-sm font-semibold" style={{ color: colors.text }}>DB_PASSWORD</span>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={config.password}
              onChange={updateField('password')}
              placeholder={isSpanish ? 'Contraseña de la base de datos' : 'Database password'}
              className="w-full rounded-xl border px-4 py-3 pr-12 outline-none transition focus:ring-2"
              style={{
                backgroundColor: colors.cardSoft,
                borderColor: colors.border,
                color: colors.text,
                '--tw-ring-color': `${theme.primary}55`,
              }}
            />
            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg"
              style={{ color: colors.muted }}
              aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        <label className="space-y-1.5 md:col-span-2">
          <span className="text-sm font-semibold" style={{ color: colors.text }}>DB_DRIVER</span>
          <input
            value={config.driver}
            onChange={updateField('driver')}
            placeholder={fields[3].placeholder}
            className="w-full rounded-xl border px-4 py-3 outline-none transition focus:ring-2"
            style={{
              backgroundColor: colors.cardSoft,
              borderColor: colors.border,
              color: colors.text,
              '--tw-ring-color': `${theme.primary}55`,
            }}
          />
        </label>
      </div>

      <div className="mt-5 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={handleTest}
          className="rounded-xl border px-4 py-3 font-bold flex items-center justify-center gap-2 transition hover:-translate-y-0.5"
          style={{ color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}
        >
          <TestTube2 size={18} />
          {isSpanish ? 'Probar conexión' : 'Test connection'}
        </button>
        <button
          type="button"
          onClick={handleSave}
          className="rounded-xl px-4 py-3 font-bold text-white flex items-center justify-center gap-2 transition hover:-translate-y-0.5"
          style={{ backgroundColor: theme.primary }}
        >
          <Save size={18} />
          {isSpanish ? 'Guardar configuración' : 'Save configuration'}
        </button>
      </div>

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

      <p className="mt-4 text-xs leading-5" style={{ color: colors.muted }}>
        {isSpanish
          ? 'Importante: las credenciales se envían al backend y no se guardan en localStorage. No es recomendable conectar directamente el navegador con SQL Server.'
          : 'Important: credentials are sent to the backend and are not stored in localStorage. Direct browser-to-SQL Server connections are not recommended.'}
      </p>
    </section>
  );
};
