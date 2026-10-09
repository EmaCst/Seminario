import { useContext } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { LayoutDashboard, ChartNoAxesCombined, BrainCircuit, FileText, Settings, LogOut } from 'lucide-react';

const menuItems = [
  { id: 'dashboard', labelKey: 'dashboard', icon: LayoutDashboard },
  { id: 'analytics', labelKey: 'analytics', icon: ChartNoAxesCombined },
  { id: 'predictions', labelKey: 'predictions', icon: BrainCircuit },
  { id: 'reports', labelKey: 'reports', icon: FileText },
  { id: 'settings', labelKey: 'settings', icon: Settings },
  { id: 'logout', labelKey: 'logout', icon: LogOut },
];

export const Sidebar = () => {
  const { activeTab, setActiveTab, theme, colors, t, institutionLogo, institutionName } = useContext(DashboardContext);

  return (
    <aside
      className="w-[82px] sm:w-56 shrink-0 p-3 sm:p-4 flex flex-col items-center transition-colors duration-300"
      style={{ background: `linear-gradient(180deg, ${colors.sidebar} 0%, ${theme.primaryStrong} 100%)` }}
    >
      <div className="mb-7 mt-2 w-14 h-14 sm:w-20 sm:h-20 rounded-full flex items-center justify-center overflow-hidden border-[3px] border-white/70 bg-white shadow-lg">
        {institutionLogo ? <img src={institutionLogo} alt={institutionName} className="object-contain w-full h-full" /> : <strong className="text-sm sm:text-base" style={{color:'#0B4E8A'}}>{institutionName.split(/\\s+/).filter(Boolean).map(word=>word[0]).slice(0,4).join('').toUpperCase()}</strong>}
      </div>

      <nav className="w-full space-y-2">
        {menuItems.map(({ id, labelKey, icon: Icon }) => {
          const isActive = activeTab === id;
          const isLogout = id === 'logout';
          return (
            <button
              key={id}
              onClick={() => !isLogout && setActiveTab(id)}
              className="w-full min-h-11 px-3 rounded-xl font-semibold transition-all duration-200 flex items-center justify-center sm:justify-start gap-3 text-sm hover:bg-white/14"
              style={{
                backgroundColor: isActive ? 'rgba(255,255,255,0.96)' : 'transparent',
                color: isActive ? theme.primaryStrong : 'rgba(255,255,255,0.94)',
                boxShadow: isActive ? '0 5px 16px rgba(0,0,0,0.16)' : 'none',
              }}
              title={t[labelKey]}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="hidden sm:inline truncate">{t[labelKey]}</span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto hidden sm:block text-[10px] text-center text-white/70 px-2 pb-2">
        {t.currentTheme}: {t[theme.nameKey]}
      </div>
    </aside>
  );
};
