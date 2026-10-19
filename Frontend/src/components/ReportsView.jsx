import { useContext, useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, CalendarRange, CheckCircle2, Database,
  Download, Eye, FileText, LoaderCircle, SlidersHorizontal,
} from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import {
  downloadConfiguredReport, getReportOptions, previewConfiguredReport,
} from '../services/api';

const TYPES = [
  { key: 'executive', es: 'Ejecutivo', en: 'Executive', descEs: 'Visión rápida con indicadores y conclusiones.', descEn: 'Overview with KPIs and insights.' },
  { key: 'analytics', es: 'Analítico', en: 'Analytics', descEs: 'Tendencias y detalle de actividad.', descEn: 'Trends and activity details.' },
  { key: 'predictive', es: 'Predictivo', en: 'Predictive', descEs: 'Proyecciones y comportamiento atípico.', descEn: 'Forecasts and anomalous behavior.' },
  { key: 'complete', es: 'Completo', en: 'Complete', descEs: 'Todos los apartados fundamentales.', descEn: 'All essential sections.' },
  { key: 'custom', es: 'Personalizado', en: 'Custom', descEs: 'Elige exactamente lo que necesitas.', descEn: 'Choose exactly what you need.' },
];
const SECTIONS = [
  { key: 'executive', es: 'Resumen ejecutivo', en: 'Executive summary' },
  { key: 'analytics', es: 'Tendencias y analítica', en: 'Trends and analytics' },
  { key: 'predictive', es: 'Pronósticos y anomalías', en: 'Forecasts and anomalies' },
  { key: 'visualizations', es: 'Visualizaciones guardadas', en: 'Saved visualizations' },
  { key: 'methodology', es: 'Metodología y limitaciones', en: 'Methodology and limitations' },
];
const DEFAULT_SECTIONS = {
  executive: ['executive', 'methodology'],
  analytics: ['analytics', 'methodology'],
  predictive: ['predictive', 'methodology'],
  complete: ['executive', 'analytics', 'predictive', 'methodology'],
  custom: ['executive', 'analytics', 'methodology'],
};
const locale = (language) => language === 'es';
const displayNumber = (value) => value == null ? '—' : Number(value).toLocaleString('es-GT', { maximumFractionDigits: 2 });

