import { useContext, useEffect, useState } from 'react';
import {
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Database,
  Download,
  FileText,
  Layers3,
  LoaderCircle,
} from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { downloadReportPdf, getAdaptiveAnalytics } from '../services/api';

const reportOptions = [
  {
    type: 'executive',
    icon: FileText,
    title: 'Resumen ejecutivo',
    description: 'KPIs, comportamiento reciente e insights clave para una lectura rápida del negocio.',
    includes: ['Fuente y dominio', 'KPIs principales', 'Comparación mensual', 'Mejor y menor período', 'Insights automáticos'],
  },
  {
    type: 'analytics',
    icon: BarChart3,
    title: 'Reporte analítico',
    description: 'Desglose detallado de tendencias, rankings, distribuciones y métricas secundarias.',
    includes: ['Detalle temporal', 'Rankings del negocio', 'Distribuciones', 'Métricas secundarias', 'Datos acumulados'],
  },
  {
    type: 'predictive',
    icon: BrainCircuit,
    title: 'Reporte predictivo',
    description: 'Pronóstico a tres meses y detección automática de comportamientos atípicos.',
    includes: ['Regresión lineal', 'R²', 'Pronóstico 3 meses', 'Isolation Forest', 'Anomalías detectadas'],
  },
  {
    type: 'complete',
    icon: Layers3,
    title: 'Reporte completo',
    description: 'Documento integral con resumen ejecutivo, analítica y apartado predictivo.',
    includes: ['Resumen ejecutivo', 'Analítica detallada', 'Rankings y distribuciones', 'Predicciones', 'Anomalías'],
  },
];

export const ReportsView = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [source, setSource] = useState(null);
  const [downloading, setDownloading] = useState('');
  const [error, setError] = useState('');
  const [lastDownloaded, setLastDownloaded] = useState('');

  useEffect(() => {
    getAdaptiveAnalytics()
      .then(setSource)
      .catch(() => setSource(null));
  }, []);

  const handleDownload = async (type) => {
    setDownloading(type);
    setError('');
    setLastDownloaded('');

    try {
      const { blob, filename } = await downloadReportPdf(type);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setLastDownloaded(type);
    } catch (err) {
      setError(err.message || 'No fue posible generar el reporte.');
    } finally {
      setDownloading('');
    }
  };

  return (
    <section className="space-y-5">
      <div>
        <div className="flex items-center gap-2 mb-1" style={{ color: theme.primary }}>
          <FileText size={22} />
          <span className="text-sm font-bold uppercase tracking-wide">Reporting</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
          {language === 'es' ? 'Reportes' : 'Reports'}
        </h1>
        <p className="mt-2 max-w-3xl" style={{ color: colors.muted }}>
          {language === 'es'
            ? 'Genera documentos PDF adaptados automáticamente al dominio, estructura y datos de la base activa.'
            : 'Generate PDF documents automatically adapted to the active database domain, structure and data.'}
        </p>
      </div>

      <div
        className="rounded-2xl border p-5 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4"
        style={{ backgroundColor: colors.card, borderColor: colors.border }}
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
            <Database size={23} />
          </div>
          <div>
            <p className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Fuente del reporte' : 'Report source'}</p>
            <p className="font-extrabold text-lg" style={{ color: colors.text }}>{source?.database || 'Base activa'}</p>
            <p className="text-sm capitalize" style={{ color: colors.muted }}>
              {source ? `${source.domain || 'generic'} · ${source.provider || ''}` : 'Los reportes usarán la conexión activa'}
            </p>
          </div>
        </div>
        <div className="text-sm max-w-xl" style={{ color: colors.muted }}>
          {language === 'es'
            ? 'El contenido se construye al momento de descargarlo, por lo que refleja los datos disponibles en ese instante.'
            : 'Content is built at download time, so it reflects the data available at that moment.'}
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border p-4" style={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2', color: '#B91C1C' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {reportOptions.map((report) => {
          const Icon = report.icon;
          const isLoading = downloading === report.type;
          const wasDownloaded = lastDownloaded === report.type;

          return (
            <article
              key={report.type}
              className="rounded-2xl border p-5 shadow-sm flex flex-col"
              style={{ backgroundColor: colors.card, borderColor: colors.border }}
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                  <Icon size={23} />
                </div>
                <div>
                  <h2 className="font-extrabold text-xl" style={{ color: colors.text }}>{report.title}</h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: colors.muted }}>{report.description}</p>
                </div>
              </div>

              <div className="mt-5 rounded-2xl border p-4 flex-1" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}>
                <p className="text-xs font-bold uppercase tracking-wide mb-3" style={{ color: colors.muted }}>
                  {language === 'es' ? 'Incluye' : 'Includes'}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {report.includes.map((item) => (
                    <div key={item} className="flex items-center gap-2 text-sm" style={{ color: colors.text }}>
                      <CheckCircle2 size={15} style={{ color: theme.primary }} />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between gap-3">
                <div className="text-xs" style={{ color: colors.muted }}>
                  PDF · {language === 'es' ? 'generación dinámica' : 'dynamic generation'}
                </div>
                <button
                  onClick={() => handleDownload(report.type)}
                  disabled={Boolean(downloading)}
                  className="rounded-xl px-4 py-2.5 flex items-center gap-2 font-bold disabled:opacity-60"
                  style={{ backgroundColor: theme.primary, color: '#fff' }}
                >
                  {isLoading ? <LoaderCircle size={17} className="animate-spin" /> : <Download size={17} />}
                  {isLoading
                    ? (language === 'es' ? 'Generando...' : 'Generating...')
                    : wasDownloaded
                      ? (language === 'es' ? 'Descargar otra vez' : 'Download again')
                      : (language === 'es' ? 'Generar PDF' : 'Generate PDF')}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <div className="rounded-2xl border p-4 text-sm" style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.muted }}>
        <strong style={{ color: colors.text }}>{language === 'es' ? 'Nota:' : 'Note:'}</strong>{' '}
        {language === 'es'
          ? 'El reporte predictivo solo incluye pronósticos y anomalías cuando la base posee suficientes datos temporales para ejecutar los modelos.'
          : 'The predictive report only includes forecasts and anomalies when the database has enough time-series data to run the models.'}
      </div>
    </section>
  );
};
