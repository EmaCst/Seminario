import { useContext } from 'react';
import { DashboardProvider, DashboardContext } from './context/DashboardContext';
import { Sidebar } from './components/Sidebar';
import { UniversalDashboard } from './components/UniversalDashboard';
import { SettingsView } from './components/SettingsView';
import { PredictionsView } from './components/PredictionsView';
import { AnalyticsView } from './components/AnalyticsView';
import { ReportsView } from './components/ReportsView';
import { Header } from './components/Header';
import { Chatbot } from './components/Chatbot';

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
            {activeTab === 'analytics' && <AnalyticsView />}
            {activeTab === 'predictions' && <PredictionsView />}
            {activeTab === 'reports' && <ReportsView />}
            {activeTab === 'settings' && <SettingsView />}
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
