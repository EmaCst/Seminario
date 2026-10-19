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
const fullMonthLabel = (year, month, language) => (
  new Intl.DateTimeFormat(language === 'es' ? 'es-GT' : 'en-US', {
    year: 'numeric', month: 'long', timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, 1)))
);

const qualityFromEvidence = (confidence, language) => {
  const names = {
    moderate: language === 'es' ? 'Moderada' : 'Moderate',
    limited: language === 'es' ? 'Limitada' : 'Limited',
    insufficient: language === 'es' ? 'Insuficiente' : 'Insufficient',
  };
  return { label: names[confidence] || (language === 'es' ? 'Sin evaluar' : 'Not evaluated') };
};

const severityLabel = (severity, language) => {
  if (language !== 'en') return severity || 'No determinada';
  if (severity === 'alta') return 'High';
  if (severity === 'media') return 'Medium';
  if (severity === 'baja') return 'Low';
  return 'Unknown';
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
    let active = true;
    Promise.all([getForecast(horizon), getAnomalies()])
      .then(([forecastData, anomalyData]) => {
        if (!active) return;
        setForecast(forecastData);
        setAnomalies(anomalyData);
      })
      .catch((err) => { if (active) setError(err.message || 'No fue posible generar el análisis predictivo.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [horizon]);

  const chartData = useMemo(() => {
    if (!forecast) return [];
    const history = forecast.training_points || [];
    const historical = history.map((point, index) => ({
      label: monthLabel(point.year, point.month),
      historical: point.total,
      // Connect the projected curve to the observed last value.
      prediction: index === history.length - 1 ? point.total : null,
    }));
    const projected = (forecast.forecast || []).map((point) => ({
      label: monthLabel(point.year, point.month),
      historical: null,
      prediction: point.predicted_total,
      priorYear: point.prior_year_total,
    }));
    return [...historical, ...projected];
  }, [forecast]);

  const quality = qualityFromEvidence(forecast?.confidence, language);
  const anomalyCount = anomalies?.anomalies?.length || 0;
  const validation = forecast?.validation;
  const forecastBasis = forecast?.forecast_basis;
  const containsPastPeriods = forecast?.forecast?.some((point) => point.period_status !== 'future');
  const modelName = ({
    seasonal_trend: 'Tendencia + estacionalidad',
    seasonal_drift: 'Patrón anual + evolución histórica',
    seasonal_naive: 'Referencia sin ajuste: mismo mes del año anterior',
    linear_regression: 'Regresión lineal',
    naive_last: 'Referencia sin ajuste: último mes',
  })[forecast?.model] || forecast?.model || '—';

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
              {language === 'es' ? 'Motor' : 'Engine'}: <strong style={{ color: colors.text }}>{modelName} · Anomalías por desviación contextual</strong>
            </div>
          </div>

          {forecastBasis && (
            <div className="rounded-2xl border p-4 text-sm space-y-1"
              style={{
                borderColor: containsPastPeriods ? '#F59E0B88' : colors.border,
                backgroundColor: containsPastPeriods ? '#F59E0B10' : colors.card,
                color: colors.text,
              }}
            >
              <p className="font-bold">
                {language === 'es' ? 'Último período con datos reales' : 'Last period with actual data'}:{' '}
                {monthLabel(forecastBasis.last_observed.year, forecastBasis.last_observed.month)}
              </p>
              <p>
                {language === 'es' ? 'Período estimado' : 'Estimated range'}:{' '}
                {monthLabel(forecastBasis.first_projected.year, forecastBasis.first_projected.month)}
                {' → '}
                {monthLabel(forecastBasis.last_projected.year, forecastBasis.last_projected.month)}
              </p>
              {containsPastPeriods && (
                <p className="font-semibold">
                  {language === 'es'
                    ? 'Atención: algunos períodos estimados ya transcurrieron o corresponden al mes actual. La proyección empieza después del último dato registrado, no después de hoy.'
                    : 'Warning: some estimated periods have elapsed or belong to the current month. Estimates begin after the last recorded month, not after today.'}
                </p>
              )}
              {forecastBasis.model_origin === 'baseline_reference' && (
                <p>
                  {language === 'es'
                    ? 'Se seleccionó una referencia sencilla: los valores no representan un modelo temporal complejo.'
                    : 'A simple baseline was selected; these values are not a complex temporal model.'}
                </p>
              )}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              { icon: CalendarRange, label: language === 'es' ? 'Meses de entrenamiento' : 'Training months', value: forecast.training_months },
              { icon: TrendingUp, label: language === 'es' ? 'Mejora vs. ingenuo' : 'Skill vs. naive', value: forecast.validation?.skill_vs_naive_pct == null ? '—' : `${forecast.validation.skill_vs_naive_pct}%` },
              { icon: BrainCircuit, label: language === 'es' ? 'Calidad predictiva' : 'Forecast quality', value: quality.label },
              { icon: AlertTriangle, label: language === 'es' ? 'Anomalías detectadas' : 'Detected anomalies', value: anomalyCount },
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
                <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>{language === 'es' ? 'Historial y estimaciones posteriores al último registro' : 'History and estimates after the last observation'}</h2>
                <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? `Estimación de ${horizon} meses desde el último registro disponible.` : `Estimates for ${horizon} months after the latest recorded period.`}</p>
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
                    <Line type="monotone" dataKey="prediction" name={language === 'es' ? 'Valor estimado' : 'Estimated value'} stroke={theme.primaryStrong} strokeWidth={3} strokeDasharray="7 5" connectNulls={false} />
                    <Line type="monotone" dataKey="priorYear" name={language === 'es' ? 'Mismo mes del año anterior' : 'Same month last year'} stroke="#D97706" strokeWidth={2} strokeDasharray="3 6" connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg mb-4" style={{ color: colors.text }}>{language === 'es' ? 'Valores estimados y referencia anual' : 'Estimates and annual benchmark'}</h2>
              {(forecast.forecast || []).length > 3 && (
                <p className="text-xs mb-3" style={{ color: colors.muted }}>
                  {language === 'es'
                    ? 'Desplázate dentro de este panel para consultar todos los períodos sin alargar la página.'
                    : 'Scroll within this panel to see every period without extending the page.'}
                </p>
              )}
              <div
                role="region"
                aria-label={language === 'es' ? 'Lista desplazable de valores estimados y referencias anuales' : 'Scrollable list of estimated values and annual references'}
                tabIndex={0}
                className="max-h-[340px] min-h-0 min-w-0 space-y-3 overflow-y-auto overscroll-contain pr-2 focus-visible:outline-2 focus-visible:outline-offset-2"
                style={{ scrollbarWidth: 'thin', scrollbarColor: `${colors.border} transparent` }}
              >
                {(forecast.forecast || []).map((item) => (
                  <div key={`${item.year}-${item.month}`} className="min-w-0 rounded-xl border p-3 flex items-start justify-between gap-2" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <span className="shrink-0 pt-1 text-sm font-semibold" style={{ color: colors.muted }}>{monthLabel(item.year, item.month)}</span>
                    <div className="min-w-0 flex-1 break-words text-right">
                      <span className="font-extrabold text-lg block" style={{ color: theme.primary }}>{item.predicted_total}</span>
                      <span className="text-xs block" style={{ color: colors.muted }}>
                        {item.period_status === 'historical_gap'
                          ? (language === 'es' ? 'Período ya transcurrido' : 'Already elapsed')
                          : item.period_status === 'current_month'
                            ? (language === 'es' ? 'Mes actual' : 'Current month')
                            : (language === 'es' ? 'Período futuro' : 'Future period')}
                      </span>
                      {item.prior_year_total != null && (
                        <span className="text-xs block" style={{ color: colors.muted }}>
                          {language === 'es' ? 'Mismo mes del año anterior' : 'Same month last year'}: {item.prior_year_total}
                          {' · Δ '}{item.change_vs_prior_year > 0 ? '+' : ''}{item.change_vs_prior_year}
                        </span>
                      )}
                      {item.lower_estimate != null && (
                        <span className="text-xs block" style={{ color: colors.muted }}>
                          P80 histórico: {item.lower_estimate}–{item.upper_estimate}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="rounded-2xl border p-5 shadow-sm flex flex-col" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg" style={{ color: colors.text }}>
                {language === 'es' ? 'Calidad del modelo' : 'Model quality'}
              </h2>

              <div className="flex-1 flex flex-col items-center justify-center text-center py-5">
                <p className="text-xs font-bold uppercase tracking-[0.14em]" style={{ color: colors.muted }}>
                  {language === 'es' ? 'Confiabilidad evaluada' : 'Validated reliability'}
                </p>
                <p className="mt-1 text-2xl font-extrabold" style={{ color: theme.primary }}>
                  {quality.label}
                </p>
                <p className="mt-3 text-lg font-extrabold" style={{ color: colors.text }}>
                  R² de validación = {forecast.r2_score ?? (language === 'es' ? 'N/D' : 'N/A')}
                </p>

                <p className="mt-3 max-w-md text-sm leading-6" style={{ color: colors.muted }}>
                  {validation?.months
                    ? `Backtesting con ${validation.months} orígenes y ${validation.samples} predicciones históricas (hasta ${validation.horizon} meses de horizonte). MAE: ${validation.selected?.mae ?? '—'} · RMSE: ${validation.selected?.rmse ?? '—'} · WAPE: ${validation.selected?.wape ?? '—'}%. Referencia anual MAE: ${validation.seasonal_baseline?.mae ?? 'no evaluada'}.`
                    : 'Historial insuficiente para medir la precisión fuera del entrenamiento.'}
                </p>
                {forecast.seasonal_patterns?.length > 0 && (
                  <div className="mt-3 text-left w-full max-w-md rounded-xl border p-3" style={{ borderColor: colors.border }}>
                    <p className="font-bold text-sm mb-2" style={{ color: colors.text }}>Patrones estacionales observados</p>
                    <div className="flex flex-wrap gap-2">
                      {forecast.seasonal_patterns.map((pattern) => (
                        <span key={pattern.month} className="rounded-lg px-2 py-1 text-xs" style={{ backgroundColor: colors.cardSoft, color: colors.text }}>
                          {monthLabel(2026, pattern.month).slice(0, 2)}: {pattern.direction === 'increase' ? '↑' : '↓'} {Math.abs(pattern.estimated_effect)} ({pattern.observations} años)
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div
                  className="mt-4 w-full max-w-md rounded-xl border px-4 py-3"
                  style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}
                >
                  <p className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: colors.muted }}>
                    {language === 'es' ? 'Fórmula de R²' : 'R² formula'}
                  </p>
                  <div className="text-sm sm:text-base font-semibold overflow-x-auto whitespace-nowrap" style={{ color: colors.text }}>
                    R² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(yᵢ − ȳ)²
                  </div>
                  <p className="mt-2 text-xs leading-5" style={{ color: colors.muted }}>
                    {language === 'es'
                      ? 'yᵢ = valor real · ŷᵢ = valor predicho · ȳ = promedio de los valores reales'
                      : 'yᵢ = actual value · ŷᵢ = predicted value · ȳ = average of actual values'}
                  </p>
                </div>

                <p className="mt-3 max-w-md text-xs leading-5" style={{ color: colors.muted }}>
                  {language === 'es'
                    ? 'Cuanto más cercano a 1 sea R², mejor explica el modelo la variación histórica observada.'
                    : 'The closer R² is to 1, the better the model explains the historical variation observed.'}
                </p>
              </div>

              <div className="rounded-xl p-3 text-sm" style={{ backgroundColor: colors.accentSoft, color: colors.text }}>
                {forecast.warning}
              </div>
            </div>

            <div className="self-start min-w-0 rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
              <h2 className="font-extrabold text-lg mb-3" style={{ color: colors.text }}>{language === 'es' ? 'Comportamientos atípicos' : 'Anomalous behavior'}</h2>

              {anomalies?.baseline && (
                <div className="grid grid-cols-3 gap-2 mb-4">
                  <div className="rounded-xl border p-2.5" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <p className="text-[11px] uppercase font-bold" style={{ color: colors.muted }}>{language === 'es' ? 'Promedio' : 'Average'}</p>
                    <p className="font-extrabold" style={{ color: colors.text }}>{anomalies.baseline.average}</p>
                  </div>
                  <div className="rounded-xl border p-2.5" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <p className="text-[11px] uppercase font-bold" style={{ color: colors.muted }}>{language === 'es' ? 'Mediana' : 'Median'}</p>
                    <p className="font-extrabold" style={{ color: colors.text }}>{anomalies.baseline.median}</p>
                  </div>
                  <div className="rounded-xl border p-2.5" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                    <p className="text-[11px] uppercase font-bold" style={{ color: colors.muted }}>{language === 'es' ? 'Desv. est.' : 'Std. dev.'}</p>
                    <p className="font-extrabold" style={{ color: colors.text }}>{anomalies.baseline.std_dev}</p>
                  </div>
                </div>
              )}

              {anomalyCount === 0 ? (
                <div className="space-y-4">
                  <div className="rounded-xl border p-4" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                    <p className="text-sm font-extrabold" style={{ color: colors.text }}>
                      {language === 'es' ? 'No se encontraron anomalías bajo los criterios actuales' : 'No anomalies under the current criteria'}
                    </p>
                    <p className="mt-2 text-sm leading-6" style={{ color: colors.muted }}>
                      {language === 'es'
                        ? `Kenneth revisó ${anomalies?.months_evaluated ?? '—'} períodos mensuales de esta serie. Que no haya alertas no significa que los valores sean idénticos ni que no existan cambios que valga la pena revisar.`
                        : `Kenneth reviewed ${anomalies?.months_evaluated ?? '—'} monthly periods in this series. No alerts does not mean the values never changed or that further review is unnecessary.`}
                    </p>
                    {anomalies?.screening && (
                      <p className="mt-2 text-xs leading-5" style={{ color: colors.muted }}>
                        {language === 'es'
                          ? `Criterio actual: desviación superior a ${anomalies.screening.absolute_threshold} unidades y al 20% respecto al valor esperado, ajustado al historial${anomalies.screening.seasonality_adjusted ? ' y al mes del año' : ''}.`
                          : `Current rule: a deviation greater than ${anomalies.screening.absolute_threshold} units and 20% relative to expected values, adjusted to historical behavior${anomalies.screening.seasonality_adjusted ? ' and calendar seasonality' : ''}.`}
                      </p>
                    )}
                  </div>
                  {(anomalies?.review_points || []).length > 0 && (
                    <div className="space-y-2">
                      <h3 className="font-bold text-sm" style={{ color: colors.text }}>
                        {language === 'es' ? 'Variaciones que sí se observaron' : 'Noteworthy observed variations'}
                      </h3>
                      <p className="text-xs leading-5" style={{ color: colors.muted }}>
                        {language === 'es'
                          ? 'Estos períodos son los que más se alejaron de su valor esperado, pero no alcanzaron el umbral de anomalía. No son alertas.'
                          : 'These periods diverged most from their expected values without meeting the anomaly threshold. They are not alerts.'}
                      </p>
                      <div className="max-h-[420px] space-y-2 overflow-y-auto overscroll-contain pr-1" role="region"
                        aria-label={language === 'es' ? 'Variaciones históricas para revisar' : 'Historical variations to review'} tabIndex={0}>
                        {(anomalies.review_points || []).map((point) => (
                          <div key={`${point.year}-${point.month}`} className="rounded-xl border p-3.5 space-y-2"
                            style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <time className="font-bold capitalize text-sm" dateTime={`${point.year}-${String(point.month).padStart(2, '0')}`}
                                style={{ color: colors.text }}>{fullMonthLabel(point.year, point.month, language)}</time>
                              <span className="text-xs font-semibold" style={{ color: colors.muted }}>
                                {language === 'es' ? 'Variación habitual / no confirmada como anomalía' : 'Variation / not a confirmed anomaly'}
                              </span>
                            </div>
                            <p className="text-sm leading-6" style={{ color: colors.text }}>
                              {point.explanation || (language === 'es'
                                ? `Valor registrado: ${point.total}; esperado: ${point.expected_total}.`
                                : `Recorded: ${point.total}; expected: ${point.expected_total}.`)}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!anomalies?.warning && (
                    <p className="text-xs leading-5" style={{ color: colors.muted }}>{anomalies.warning}</p>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {anomalies.anomalies.map((item) => (
                    <div key={`${item.year}-${item.month}`} className="rounded-xl border p-4" style={{ borderColor: '#F59E0B55', backgroundColor: '#F59E0B10' }}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0 space-y-2">
                          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.muted }}>
                            {language === 'es' ? 'Fecha de la anomalía' : 'Anomaly period'}
                          </p>
                          <time
                            dateTime={`${item.year}-${String(item.month).padStart(2, '0')}`}
                            className="block text-base font-extrabold capitalize"
                            style={{ color: colors.text }}
                          >
                            {fullMonthLabel(item.year, item.month, language)}
                          </time>
                          <p className="text-xs" style={{ color: colors.muted }}>
                            {language === 'es' ? 'Análisis mensual (no identifica un día específico)' : 'Monthly analysis (no specific day identified)'}
                          </p>
                          <span className="inline-block rounded-full px-2 py-1 text-xs font-bold uppercase" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                            {language === 'es' ? 'Severidad' : 'Severity'}: {severityLabel(item.severity, language)}
                          </span>
                        </div>
                        <strong className="text-xl" style={{ color: '#D97706' }}>{item.total}</strong>
                      </div>

                      <div className="mt-4 space-y-3 rounded-xl border p-3.5" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
                        <div>
                          <h3 className="text-sm font-bold" style={{ color: colors.text }}>
                            {language === 'es' ? '¿Qué ocurrió?' : 'What happened?'}
                          </h3>
                          <p className="mt-1.5 text-sm leading-6 break-words" style={{ color: colors.text }}>
                            {item.explanation || item.reason || (language === 'es'
                              ? 'El valor se alejó del comportamiento histórico esperado.'
                              : 'The observed value differed from its expected historical behavior.')}
                          </p>
                        </div>
                        <div>
                          <h3 className="text-sm font-bold" style={{ color: colors.text }}>
                            {language === 'es' ? '¿Qué indican los datos?' : 'What does the data indicate?'}
                          </h3>
                          <p className="mt-1.5 text-sm leading-6 break-words" style={{ color: colors.text }}>
                            {item.diagnostic_explanation || (language === 'es'
                              ? 'No se identificó una causa verificable con los datos disponibles.'
                              : 'The available data do not establish a verified cause.')}
                          </p>
                        </div>
                        <div>
                          <h3 className="text-sm font-bold" style={{ color: colors.text }}>
                            {language === 'es' ? '¿Qué conviene revisar?' : 'What should be investigated?'}
                          </h3>
                          <p className="mt-1.5 text-sm leading-6 break-words" style={{ color: colors.muted }}>
                            {item.recommendation || (language === 'es'
                              ? 'Revisa los registros del período antes de atribuir una causa.'
                              : 'Review the period records before attributing a cause.')}
                          </p>
                        </div>
                      </div>
                      <p className="text-xs mt-2" style={{ color: colors.muted }}>
                        {language === 'es' ? 'Esperado según historial' : 'Historically expected'}: {item.expected_total ?? '—'}
                      </p>
                      {(anomalies.diagnostics?.investigations || [])
                        .filter((finding) => finding.year === item.year && finding.month === item.month)
                        .map((finding) => (
                          <div key={`${finding.year}-${finding.month}-diagnostic`} className="mt-3 rounded-xl border p-3" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
                            <strong className="text-sm" style={{ color: colors.text }}>{language === 'es' ? 'Investigación de segmentos' : 'Segment investigation'}</strong>
                            <p className="text-xs mt-1" style={{ color: colors.muted }}>
                              {finding.reference_period
                                ? `${language === 'es' ? 'Comparado con' : 'Compared with'} ${monthLabel(finding.reference_period.year, finding.reference_period.month)}`
                                : (language === 'es' ? 'Sin período comparable' : 'No comparable period')}
                            </p>
                            {finding.contributors.map((segment) => (
                              <p key={`${segment.dimension}-${segment.category}`} className="text-xs mt-1" style={{ color: colors.text }}>
                                {segment.dimension}: {segment.category} · {language === 'es' ? 'Variación' : 'Change'} {segment.change > 0 ? '+' : ''}{segment.change}
                              </p>
                            ))}
                            {(finding.related_indicators || []).length > 0 && (
                              <p className="text-xs font-bold mt-3" style={{ color: colors.text }}>
                                {language === 'es' ? 'Indicadores con cambios simultáneos' : 'Indicators with concurrent changes'}
                              </p>
                            )}
                            {(finding.related_indicators || []).map((related) => (
                              <p key={related.role} className="text-xs mt-1" style={{ color: colors.text }}>
                                {related.role} · {language === 'es' ? 'Variación' : 'Change'} {related.change > 0 ? '+' : ''}{related.change}
                                {related.change_pct == null ? '' : ` (${related.change_pct}%)`}
                              </p>
                            ))}
                            {finding.limitations.map((notice) => (
                              <p key={notice} className="text-xs mt-1" style={{ color: colors.muted }}>{notice}</p>
                            ))}
                            <p className="text-xs mt-2" style={{ color: colors.muted }}>
                              {language === 'es' ? 'Asociaciones descriptivas; no se ha demostrado causalidad.' : 'Descriptive associations; causality is not established.'}
                            </p>
                          </div>
                        ))}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-xs">
                        <div className="rounded-lg p-2" style={{ backgroundColor: colors.card }}>
                          <span style={{ color: colors.muted }}>vs promedio</span>
                          <strong className="block mt-1" style={{ color: colors.text }}>{item.pct_vs_average == null ? '—' : `${item.pct_vs_average > 0 ? '+' : ''}${item.pct_vs_average}%`}</strong>
                        </div>
                        <div className="rounded-lg p-2" style={{ backgroundColor: colors.card }}>
                          <span style={{ color: colors.muted }}>vs anterior</span>
                          <strong className="block mt-1" style={{ color: colors.text }}>{item.pct_vs_previous == null ? '—' : `${item.pct_vs_previous > 0 ? '+' : ''}${item.pct_vs_previous}%`}</strong>
                        </div>
                        <div className="rounded-lg p-2" style={{ backgroundColor: colors.card }}>
                          <span style={{ color: colors.muted }}>z-score</span>
                          <strong className="block mt-1" style={{ color: colors.text }}>{item.z_score ?? '—'}</strong>
                        </div>
                        <div className="rounded-lg p-2" style={{ backgroundColor: colors.card }}>
                          <span style={{ color: colors.muted }}>Desv. / umbral</span>
                          <strong className="block mt-1" style={{ color: colors.text }}>{item.anomaly_score}</strong>
                        </div>
                      </div>
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
