import { useContext } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { Check, Moon, Sun, Languages, Palette, ChartNoAxesCombined } from 'lucide-react';
import { DatabaseConfig } from './DatabaseConfig';
import { DatabaseUpload } from './DatabaseUpload';

export const SettingsView = () => {
  const {
    theme,
    themeId,
    themes,
    setThemeId,
    colors,
    visibleCharts,
    toggleChart,
    isDarkMode,
    setIsDarkMode,
    language,
    setLanguage,
    t,
  } = useContext(DashboardContext);

  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border };

  const settings = [
    { key: 'monthSales', label: t.showMonthSales },
    { key: 'salesPerMonth', label: t.showSalesPerMonth },
    { key: 'topProducts', label: t.showTopProducts },
  ];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>{t.settings}</h2>
        <p className="mt-2" style={{ color: colors.muted }}>{t.appearanceText}</p>
      </div>

      <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}>
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
            <Palette size={20} />
          </div>
          <div>
            <h3 className="text-lg font-bold" style={{ color: colors.text }}>{t.themeColor}</h3>
            <p className="text-sm" style={{ color: colors.muted }}>{t.chooseTheme}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {Object.values(themes).map((palette) => {
            const selected = palette.id === themeId;
            return (
              <button
                key={palette.id}
                onClick={() => setThemeId(palette.id)}
                className="rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md"
                style={{ borderColor: selected ? palette.primary : colors.border, backgroundColor: colors.cardSoft, boxShadow: selected ? `0 0 0 2px ${palette.primary}22` : undefined }}
              >
                <div className="flex items-center justify-between gap-2 mb-4">
                  <span className="w-11 h-11 rounded-xl shadow-sm" style={{ backgroundColor: palette.primary }} />
                  {selected && (
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-white" style={{ backgroundColor: palette.primary }}>
                      <Check size={16} strokeWidth={3} />
                    </span>
                  )}
                </div>
                <div className="font-bold" style={{ color: colors.text }}>{t[palette.nameKey]}</div>
                {selected && <div className="text-xs mt-1 font-semibold" style={{ color: palette.primary }}>{t.selected}</div>}
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}>
          <div className="flex items-start gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
              {isDarkMode ? <Moon size={20} /> : <Sun size={20} />}
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: colors.text }}>{t.displayMode}</h3>
              <p className="text-sm" style={{ color: colors.muted }}>{t.displayModeText}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setIsDarkMode(false)}
              className="rounded-xl border p-4 flex items-center justify-center gap-2 font-bold transition-all"
              style={!isDarkMode ? { backgroundColor: theme.primary, color: '#fff', borderColor: theme.primary } : { color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}
            >
              <Sun size={18} /> {t.lightMode}
            </button>
            <button
              onClick={() => setIsDarkMode(true)}
              className="rounded-xl border p-4 flex items-center justify-center gap-2 font-bold transition-all"
              style={isDarkMode ? { backgroundColor: theme.primary, color: '#fff', borderColor: theme.primary } : { color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}
            >
              <Moon size={18} /> {t.darkMode}
            </button>
          </div>
        </section>

        <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}>
          <div className="flex items-start gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
              <Languages size={20} />
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: colors.text }}>{t.language}</h3>
              <p className="text-sm" style={{ color: colors.muted }}>{t.languageText}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setLanguage('es')}
              className="rounded-xl border p-4 font-bold transition-all"
              style={language === 'es' ? { backgroundColor: theme.primary, color: '#fff', borderColor: theme.primary } : { color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}
            >
              {t.spanish}
            </button>
            <button
              onClick={() => setLanguage('en')}
              className="rounded-xl border p-4 font-bold transition-all"
              style={language === 'en' ? { backgroundColor: theme.primary, color: '#fff', borderColor: theme.primary } : { color: colors.text, borderColor: colors.border, backgroundColor: colors.cardSoft }}
            >
              {t.english}
            </button>
          </div>
        </section>
      </div>

      <DatabaseUpload />
      <DatabaseConfig />

      <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}>
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
            <ChartNoAxesCombined size={20} />
          </div>
          <div>
            <h3 className="text-lg font-bold" style={{ color: colors.text }}>{t.chartVisibility}</h3>
          </div>
        </div>

        <div className="space-y-3">
          {settings.map((item) => (
            <label key={item.key} className="flex items-center justify-between gap-4 rounded-xl border px-4 py-3 cursor-pointer" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}>
              <span className="font-medium" style={{ color: colors.text }}>{item.label}</span>
              <input
                type="checkbox"
                checked={visibleCharts[item.key]}
                onChange={() => toggleChart(item.key)}
                className="w-5 h-5 rounded cursor-pointer"
                style={{ accentColor: theme.primary }}
              />
            </label>
          ))}
        </div>
      </section>
    </div>
  );
};
