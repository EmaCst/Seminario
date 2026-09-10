import { useContext, useState } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import {
  Check,
  Moon,
  Sun,
  Languages,
  Palette,
  ChartNoAxesCombined,
  Database,
  Server,
  FileSpreadsheet,
  Construction,
} from 'lucide-react';
import { DatabaseConfig } from './DatabaseConfig';
import { DatabaseUpload } from './DatabaseUpload';

const DataSourceSwitcher = ({ source, setSource, theme, colors, language }) => {
  const options = [
    {
      id: 'sqlserver',
      label: 'SQL Server',
      icon: Database,
      status: language === 'es' ? 'Disponible' : 'Available',
      enabled: true,
    },
    {
      id: 'postgresql',
      label: 'PostgreSQL',
      icon: Server,
      status: language === 'es' ? 'En desarrollo' : 'In development',
      enabled: true,
    },
    {
      id: 'excel',
      label: 'Excel',
      icon: FileSpreadsheet,
      status: language === 'es' ? 'En evaluación' : 'Under evaluation',
      enabled: true,
    },
  ];

  return (
    <section
      className="p-5 sm:p-6 rounded-2xl border shadow-sm"
      style={{ backgroundColor: colors.card, borderColor: colors.border }}
    >
      <div className="flex items-start gap-3 mb-5">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: colors.accentSoft, color: theme.primary }}
        >
          <Database size={20} />
        </div>
        <div>
          <h3 className="text-lg font-bold" style={{ color: colors.text }}>
            {language === 'es' ? 'Fuente de datos' : 'Data source'}
          </h3>
          <p className="text-sm" style={{ color: colors.muted }}>
            {language === 'es'
              ? 'Selecciona el origen que deseas conectar o cargar en Kenneth.'
              : 'Choose the source you want to connect or upload to Kenneth.'}
          </p>
        </div>
      </div>

      <div
        className="grid grid-cols-1 sm:grid-cols-3 overflow-hidden rounded-xl border"
        style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}
      >
        {options.map((option, index) => {
          const selected = source === option.id;
          const Icon = option.icon;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => option.enabled && setSource(option.id)}
              className="relative px-4 py-4 sm:py-3.5 transition-all text-left sm:text-center flex sm:flex-col items-center justify-between sm:justify-center gap-2"
              style={{
                backgroundColor: selected ? theme.primary : 'transparent',
                color: selected ? '#fff' : colors.text,
                borderLeft: index > 0 ? `1px solid ${colors.border}` : undefined,
              }}
            >
              <div className="flex items-center gap-2 font-bold">
                <Icon size={18} />
                <span>{option.label}</span>
              </div>
              <span
                className="text-[11px] font-semibold rounded-full px-2 py-0.5"
                style={{
                  backgroundColor: selected ? 'rgba(255,255,255,0.16)' : colors.accentSoft,
                  color: selected ? '#fff' : theme.primary,
                }}
              >
                {option.status}
              </span>

              {selected && (
                <span
                  className="hidden sm:block absolute -bottom-2 left-1/2 -translate-x-1/2 rotate-45 w-4 h-4"
                  style={{ backgroundColor: theme.primary }}
                />
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
};

const SourcePlaceholder = ({ source, theme, colors, language }) => {
  const isPostgres = source === 'postgresql';
  const title = isPostgres ? 'PostgreSQL' : 'Excel';
  const Icon = isPostgres ? Server : FileSpreadsheet;

  return (
    <section
      className="p-5 sm:p-6 rounded-2xl border shadow-sm"
      style={{ backgroundColor: colors.card, borderColor: colors.border }}
    >
      <div className="min-h-52 rounded-2xl border border-dashed p-8 flex flex-col items-center justify-center text-center"
        style={{ borderColor: colors.border, backgroundColor: colors.cardSoft }}
      >
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
          style={{ backgroundColor: colors.accentSoft, color: theme.primary }}
        >
          <Icon size={28} />
        </div>
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-xl font-extrabold" style={{ color: colors.text }}>{title}</h3>
          <Construction size={18} style={{ color: theme.primary }} />
        </div>
        <p className="max-w-2xl text-sm leading-6" style={{ color: colors.muted }}>
          {isPostgres
            ? (language === 'es'
                ? 'La interfaz ya está reservada para PostgreSQL. Aquí aparecerán la conexión por host, puerto, base de datos y credenciales, además de la carga de archivos .dump, .backup y .sql cuando implementemos el backend.'
                : 'The interface is already reserved for PostgreSQL. Connection fields and .dump, .backup and .sql uploads will appear here once the backend is implemented.')
            : (language === 'es'
                ? 'Excel queda reservado como una futura fuente de datos. Si se aprueba, esta vista permitirá cargar .xlsx, .xls o .csv y transformar sus hojas en entidades para el Semantic Mapper.'
                : 'Excel is reserved as a future data source. If approved, this view will allow .xlsx, .xls or .csv uploads and map sheets into Semantic Mapper entities.')}
        </p>
      </div>
    </section>
  );
};

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

  const [dataSource, setDataSource] = useState('sqlserver');
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

      <DataSourceSwitcher
        source={dataSource}
        setSource={setDataSource}
        theme={theme}
        colors={colors}
        language={language}
      />

      {dataSource === 'sqlserver' ? (
        <>
          <DatabaseUpload />
          <DatabaseConfig />
        </>
      ) : (
        <SourcePlaceholder
          source={dataSource}
          theme={theme}
          colors={colors}
          language={language}
        />
      )}

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
