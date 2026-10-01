import { useContext } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { Sun, Moon, Check } from 'lucide-react';

export const Header = () => {
  const {
    theme,
    themeId,
    themes,
    setThemeId,
    colors,
    t,
    isDarkMode,
    setIsDarkMode,
    language,
    setLanguage,
  } = useContext(DashboardContext);

  return (
    <header
      className="px-5 sm:px-6 lg:px-8 py-5 flex flex-col xl:flex-row xl:items-center justify-between gap-4 border-b transition-colors duration-300"
      style={{ borderColor: colors.border, backgroundColor: colors.panel }}
    >
      <div className="min-w-0">
        <h1 className="text-lg sm:text-xl lg:text-2xl font-extrabold tracking-tight truncate" style={{ color: theme.primary }}>
          {t.university}
        </h1>
        <p className="text-xs sm:text-sm mt-1" style={{ color: colors.muted }}>
          {t.welcome}: David Emanuel Castellanos Velásquez
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <div
          className="flex items-center gap-1 p-1 rounded-full border"
          style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}
          aria-label={t.themeColor}
        >
          {Object.values(themes).map((palette) => (
            <button
              key={palette.id}
              onClick={() => setThemeId(palette.id)}
              title={t[palette.nameKey]}
              aria-label={t[palette.nameKey]}
              className="relative w-7 h-7 rounded-full transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-offset-2"
              style={{ backgroundColor: palette.primary, '--tw-ring-color': palette.primary }}
            >
              {themeId === palette.id && <Check className="absolute inset-0 m-auto w-4 h-4 text-white" strokeWidth={3} />}
            </button>
          ))}
        </div>

        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className="h-10 px-3 rounded-full border flex items-center gap-2 font-semibold text-xs sm:text-sm transition-all hover:scale-[1.02]"
          style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text }}
          aria-label={isDarkMode ? t.lightMode : t.darkMode}
          title={isDarkMode ? t.lightMode : t.darkMode}
        >
          {isDarkMode ? <Sun className="w-4 h-4" style={{ color: theme.primary }} /> : <Moon className="w-4 h-4" style={{ color: theme.primary }} />}
          <span className="hidden sm:inline">{isDarkMode ? t.lightMode : t.darkMode}</span>
        </button>

        <div
          className="flex p-1 rounded-full border text-xs font-bold"
          style={{ backgroundColor: colors.cardSoft, borderColor: colors.border }}
        >
          {['es', 'en'].map((code) => {
            const active = language === code;
            return (
              <button
                key={code}
                onClick={() => setLanguage(code)}
                className="px-3 py-1.5 rounded-full transition-all"
                style={active ? { backgroundColor: theme.primary, color: '#fff' } : { color: colors.muted }}
                aria-pressed={active}
              >
                {code.toUpperCase()}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
