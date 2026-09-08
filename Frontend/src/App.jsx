import { useContext } from 'react';
import { DashboardProvider, DashboardContext } from './context/DashboardContext';
import { Sidebar } from './components/Sidebar';
import { UniversalDashboard } from './components/UniversalDashboard';
import { SettingsView } from './components/SettingsView';
import { Header } from './components/Header';
import { BarChart3, FileText } from 'lucide-react';
import { Chatbot } from './components/Chatbot';

const PlaceholderView = ({ type }) => {
  const { theme, colors, t } = useContext(DashboardContext);
  const isAnalytics = type === 'analytics';
  const Icon = isAnalytics ? BarChart3 : FileText;

  return (
    <section className="space-y-5">
      <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
        {isAnalytics ? t.analyticsTitle : t.reportsTitle}
      </h1>
      <div
        className="rounded-2xl border p-8 min-h-56 flex flex-col items-center justify-center text-center shadow-sm"
        style={{ backgroundColor: colors.card, borderColor: colors.border }}
      >
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
          <Icon size={28} />
        </div>
        <p className="max-w-xl text-base" style={{ color: colors.muted }}>
          {isAnalytics ? t.analyticsText : t.reportsText}
        </p>
      </div>
    </section>
  );
};

const MainLayout = () => {
  const { activeTab, colors } = useContext(DashboardContext);

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
            {activeTab === 'dashboard' && <UniversalDashboard />}
            {activeTab === 'settings' && <SettingsView />}
            {activeTab === 'analytics' && <PlaceholderView type="analytics" />}
            {activeTab === 'reports' && <PlaceholderView type="reports" />}
          </main>
        </div>
      </div>
      <Chatbot />
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
