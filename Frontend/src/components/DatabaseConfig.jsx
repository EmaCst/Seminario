import { useContext, useState } from 'react';
import { Database, Eye, EyeOff, Save, TestTube2, BrainCircuit, Network, Table2 } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { connectDatabase, testDatabaseConnection } from '../services/api';

const initialConfig = {
  server: '',
  database: '',
  username: '',
  password: '',
  driver: 'ODBC Driver 18 for SQL Server',
};

const domainLabels = {
  retail: 'Comercio / Retail',
  education: 'Educación',
  healthcare: 'Salud / Hospital',
  transportation: 'Transporte',
  hospitality: 'Hotelería',
  restaurant: 'Restaurante',
  professional_services: 'Servicios profesionales',
  finance_accounting: 'Finanzas / Contabilidad',
  manufacturing: 'Manufactura',
  human_resources: 'Recursos humanos',
};

export const DatabaseConfig = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [config, setConfig] = useState(initialConfig);
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const isSpanish = language === 'es';

  const updateField = (field) => (event) => {
    setConfig((prev) => ({ ...prev, [field]: event.target.value }));
    setStatus(null);
  };

  const getPayload = () => ({
    server: config.server.trim(),
    database: config.database.trim(),
    username: config.username.trim() || null,
    password: config.password || null,
    driver: config.driver.trim() || 'ODBC Driver 18 for SQL Server',
  });

  const validate = () => {
    if (!config.server.trim() || !config.database.trim()) {
      setStatus({ type: 'error', message: isSpanish ? 'Servidor y base de datos son obligatorios.' : 'Server and database are required.' });
      return false;
    }
    return true;
  };

  const handleTest = async () => {
    if (!validate()) return;
    setLoading(true);
    setStatus({ type: 'info', message: isSpanish ? 'Probando conexión...' : 'Testing connection...' });

    try {
      await testDatabaseConnection(getPayload());
      setStatus({ type: 'success', message: isSpanish ? 'Conexión exitosa.' : 'Connection successful.' });
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    if (!validate()) return;
    setLoading(true);
    setAnalysis(null);
    setStatus({ type: 'info', message: isSpanish ? 'Conectando y analizando la base de datos...' : 'Connecting and analyzing database...' });

    try {
      const result = await connectDatabase(getPayload());
      setAnalysis(result);
      setStatus({
        type: 'success',
        message: isSpanish
          ? `Base ${result.database} conectada y analizada correctamente.`
          : `Database ${result.database} connected and analyzed successfully.`,
      });
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  const semantic = analysis?.semantic_model_v2?.semantic_model;
  const domain = analysis?.business_domain;
  const entities = semantic?.entities ? Object.entries(semantic.entities) : [];

  return (
    <div className="space-y-5">
      <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
            <Database size={20} />
          </div>
          <div>
            <h3 className="text-lg font-bold" style={{ color: colors.text }}>{isSpanish ? 'Conexión a base de datos' : 'Database connection'}</h3>
            <p className="text-sm mt-1" style={{ color: colors.muted }}>
              {isSpanish ? 'Conecta una base y el sistema detectará automáticamente su dominio y estructura semántica.' : 'Connect a database and the system will automatically detect its domain and semantic structure.'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            ['server', 'Servidor', 'Ej. localhost\\SQLEXPRESS'],
            ['database', 'Base de datos', 'Nombre de la base de datos'],
            ['username', 'Usuario', 'Opcional si usas autenticación integrada'],
            ['driver', 'Driver', 'ODBC Driver 18 for SQL Server'],
          ].map(([key, label, placeholder]) => (
            <label key={key} className="space-y-1.5">
              <span className="text-sm font-semibold" style={{ color: colors.text }}>{label}</span>
              <input value={config[key]} onChange={updateField(key)} placeholder={placeholder} className="w-full rounded-xl border px-4 py-3 outline-none transition focus:ring-2" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text, '--tw-ring-color': `${theme.primary}55` }} />
            </label>
          ))}

          <label className="space-y-1.5 md:col-span-2">
            <span className="text-sm font-semibold" style={{ color: colors.text }}>Contraseña</span>
            <div className="relative">
              <input type={showPassword ? 'text' : 'password'} value={config.password} onChange={updateField('password')} placeholder="Opcional" className="w-full rounded-xl border px-4 py-3 pr-12 outline-none transition focus:ring-2" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text, '--tw-ring-color': `${theme.primary}55` }} />
              <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg" style={{ color: colors.muted }}>
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
        </div>

        <div className="mt-5 flex flex-col sm:flex-row gap-3">
          <button disabled={loading} type="button" onClick={handleTest} className="rounded-xl border px-4 py-3 font-bold flex items-center justify-center gap-2 disabled:opacity-50" style={{ color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}>
            <TestTube2 size={18} /> {isSpanish ? 'Probar conexión' : 'Test connection'}
          </button>
          <button disabled={loading} type="button" onClick={handleConnect} className="rounded-xl px-4 py-3 font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50" style={{ backgroundColor: theme.primary }}>
            <Save size={18} /> {isSpanish ? 'Conectar y analizar' : 'Connect and analyze'}
          </button>
        </div>

        {status && (
          <div className="mt-4 rounded-xl border px-4 py-3 text-sm font-medium" style={{ backgroundColor: status.type === 'success' ? `${theme.primary}12` : status.type === 'error' ? '#ef444412' : colors.cardSoft, borderColor: status.type === 'success' ? `${theme.primary}35` : status.type === 'error' ? '#ef444435' : colors.border, color: status.type === 'error' ? '#dc2626' : colors.text }}>
            {status.message}
          </div>
        )}
      </section>

      {analysis && (
        <section className="p-5 sm:p-6 rounded-2xl border shadow-sm space-y-5" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}><BrainCircuit size={21} /></div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: colors.text }}>Análisis automático</h3>
              <p className="text-sm" style={{ color: colors.muted }}>{analysis.database}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
              <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>Tipo de negocio</div>
              <div className="mt-1 text-lg font-extrabold" style={{ color: theme.primary }}>{domainLabels[domain?.primary] || domain?.primary || 'No determinado'}</div>
            </div>
            <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
              <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>Confianza</div>
              <div className="mt-1 text-lg font-extrabold" style={{ color: colors.text }}>{domain?.confidence || '—'}</div>
            </div>
            <div className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
              <div className="text-xs font-bold uppercase" style={{ color: colors.muted }}>Tablas detectadas</div>
              <div className="mt-1 text-lg font-extrabold" style={{ color: colors.text }}>{analysis.tables?.length ?? 0}</div>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3"><Table2 size={18} style={{ color: theme.primary }} /><h4 className="font-bold" style={{ color: colors.text }}>Entidades entendidas por el Semantic Mapper 2.0</h4></div>
            {entities.length ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {entities.map(([role, entity]) => (
                  <div key={role} className="rounded-xl border p-4" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-extrabold" style={{ color: theme.primary }}>{role}</span>
                      <span className="text-xs font-bold rounded-full px-2 py-1" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>{entity.confidence}</span>
                    </div>
                    <div className="text-sm mt-1" style={{ color: colors.text }}>Tabla: <strong>{entity.table}</strong></div>
                    <div className="text-xs mt-2" style={{ color: colors.muted }}>
                      {Object.entries(entity.columns || {}).map(([semanticName, column]) => `${semanticName} → ${column}`).join(' · ') || 'Sin columnas semánticas adicionales'}
                    </div>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm" style={{ color: colors.muted }}>No se detectaron entidades con suficiente confianza.</p>}
          </div>

          <div className="rounded-xl border p-4" style={{ borderColor: colors.border }}>
            <div className="flex items-center gap-2 font-bold mb-2" style={{ color: colors.text }}><Network size={18} /> Relaciones detectadas: {semantic?.relations?.length ?? 0}</div>
            <p className="text-sm" style={{ color: colors.muted }}>
              Tablas todavía sin mapear: {semantic?.unmapped_tables?.length ? semantic.unmapped_tables.join(', ') : 'ninguna'}
            </p>
          </div>
        </section>
      )}
    </div>
  );
};
