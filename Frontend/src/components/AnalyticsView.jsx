import { useContext, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  Database,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DashboardContext } from '../context/DashboardContext';
import { getAdaptiveAnalytics } from '../services/api';

const roleLabel = (role) => String(role || 'datos').replaceAll('_', ' ');

const formatValue = (value) => {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
};

export const AnalyticsView = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await getAdaptiveAnalytics());
    } catch (err) {
      setError(err.message || 'No fue posible cargar la analítica.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const trend = data?.trend;
  const statusData = data?.status_distribution?.data || [];
  const entityData = useMemo(
    () => (data?.entity_counts || [])
      .slice()
      .sort((a, b) => (b.value || 0) - (a.value || 0))
      .slice(0, 8)
      .map((item) => ({ ...item, label: roleLabel(item.role) })),
    [data],
  );

  if (loading) {
    return (
      <section className="min-h-72 flex items-center justify-center">
        <div className="flex items-center gap-3" style={{ color: colors.muted }}>
          <RefreshCw size={20} className="animate-spin" />
          {language === 'es' ? 'Analizando comportamiento del negocio...' : 'Analyzing business behavior...'}
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1" style={{ color: theme.primary }}>
            <BarChart3 size={22} />
            <span className="text-sm font-bold uppercase tracking-wide">Business Intelligence</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
            {language === 'es' ? 'Analítica' : 'Analytics'}
          </h1>
          <p className="mt-2" style={{ color: colors.muted }}>
            {language === 'es'
              ? 'Tendencias, comparaciones, distribución e insights adaptados automáticamente a la base activa.'
              : 'Trends, comparisons, distributions and insights adapted automatically to the active database.'}
          </p>
        </div>

        <button
          onClick={load}
          className="self-start md:self-auto rounded-xl border px-3 py-2 flex items-center gap-2 font-semibold"
          style={{ backgroundColor: colors.card, borderColor: colors.border, color: theme.primary }}
        >
          <RefreshCw size={17} />
          {language === 'es' ? 'Actualizar' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border p-4" style={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2', color: '#B91C1C' }}>
          {error}
        </div>
      )}

      {!error && data && (
        <>
          <div className="rounded-2xl border p-5 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                <Database size={23} />
              </div>
              <div>
                <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Fuente analizada' : 'Analyzed source'}</p>
                <p className="font-extrabold text-lg" style={{ color: colors.text }}>{data.database || '—'}</p>
                <p className="text-sm capitalize" style={{ color: colors.muted }}>{data.domain || 'generic'} · {data.provider}</p>
              </div>
            </div>
            <div className="text-sm" style={{ color: colors.muted }}>
              {language === 'es' ? 'Dominio detectado automáticamente' : 'Automatically detected domain'}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: colors.muted }}>{language === 'es' ? 'Período actual' : 'Current period'}</p>
              <p className="mt-2 text-2xl font-extrabold" style={{ color: colors.text }}>{trend?.current?.period || '—'}</p>
              <p className="text-sm capitalize" style={{ color: colors.muted }}>{roleLabel(trend?.role)}</p>
            </div>

            <div className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: colors.muted }}>{language === 'es' ? 'Actividad actual' : 'Current activity'}</p>
              <p className="mt-2 text-2xl font-extrabold" style={{ color: theme.primary }}>{formatValue(trend?.current?.total)}</p>
              <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'registros del período' : 'records in period'}</p>
            </div>

            <div className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="flex items-center gap-2" style={{ color: (trend?.change_pct ?? 0) >= 0 ? theme.primary : colors.muted }}>
                {(trend?.change_pct ?? 0) >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                <p className="text-xs font-bold uppercase tracking-wide">{language === 'es' ? 'Cambio mensual' : 'Monthly change'}</p>
              </div>
              <p className="mt-2 text-2xl font-extrabold" style={{ color: colors.text }}>
                {trend?.change_pct == null ? '—' : `${trend.change_pct > 0 ? '+' : ''}${trend.change_pct}%`}
              </p>
              <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'vs. período anterior' : 'vs. previous period'}</p>
            </div>

            <div className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: colors.muted }}>{language === 'es' ? 'Pico observado' : 'Observed peak'}</p>
              <p className="mt-2 text-2xl font-extrabold" style={{ color: colors.text }}>{formatValue(trend?.peak?.total)}</p>
              <p className="text-sm" style={{ color: colors.muted }}>{trend?.peak?.period || '—'}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
            <div className="xl:col-span-2 rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="mb-4">
                <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{language === 'es' ? 'Evolución temporal' : 'Time evolution'}</h2>
                <p className="text-sm capitalize" style={{ color: colors.muted }}>{roleLabel(trend?.role)}</p>
              </div>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend?.data || []}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis dataKey="period" tick={{ fill: colors.muted, fontSize: 12 }} />
                    <YAxis tick={{ fill: colors.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Line type="monotone" dataKey="total" stroke={theme.primary} strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="flex items-center gap-2 mb-4" style={{ color: theme.primary }}>
                <Sparkles size={19} />
                <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{language === 'es' ? 'Insights automáticos' : 'Automatic insights'}</h2>
              </div>
              <div className="space-y-3">
                {(data.insights || []).map((insight, index) => (
                  <div key={`${insight.type}-${index}`} className="rounded-xl border p-3" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                    <p className="font-bold text-sm" style={{ color: colors.text }}>{insight.title}</p>
                    <p className="mt-1 text-sm leading-5" style={{ color: colors.muted }}>{insight.text}</p>
                  </div>
                ))}
                {!data.insights?.length && <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Aún no hay suficientes datos para generar insights.' : 'Not enough data to generate insights yet.'}</p>}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="flex items-center gap-2 mb-4">
                <Activity size={19} style={{ color: theme.primary }} />
                <div>
                  <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{language === 'es' ? 'Distribución por estado' : 'Status distribution'}</h2>
                  <p className="text-sm capitalize" style={{ color: colors.muted }}>{roleLabel(data.status_distribution?.role)}</p>
                </div>
              </div>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={statusData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis dataKey="label" tick={{ fill: colors.muted, fontSize: 11 }} />
                    <YAxis tick={{ fill: colors.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Bar dataKey="total" fill={theme.primary} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="mb-4">
                <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{language === 'es' ? 'Volumen por entidad' : 'Volume by entity'}</h2>
                <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Entidades detectadas por el modelo semántico.' : 'Entities detected by the semantic model.'}</p>
              </div>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={entityData} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis type="number" tick={{ fill: colors.muted, fontSize: 12 }} />
                    <YAxis type="category" dataKey="label" width={100} tick={{ fill: colors.muted, fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Bar dataKey="value" fill={theme.primary} radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
};
