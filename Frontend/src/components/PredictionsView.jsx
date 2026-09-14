import { useContext, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  CalendarRange,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import {
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
import { getAnomalies, getForecast } from '../services/api';

const monthLabel = (year, month) => `${String(month).padStart(2, '0')}/${year}`;

const qualityFromR2 = (score) => {
  if (score == null) return { label: 'Sin evaluar', level: 'unknown' };
  if (score >= 0.75) return { label: 'Alta', level: 'high' };
  if (score >= 0.5) return { label: 'Media', level: 'medium' };
  if (score >= 0.25) return { label: 'Baja', level: 'low' };
  return { label: 'Muy baja', level: 'very-low' };
};

export const PredictionsView = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [horizon, setHorizon] = useState(3);
  const [forecast, setForecast] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [forecastData, anomalyData] = await Promise.all([
        getForecast(horizon),
        getAnomalies(),
      ]);
      setForecast(forecastData);
      setAnomalies(anomalyData);
    } catch (err) {
      setError(err.message || 'No fue posible generar el análisis predictivo.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [horizon]);

  const chartData = useMemo(() => {
    if (!forecast) return [];
    const historical = (forecast.training_points || []).map((point) => ({
      label: monthLabel(point.year, point.month),
      historical: point.total,
      prediction: null,
    }));
    const projected = (forecast.forecast || []).map((point) => ({
      label: monthLabel(point.year, point.month),
      historical: null,
      prediction: point.predicted_total,
    }));
    return [...historical, ...projected];
  }, [forecast]);

  const quality = qualityFromR2(forecast?.r2_score);
  const anomalyCount = anomalies?.anomalies?.length || 0;

  if (loading) {
    return (
      <section className="min-h-72 flex items-center justify-center">
        <div className="flex items-center gap-3" style={{ color: colors.muted }}>
          <RefreshCw className="animate-spin" size={20} />
          {language === 'es' ? 'Entrenando modelos y analizando datos...' : 'Training models and analyzing data...'}
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1" style={{ color: theme.primary }}>
            <BrainCircuit size={22} />
            <span className="text-sm font-bold uppercase tracking-wide">Machine Learning</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
            {language === 'es' ? 'Predicciones' : 'Predictions'}
          </h1>
          <p className="mt-2" style={{ color: colors.muted }}>
            {language === 'es'
              ? 'Pronósticos, calidad del modelo y detección automática de comportamientos atípicos.'
              : 'Forecasts, model quality and automatic anomaly detection.'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: colors.muted }}>
            {language === 'es' ? 'Horizonte' : 'Horizon'}
          </span>
          <select
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
            className="rounded-xl border px-3 py-2 font-semibold outline-none"
            style={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }}
          >
            {[1, 3, 6, 12].map((value) => (
              <option key={value} value={value}>{value} {language === 'es' ? 'meses' : 'months'}</option>
            ))}
          </select>
          <button
            onClick={load}
            className="rounded-xl border p-2.5 transition-transform hover:scale-105"
            style={{ backgroundColor: colors.card, borderColor: colors.border, color: theme.primary }}
            title={language === 'es' ? 'Actualizar' : 'Refresh'}
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border p-4" style={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2', color: '#B91C1C' }}>
          {error}
        </div>
      )}

      {!error && forecast && (
        <>
          <div
            className="rounded-2xl border p-5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 shadow-sm"
            style={{ backgroundColor: colors.card, borderColor: colors.border }}
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                <Sparkles size={24} />
              </div>
              <div>
                <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Serie analizada' : 'Analyzed series'}</p>
                <p className="text-xl font-extrabold capitalize" style={{ color: colors.text }}>{forecast.role}</p>
                <p className="text-sm" style={{ color: colors.muted }}>{forecast.table} · {forecast.date_column}</p>
              </div>
            </div>
            <div className="text-sm" style={{ color: colors.muted }}>
              {language === 'es' ? 'Motor' : 'Engine'}: <strong style={{ color: colors.text }}>Linear Regression + Isolation Forest</strong>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              {
                icon: CalendarRange,
                label: language === 'es' ? 'Meses de entrenamiento' : 'Training months',
                value: forecast.training_months,
              },
              {
                icon: TrendingUp,
                label: 'R²',
                value: forecast.r2_score ?? '—',
              },
              {
                icon: BrainCircuit,
                label: language === 'es' ? 'Confianza' : 'Confidence',
                value: quality.label,
              },
              {
                icon: AlertTriangle,
                label: language === 'es' ? 'Anomalías detectadas' : 'Detected anomalies',
                value: anomalyCount,
              },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="rounded-2xl border p-4 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
                <div className="flex items-center gap-2 mb-2" style={{ color: theme.primary }}>
                  <Icon size={18} />
                  <span className="text-xs font-bold uppercase tracking-wide">{label}</span>
                </div>
                <p className="text-2xl font-extrabold" style={{ color: colors.text }}>{value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
            <div className="xl:col-span-2 rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <div className="mb-4">
                <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>
                  {language === 'es' ? 'Histórico + proyección' : 'History + forecast'}
                </h2>
                <p className="text-sm" style={{ color: colors.muted }}>
                  {language === 'es' ? `Pronóstico para los próximos ${horizon} meses.` : `Forecast for the next ${horizon} months.`}
                </p>
              </div>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.25} />
                    <XAxis dataKey="label" tick={{ fill: colors.muted, fontSize: 12 }} />
                    <YAxis tick={{ fill: colors.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }} />
                    <Legend />
                    <Line type="monotone" dataKey="historical" name={language === 'es' ? 'Histórico' : 'Historical'} stroke={theme.primary} strokeWidth={3} connectNulls={false} />
                    <Line type="monotone" dataKey="prediction" name={language === 'es' ? 'Predicción' : 'Prediction'} stroke={theme.primaryStrong} strokeWidth={3} strokeDasharray="7 5" connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg mb-4" style={{ color: colors.text }}>
                {language === 'es' ? 'Próximos valores' : 'Next values'}
              </h2>
              <div className="space-y-3">
                {(forecast.forecast || []).map((item) => (
                  <div key={`${item.year}-${item.month}`} className="rounded-xl border p-3 flex items-center justify-between" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <span className="font-semibold" style={{ color: colors.muted }}>{monthLabel(item.year, item.month)}</span>
                    <span className="font-extrabold text-lg" style={{ color: theme.primary }}>{item.predicted_total}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg mb-3" style={{ color: colors.text }}>
                {language === 'es' ? 'Calidad del modelo' : 'Model quality'}
              </h2>
              <p className="text-sm leading-6" style={{ color: colors.muted }}>
                {language === 'es'
                  ? `El modelo obtuvo un R² de ${forecast.r2_score ?? 'N/D'}, clasificado como confianza ${quality.label.toLowerCase()}. Cuanto mayor sea el R², mejor explica la tendencia histórica observada.`
                  : `The model obtained an R² of ${forecast.r2_score ?? 'N/A'}, classified as ${quality.label.toLowerCase()} confidence.`}
              </p>
              <div className="mt-4 rounded-xl p-3 text-sm" style={{ backgroundColor: colors.accentSoft, color: colors.text }}>
                {forecast.warning}
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg mb-3" style={{ color: colors.text }}>
                {language === 'es' ? 'Comportamientos atípicos' : 'Anomalous behavior'}
              </h2>
              {anomalyCount === 0 ? (
                <p className="text-sm" style={{ color: colors.muted }}>
                  {language === 'es' ? 'No se detectaron meses atípicos con el modelo actual.' : 'No anomalous months were detected.'}
                </p>
              ) : (
                <div className="space-y-3">
                  {anomalies.anomalies.map((item) => (
                    <div key={`${item.year}-${item.month}`} className="rounded-xl border p-3" style={{ borderColor: '#F59E0B55', backgroundColor: '#F59E0B10' }}>
                      <div className="flex justify-between gap-3">
                        <strong style={{ color: colors.text }}>{monthLabel(item.year, item.month)}</strong>
                        <strong style={{ color: '#D97706' }}>{item.total}</strong>
                      </div>
                      <p className="text-xs mt-1" style={{ color: colors.muted }}>
                        score: {item.anomaly_score}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
};
