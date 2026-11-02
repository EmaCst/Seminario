import { useContext } from 'react';
import { Database, Settings2 } from 'lucide-react';
import { DashboardProvider, DashboardContext } from './context/DashboardContext';
import { Sidebar } from './components/Sidebar';
import { UniversalDashboard } from './components/UniversalDashboard';
import { SettingsView } from './components/SettingsView';
import { PredictionsView } from './components/PredictionsView';
import { AnalyticsView } from './components/AnalyticsView';
import { ReportsView } from './components/ReportsView';
import { Header } from './components/Header';
import { Chatbot } from './components/Chatbot';
import { CustomizationPanel } from './components/CustomizationPanel';

const MainLayout = () => {
  const { activeTab, setActiveTab, colors, theme, language, sourceReady, sourceRevision, sourceStatus } = useContext(DashboardContext);
  const noSource = sourceStatus?.connected === false;
  const sourceUnavailable = sourceReady && sourceStatus == null;
  // A new connection means a new data workspace, not just a new title.
  // Remounting discards chat turns, outstanding previews, cached React data,
  // report selections and open visualization editors in one operation.
  const workspaceKey = sourceRevision || 'disconnected';

  return (
    <div className="min-h-screen transition-colors duration-300 p-2 sm:p-4 lg:p-6" style={{ backgroundColor: colors.page }}>
      <div
        className="mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-[1500px] overflow-hidden rounded-[28px] border shadow-2xl transition-colors duration-300"
        style={{ backgroundColor: colors.panel, borderColor: colors.border }}
      >
        <Sidebar />
        <div className="min-w-0 flex-1 flex flex-col">
          <Header />
          <main className="flex-1 overflow-y-auto p-5 sm:p-6 lg:p-8">
            {!sourceReady && (
              <p className="py-14 text-center text-sm" style={{color:colors.muted}}>
                Comprobando la fuente activa de Kenneth…
              </p>
            )}
            {sourceReady && activeTab !== 'settings' && (noSource || sourceUnavailable) && (
              <section className="mx-auto flex max-w-xl flex-col items-center rounded-2xl border p-8 text-center shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                  <Database size={28} />
                </div>
                <h2 className="text-2xl font-extrabold" style={{ color: colors.text }}>
                  {noSource
                    ? (language === 'es' ? 'Conecta una fuente de datos para comenzar' : 'Connect a data source to get started')
                    : (language === 'es' ? 'No se pudo contactar con el servidor' : 'Could not reach the server')}
                </h2>
                <p className="mt-3 text-sm leading-6" style={{ color: colors.muted }}>
                  {noSource
                    ? (language === 'es'
                      ? 'Todavía no hay una base de datos conectada. Desde Configuración puedes conectar SQL Server o PostgreSQL, o importar un archivo Excel para generar tus análisis y gráficos.'
                      : 'There is no database connected yet. Open Settings to connect SQL Server or PostgreSQL, or import an Excel file to generate charts and insights.')
                    : (language === 'es'
                      ? 'No fue posible verificar la conexión con el backend. Comprueba que el servidor esté funcionando y vuelve a intentarlo.'
                      : 'The backend connection could not be verified. Make sure the server is running and try again.')}
                </p>
                {noSource && (
                  <button
                    type="button"
                    onClick={() => setActiveTab('settings')}
                    className="mt-6 inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
                    style={{ backgroundColor: theme.primary }}
                  >
                    <Settings2 size={18} />
                    {language === 'es' ? 'Ir a Configuración' : 'Open Settings'}
                  </button>
                )}
              </section>
            )}
            {sourceReady && !noSource && !sourceUnavailable && activeTab === 'dashboard' && <UniversalDashboard key={workspaceKey} />}
            {sourceReady && !noSource && !sourceUnavailable && activeTab === 'analytics' && <AnalyticsView key={workspaceKey} />}
            {sourceReady && !noSource && !sourceUnavailable && activeTab === 'predictions' && <PredictionsView key={workspaceKey} />}
            {sourceReady && !noSource && !sourceUnavailable && activeTab === 'reports' && <ReportsView key={workspaceKey} />}
            {sourceReady && activeTab === 'settings' && <SettingsView key={workspaceKey} />}
          </main>
        </div>
      </div>
      {sourceReady && !noSource && !sourceUnavailable && <Chatbot key={workspaceKey} />}
      <CustomizationPanel />
    </div>
  );
};

export default function App() {
  return (
    <DashboardProvider>
      <MainLayout />
    </DashboardProvider>
  );
}
