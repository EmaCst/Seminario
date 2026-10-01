import { useContext, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  CalendarRange,
  Database,
  Layers3,
  RefreshCw,
  Sparkles,
  Trophy,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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

const rangeOptions = [
  { value: 3, label: '3M' },
  { value: 6, label: '6M' },
  { value: 12, label: '12M' },
  { value: 0, label: 'Todo' },
];

const rankingGridClass = (count) => {
  if (count <= 1) return 'grid grid-cols-1 gap-4';
  if (count === 2) return 'grid grid-cols-1 lg:grid-cols-2 gap-4';
  return 'grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4';
};

const SectionTitle = ({ icon: Icon, title, subtitle, theme, colors }) => (
  <div className="flex items-start gap-3 mb-4">
    <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
      <Icon size={18} />
    </div>
    <div>
      <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{title}</h2>
      {subtitle && <p className="text-sm" style={{ color: colors.muted }}>{subtitle}</p>}
    </div>
  </div>
);

export const AnalyticsView = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [data, setData] = useState(null);
  const [range, setRange] = useState(12);
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
  const trendData = useMemo(() => {
    const rows = trend?.data || [];
    return range > 0 ? rows.slice(-range) : rows;
  }, [trend, range]);

  const entityData = useMemo(
    () => (data?.entity_counts || [])
      .slice()
      .sort((a, b) => (b.value || 0) - (a.value || 0))
      .slice(0, 10)
      .map((item) => ({ ...item, label: roleLabel(item.role) })),
    [data],
  );

  if (loading) {
    return (
      <section className="min-h-72 flex items-center justify-center">
        <div className="flex items-center gap-3" style={{ color: colors.muted }}>
          <RefreshCw size={20} className="animate-spin" />
          {language === 'es' ? 'Construyendo analítica del negocio...' : 'Building business analytics...'}
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col xl:flex-row xl:items-end xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1" style={{ color: theme.primary }}>
            <BarChart3 size={22} />
            <span className="text-sm font-bold uppercase tracking-wide">Business Intelligence</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
            {language === 'es' ? 'Analítica' : 'Analytics'}
          </h1>
          <p className="mt-2 max-w-3xl" style={{ color: colors.muted }}>
            {language === 'es'
              ? 'Explora tendencias, comparaciones, rankings, distribuciones y métricas adaptadas al dominio de la base activa.'
              : 'Explore trends, comparisons, rankings, distributions and metrics adapted to the active database domain.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border p-1" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
            {rangeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setRange(option.value)}
                className="px-3 py-1.5 rounded-lg text-sm font-bold transition-colors"
                style={{
                  backgroundColor: range === option.value ? theme.primary : 'transparent',
                  color: range === option.value ? '#fff' : colors.muted,
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            onClick={load}
            className="rounded-xl border px-3 py-2 flex items-center gap-2 font-semibold"
            style={{ backgroundColor: colors.card, borderColor: colors.border, color: theme.primary }}
          >
            <RefreshCw size={17} />
            {language === 'es' ? 'Actualizar' : 'Refresh'}
          </button>
        </div>
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
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-sm">
              <div><span style={{ color: colors.muted }}>Entidades</span><strong className="block" style={{ color: colors.text }}>{data.metadata?.entities_detected ?? '—'}</strong></div>
              <div><span style={{ color: colors.muted }}>Relaciones</span><strong className="block" style={{ color: colors.text }}>{data.metadata?.relations_detected ?? '—'}</strong></div>
              <div><span style={{ color: colors.muted }}>Períodos</span><strong className="block" style={{ color: colors.text }}>{data.metadata?.periods_analyzed ?? '—'}</strong></div>
              <div><span style={{ color: colors.muted }}>Rango</span><strong className="block" style={{ color: colors.text }}>{data.metadata?.date_range?.from || '—'} → {data.metadata?.date_range?.to || '—'}</strong></div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-4">
            {[
              { label: 'Período actual', value: trend?.current?.period || '—', detail: roleLabel(trend?.role) },
              { label: 'Actividad actual', value: formatValue(trend?.current?.total), detail: 'registros' },
              { label: 'Cambio mensual', value: trend?.change_pct == null ? '—' : `${trend.change_pct > 0 ? '+' : ''}${trend.change_pct}%`, detail: trend?.change_absolute == null ? 'sin comparación' : `${trend.change_absolute > 0 ? '+' : ''}${formatValue(trend.change_absolute)} registros` },
              { label: 'Promedio mensual', value: formatValue(trend?.average), detail: `${trend?.periods || 0} períodos` },
              { label: 'Mejor período', value: formatValue(trend?.peak?.total), detail: trend?.peak?.period || '—' },
              { label: 'Menor período', value: formatValue(trend?.lowest?.total), detail: trend?.lowest?.period || '—' },
            ].map((card) => (
              <div key={card.label} className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
                <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: colors.muted }}>{card.label}</p>
                <p className="mt-2 text-2xl font-extrabold" style={{ color: colors.text }}>{card.value}</p>
                <p className="mt-1 text-xs capitalize" style={{ color: colors.muted }}>{card.detail}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
            <div className="xl:col-span-2 rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={TrendingUp} title={language === 'es' ? 'Evolución y promedio móvil' : 'Evolution and moving average'} subtitle={`${roleLabel(trend?.role)} · ${range === 0 ? 'histórico completo' : `últimos ${range} meses`}`} theme={theme} colors={colors} />
              <div className="h-[340px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis dataKey="period" tick={{ fill: colors.muted, fontSize: 12 }} />
                    <YAxis tick={{ fill: colors.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Legend />
                    <Line type="monotone" dataKey="total" name={language === 'es' ? 'Actividad' : 'Activity'} stroke={theme.primary} strokeWidth={3} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="rolling_average" name={language === 'es' ? 'Promedio móvil 3M' : '3M moving average'} stroke={theme.primaryStrong} strokeWidth={2} strokeDasharray="7 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={Sparkles} title={language === 'es' ? 'Insights automáticos' : 'Automatic insights'} subtitle={language === 'es' ? 'Hallazgos derivados de los datos actuales.' : 'Findings derived from current data.'} theme={theme} colors={colors} />
              <div className="space-y-3 max-h-[330px] overflow-y-auto pr-1">
                {(data.insights || []).map((insight, index) => (
                  <div key={`${insight.type}-${index}`} className="rounded-xl border p-3" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                    <p className="font-bold text-sm" style={{ color: colors.text }}>{insight.title}</p>
                    <p className="mt-1 text-sm leading-5" style={{ color: colors.muted }}>{insight.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {(data.rankings || []).length > 0 && (
            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={Trophy} title={language === 'es' ? 'Rankings del negocio' : 'Business rankings'} subtitle={language === 'es' ? 'Clasificaciones construidas a partir de relaciones reales del modelo semántico.' : 'Rankings built from real semantic-model relationships.'} theme={theme} colors={colors} />
              <div className={rankingGridClass(data.rankings.length)}>
                {data.rankings.map((ranking) => (
                  <div key={ranking.title} className="rounded-2xl border p-4" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                    <h3 className="font-extrabold" style={{ color: colors.text }}>{ranking.title}</h3>
                    <div className="mt-3 space-y-2">
                      {ranking.data.map((item, index) => (
                        <div key={`${ranking.title}-${item.label}`} className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-extrabold shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>{index + 1}</span>
                            <span className="font-semibold truncate" style={{ color: colors.text }}>{item.label}</span>
                          </div>
                          <span className="font-extrabold shrink-0" style={{ color: theme.primary }}>{formatValue(item.value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(data.numeric_metrics || []).length > 0 && (
            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={Activity} title={language === 'es' ? 'Métricas secundarias' : 'Secondary metrics'} subtitle={language === 'es' ? 'Resumen estadístico de columnas numéricas relevantes detectadas automáticamente.' : 'Statistical summary of relevant numeric columns detected automatically.'} theme={theme} colors={colors} />
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {data.numeric_metrics.slice(0, 6).map((metric) => (
                  <div key={`${metric.table}-${metric.column}`} className="rounded-2xl border p-4" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-extrabold capitalize" style={{ color: colors.text }}>{roleLabel(metric.role)} · {metric.metric}</p>
                        <p className="text-xs" style={{ color: colors.muted }}>{metric.table}.{metric.column}</p>
                      </div>
                      <span className="text-xs font-bold px-2 py-1 rounded-lg" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>{metric.records} datos</span>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div><span style={{ color: colors.muted }}>Total</span><strong className="block text-lg" style={{ color: colors.text }}>{formatValue(metric.total)}</strong></div>
                      <div><span style={{ color: colors.muted }}>Promedio</span><strong className="block text-lg" style={{ color: colors.text }}>{formatValue(metric.average)}</strong></div>
                      <div><span style={{ color: colors.muted }}>Mínimo</span><strong className="block" style={{ color: colors.text }}>{formatValue(metric.minimum)}</strong></div>
                      <div><span style={{ color: colors.muted }}>Máximo</span><strong className="block" style={{ color: colors.text }}>{formatValue(metric.maximum)}</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {(data.distributions || []).slice(0, 4).map((distribution) => (
              <div key={`${distribution.role}-${distribution.column}`} className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
                <SectionTitle icon={Layers3} title={distribution.label} subtitle={roleLabel(distribution.role)} theme={theme} colors={colors} />
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={distribution.data}>
                      <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                      <XAxis dataKey="label" tick={{ fill: colors.muted, fontSize: 11 }} interval={0} angle={distribution.data.length > 5 ? -20 : 0} textAnchor={distribution.data.length > 5 ? 'end' : 'middle'} height={distribution.data.length > 5 ? 55 : 30} />
                      <YAxis tick={{ fill: colors.muted, fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                      <Bar dataKey="total" fill={theme.primary} radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={BarChart3} title={language === 'es' ? 'Volumen por entidad' : 'Volume by entity'} subtitle={language === 'es' ? 'Entidades detectadas y mapeadas por el modelo semántico.' : 'Entities detected and mapped by the semantic model.'} theme={theme} colors={colors} />
              <div className="h-[330px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={entityData} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis type="number" tick={{ fill: colors.muted, fontSize: 12 }} />
                    <YAxis type="category" dataKey="label" width={105} tick={{ fill: colors.muted, fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Bar dataKey="value" fill={theme.primary} radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm overflow-hidden" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <SectionTitle icon={CalendarRange} title={language === 'es' ? 'Detalle histórico' : 'Historical detail'} subtitle={language === 'es' ? 'Valores mensuales usados para el análisis temporal.' : 'Monthly values used for time analysis.'} theme={theme} colors={colors} />
              <div className="overflow-x-auto max-h-[330px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0" style={{ backgroundColor: colors.card }}>
                    <tr className="border-b" style={{ borderColor: colors.border, color: colors.muted }}>
                      <th className="text-left py-2 pr-4">Período</th>
                      <th className="text-right py-2 px-3">Actividad</th>
                      <th className="text-right py-2 px-3">Prom. 3M</th>
                      <th className="text-right py-2 pl-3">Acumulado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trendData.slice().reverse().map((row) => (
                      <tr key={row.period} className="border-b last:border-0" style={{ borderColor: colors.border }}>
                        <td className="py-2.5 pr-4 font-semibold" style={{ color: colors.text }}>{row.period}</td>
                        <td className="py-2.5 px-3 text-right" style={{ color: colors.text }}>{formatValue(row.total)}</td>
                        <td className="py-2.5 px-3 text-right" style={{ color: colors.muted }}>{formatValue(row.rolling_average)}</td>
                        <td className="py-2.5 pl-3 text-right font-semibold" style={{ color: theme.primary }}>{formatValue(row.cumulative)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border p-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.muted }}>
            <span className="font-bold" style={{ color: colors.text }}>Cobertura del análisis:</span>
            <span>{data.metadata?.entities_detected ?? 0} entidades semánticas</span>
            <span>{data.metadata?.relations_detected ?? 0} relaciones</span>
            <span>{data.metadata?.unmapped_tables ?? 0} tablas sin mapear</span>
            <span>{(data.distributions || []).length} distribuciones</span>
            <span>{(data.rankings || []).length} rankings</span>
            <span>{(data.numeric_metrics || []).length} métricas numéricas</span>
          </div>
        </>
      )}
    </section>
  );
};