export const ReportsView = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const es = locale(language);
  const [options, setOptions] = useState(null);
  const [reportType, setReportType] = useState('complete');
  const [title, setTitle] = useState('Informe empresarial');
  const [startMonth, setStartMonth] = useState('');
  const [endMonth, setEndMonth] = useState('');
  const [sections, setSections] = useState(DEFAULT_SECTIONS.complete);
  const [visualizationIds, setVisualizationIds] = useState([]);
  const [horizon, setHorizon] = useState(3);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [lastFile, setLastFile] = useState('');

  useEffect(() => {
    let active = true;
    getReportOptions()
      .then((response) => { if (active) setOptions(response); })
      .catch((err) => { if (active) setError(err.message || 'No fue posible cargar las opciones de reporte.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const invalidate = () => { setPreview(null); setError(''); };
  const changeType = (type) => {
    setReportType(type);
    setSections(DEFAULT_SECTIONS[type]);
    if (type !== 'custom') setVisualizationIds([]);
    invalidate();
  };
  const toggleSection = (key) => {
    setSections((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key]);
    if (key === 'visualizations' && sections.includes('visualizations')) setVisualizationIds([]);
    invalidate();
  };
  const toggleVisualization = (id) => {
    setVisualizationIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : [...current, id]);
    invalidate();
  };

  const isRangeInvalid = Boolean(startMonth !== endMonth && (!startMonth || !endMonth)) ||
    Boolean(startMonth && endMonth && startMonth > endMonth);
  const isConfigurationValid = Boolean(options?.source && title.trim().length >= 3 &&
    title.trim().length <= 120 && sections.length > 0 && !isRangeInvalid);
  const payload = () => ({
    report_type: reportType,
    title: title.trim(),
    start_month: startMonth || null,
    end_month: endMonth || null,
    sections: sections,
    visualization_ids: visualizationIds,
    horizon: Number(horizon),
    source_key: options?.source?.key,
  });

  const showPreview = async () => {
    setBusy('preview');
    setError('');
    try {
      const response = await previewConfiguredReport(payload());
      setPreview(response);
    } catch (err) {
      setPreview(null);
      setError(err.message || 'No fue posible previsualizar el informe.');
    } finally {
      setBusy('');
    }
  };

  const download = async () => {
    setBusy('download');
    setError('');
    setLastFile('');
    try {
      const { blob, filename } = await downloadConfiguredReport(payload());
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setLastFile(filename);
    } catch (err) {
      setError(err.message || 'No fue posible generar el documento.');
    } finally {
      setBusy('');
    }
  };

  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border };
  const controlStyle = { backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text };

  return (
    <section className="space-y-5 pb-10">
      <header>
        <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider" style={{ color: theme.primary }}>
          <FileText size={20} /> Kenneth Reports
        </div>
        <h1 className="mt-1 text-3xl font-extrabold" style={{ color: theme.primary }}>
          {es ? 'Crea un informe profesional' : 'Create a professional report'}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: colors.muted }}>
          {es
            ? 'Personaliza las secciones, el período y las gráficas que aparecerán en el PDF. Kenneth utiliza exclusivamente los datos disponibles en la fuente activa.'
            : 'Choose sections, dates and saved charts to include in the PDF. Kenneth uses verified information from the active source.'}
        </p>
      </header>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-xl border p-3 text-sm"
          style={{ borderColor: '#FDA4AF', backgroundColor: '#FFF1F2', color: '#9F1239' }}>
          <AlertTriangle size={18} className="shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-3 rounded-2xl border p-6" style={cardStyle}>
          <LoaderCircle size={19} className="animate-spin" />
          {es ? 'Consultando las opciones de la fuente activa…' : 'Loading active source options…'}
        </div>
      ) : options ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(330px,0.9fr)]">
          <div className="space-y-5">
            <div className="rounded-2xl border p-5" style={cardStyle}>
              <div className="flex items-center gap-3">
                <Database size={21} style={{ color: theme.primary }} />
                <div>
                  <p className="text-xs font-bold uppercase" style={{ color: colors.muted }}>
                    {es ? 'Fuente de datos activa' : 'Active data source'}
                  </p>
                  <p className="font-bold" style={{ color: colors.text }}>{options.source.database}</p>
                  <p className="text-xs" style={{ color: colors.muted }}>{options.source.provider}</p>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5" style={{ color: colors.muted }}>
                {es
                  ? 'Si cambias de base de datos, actualiza esta pantalla antes de generar el reporte. No se mezclarán datos de distintas fuentes.'
                  : 'Refresh this page when switching databases. Sources will not be mixed.'}
              </p>
            </div>

            <div className="rounded-2xl border p-5" style={cardStyle}>
              <h2 className="mb-3 flex items-center gap-2 font-extrabold" style={{ color: colors.text }}>
                <SlidersHorizontal size={18} /> {es ? 'Tipo de reporte' : 'Report type'}
              </h2>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {TYPES.map((type) => (
                  <button type="button" key={type.key} onClick={() => changeType(type.key)}
                    aria-pressed={reportType === type.key}
                    className="rounded-xl border p-3 text-left transition hover:opacity-90"
                    style={{
                      backgroundColor: reportType === type.key ? colors.accentSoft : colors.cardSoft,
                      borderColor: reportType === type.key ? theme.primary : colors.border,
                      color: colors.text,
                    }}>
                    <span className="block text-sm font-extrabold">{es ? type.es : type.en}</span>
                    <span className="mt-1 block text-xs leading-5" style={{ color: colors.muted }}>{es ? type.descEs : type.descEn}</span>
                  </button>
                ))}
              </div>
              <label htmlFor="report-title" className="mt-5 mb-2 block text-sm font-bold" style={{ color: colors.text }}>
                {es ? 'Título del documento' : 'Document title'}
              </label>
              <input id="report-title" type="text" maxLength={120} value={title}
                onChange={(e) => { setTitle(e.target.value); invalidate(); }}
                className="w-full rounded-xl border px-3 py-2.5 text-sm outline-none focus:ring-2"
                style={controlStyle} />
            </div>

            <div className="rounded-2xl border p-5" style={cardStyle}>
              <h2 className="mb-3 flex items-center gap-2 font-extrabold" style={{ color: colors.text }}>
                <CalendarRange size={18} /> {es ? 'Período descriptivo' : 'Descriptive date range'}
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold" style={{ color: colors.muted }}>
                  {es ? 'Desde' : 'From'}
                  <input type="month" value={startMonth}
                    onChange={(e) => { setStartMonth(e.target.value); invalidate(); }}
                    className="mt-1 block w-full rounded-lg border p-2.5 text-sm" style={controlStyle} />
                </label>
                <label className="text-xs font-semibold" style={{ color: colors.muted }}>
                  {es ? 'Hasta' : 'To'}
                  <input type="month" value={endMonth}
                    onChange={(e) => { setEndMonth(e.target.value); invalidate(); }}
                    className="mt-1 block w-full rounded-lg border p-2.5 text-sm" style={controlStyle} />
                </label>
              </div>
              <p className="mt-2 text-xs leading-5" style={{ color: isRangeInvalid ? '#B45309' : colors.muted }}>
                {isRangeInvalid
                  ? (es ? 'Elige ambos meses y asegúrate de que el final no sea anterior al inicio.' : 'Choose both months in chronological order.')
                  : (es
                    ? 'Deja ambos vacíos para usar todo el historial. El filtro abarca meses calendario completos; se omitirán indicadores que no puedan filtrarse correctamente.'
                    : 'Leave both blank to use all history. The filter includes entire calendar months; non-filterable global metrics will be omitted.')}
              </p>
            </div>

            <div className="rounded-2xl border p-5" style={cardStyle}>
              <h2 className="mb-3 font-extrabold" style={{ color: colors.text }}>{es ? 'Secciones del PDF' : 'PDF sections'}</h2>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {SECTIONS.map((section) => (
                  <label key={section.key} className="flex cursor-pointer items-center gap-2 rounded-xl border p-3 text-sm"
                    style={controlStyle}>
                    <input type="checkbox" checked={sections.includes(section.key)}
                      onChange={() => toggleSection(section.key)}
                      className="h-4 w-4 shrink-0" />
                    <span>{es ? section.es : section.en}</span>
                  </label>
                ))}
              </div>
              {sections.includes('predictive') && (
                <label className="mt-4 block text-sm font-semibold" style={{ color: colors.text }}>
                  {es ? 'Meses a pronosticar' : 'Forecast horizon (months)'}
                  <select value={horizon}
                    onChange={(e) => { setHorizon(Number(e.target.value)); invalidate(); }}
                    className="ml-2 rounded-lg border px-3 py-2" style={controlStyle}>
                    {[1, 3, 6, 9, 12].map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
              )}
            </div>

            {sections.includes('visualizations') && (
              <div className="rounded-2xl border p-5" style={cardStyle}>
                <h2 className="mb-2 font-extrabold" style={{ color: colors.text }}>
                  {es ? 'Gráficas guardadas' : 'Saved charts'}
                </h2>
                <p className="mb-3 text-xs leading-5" style={{ color: colors.muted }}>
                  {es
                    ? 'Escoge hasta ocho. Se aplicarán los filtros del gráfico y el período del reporte cuando la fuente permita hacerlo con certeza.'
                    : 'Select up to eight. Chart filters and report dates will apply only where supported safely.'}
                </p>
                {options.saved_visualizations.length ? (
                  <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                    {options.saved_visualizations.map((item) => (
                      <label key={item.id} className="flex cursor-pointer items-center gap-3 rounded-lg border p-2.5 text-sm"
                        style={controlStyle}>
                        <input type="checkbox" checked={visualizationIds.includes(item.id)}
                          disabled={visualizationIds.length >= 8 && !visualizationIds.includes(item.id)}
                          onChange={() => toggleVisualization(item.id)} />
                        <span className="min-w-0 flex-1 truncate">{item.title}</span>
                        <span className="text-xs uppercase" style={{ color: colors.muted }}>{item.type}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm" style={{ color: colors.muted }}>
                    {es ? 'Todavía no hay visualizaciones guardadas en esta fuente.' : 'No saved visualizations in this source yet.'}
                  </p>
                )}
              </div>
            )}
          </div>

          <aside className="min-w-0">
            <div className="sticky top-4 rounded-2xl border p-5 shadow-sm" style={cardStyle}>
              <div className="flex items-center gap-2 font-extrabold" style={{ color: colors.text }}>
                <Eye size={20} /> {es ? 'Vista previa del contenido' : 'Content preview'}
              </div>
              <p className="mt-1 text-xs leading-5" style={{ color: colors.muted }}>
                {es ? 'Muestra lo que el informe incluirá; el PDF se genera con los datos disponibles al descargar.' : 'Shows the selected content; the PDF is generated with live data at download time.'}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" disabled={!isConfigurationValid || Boolean(busy)}
                  onClick={showPreview} className="flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-bold disabled:opacity-50"
                  style={{ borderColor: theme.primary, color: theme.primary }}>
                  {busy === 'preview' ? <LoaderCircle size={16} className="animate-spin" /> : <Eye size={16} />}
                  {es ? 'Previsualizar' : 'Preview'}
                </button>
                <button type="button" disabled={!isConfigurationValid || Boolean(busy)}
                  onClick={download} className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-bold disabled:opacity-50"
                  style={{ backgroundColor: theme.primary, color: '#fff' }}>
                  {busy === 'download' ? <LoaderCircle size={16} className="animate-spin" /> : <Download size={16} />}
                  {es ? 'Descargar PDF' : 'Download PDF'}
                </button>
              </div>
              {lastFile && (
                <div className="mt-3 flex items-center gap-2 text-xs" style={{ color: theme.primary }}>
                  <CheckCircle2 size={16} /> {es ? 'Generado' : 'Generated'}: {lastFile}
                </div>
              )}
              {preview ? (
                <div className="mt-5 max-h-[68vh] space-y-4 overflow-y-auto pr-1">
                  <div className="rounded-xl p-3" style={{ backgroundColor: colors.cardSoft }}>
                    <p className="font-extrabold" style={{ color: colors.text }}>{preview.title}</p>
                    <p className="mt-1 text-xs" style={{ color: colors.muted }}>
                      {preview.period ? `${preview.period.from} → ${preview.period.to}` : (es ? 'Historial completo' : 'Full history')}
                    </p>
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-bold uppercase" style={{ color: colors.muted }}>{es ? 'Secciones' : 'Sections'}</p>
                    {preview.sections.map((item) => (
                      <p key={item} className="py-1 text-sm" style={{ color: colors.text }}>
                        <CheckCircle2 size={13} className="mr-2 inline" style={{ color: theme.primary }} />
                        {SECTIONS.find((section) => section.key === item)?.[es ? 'es' : 'en'] || item}
                      </p>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {preview.kpis.slice(0, 4).map((kpi) => (
                      <div key={kpi.role} className="rounded-lg border p-3" style={controlStyle}>
                        <p className="text-xs capitalize" style={{ color: colors.muted }}>{kpi.role.replaceAll('_', ' ')}</p>
                        <p className="text-lg font-extrabold" style={{ color: colors.text }}>{displayNumber(kpi.value)}</p>
                      </div>
                    ))}
                  </div>
                  {preview.trend.periods > 0 && (
                    <div className="rounded-xl border p-3" style={controlStyle}>
                      <p className="text-xs font-bold uppercase" style={{ color: colors.muted }}>{es ? 'Tendencia' : 'Trend'}</p>
                      <p className="mt-1 text-sm" style={{ color: colors.text }}>
                        {es ? 'Último período:' : 'Latest period:'} {preview.trend.current?.period}
                      </p>
                      <p className="mt-1 text-sm" style={{ color: colors.text }}>
                        {es ? 'Valor:' : 'Value:'} {displayNumber(preview.trend.current?.total)}
                        {' · '}{es ? 'Meses evaluados:' : 'Months evaluated:'} {preview.trend.periods}
                      </p>
                    </div>
                  )}
                  {preview.sections.includes('predictive') && (
                    <p className="text-xs" style={{ color: colors.muted }}>
                      {es ? 'Modelo:' : 'Model:'} {preview.forecast.model || (es ? 'No disponible' : 'Unavailable')}
                      {' · '}{es ? 'Anomalías:' : 'Anomalies:'} {preview.anomaly_count}
                    </p>
                  )}
                  {!!preview.visualizations.length && (
                    <div>
                      <p className="font-bold text-sm" style={{ color: colors.text }}>{es ? 'Gráficas incluidas' : 'Included charts'}</p>
                      {preview.visualizations.map((item) => (
                        <p className="mt-1 text-xs" style={{ color: colors.muted }} key={item.id}>
                          {item.title} · {item.rows} {es ? 'filas' : 'rows'}
                        </p>
                      ))}
                    </div>
                  )}
                  {!!preview.warnings.length && (
                    <div className="rounded-xl border p-3" style={{ borderColor: '#F59E0B88', backgroundColor: '#F59E0B10' }}>
                      <p className="font-bold text-sm" style={{ color: colors.text }}>{es ? 'Limitaciones detectadas' : 'Detected limitations'}</p>
                      {preview.warnings.map((message, index) => (
                        <p key={index} className="mt-2 text-xs leading-5" style={{ color: colors.muted }}>{message}</p>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-6 flex flex-col items-center justify-center rounded-xl border border-dashed px-4 py-10 text-center" style={{ borderColor: colors.border }}>
                  <BarChart3 size={25} style={{ color: colors.muted }} />
                  <p className="mt-3 text-sm" style={{ color: colors.muted }}>
                    {es ? 'Configura tu informe y selecciona Previsualizar.' : 'Configure your report and select Preview.'}
                  </p>
                </div>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
};
