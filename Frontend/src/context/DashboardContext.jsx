/* eslint-disable react-refresh/only-export-components */
import { createContext, useEffect, useMemo, useState } from 'react';

export const DashboardContext = createContext();

export const THEMES = {
  blue: {
    id: 'blue',
    nameKey: 'blueProfessional',
    primary: '#1269B0',
    primaryStrong: '#0B4E8A',
    soft: '#EAF4FC',
    sidebarLight: '#0D4D86',
    sidebarDark: '#0B3B68',
    darkBackground: '#0F1724',
    darkPanel: '#131E2D',
    darkCard: '#192637',
  },
  green: {
    id: 'green',
    nameKey: 'greenTechnology',
    primary: '#198A43',
    primaryStrong: '#116633',
    soft: '#EAF7EE',
    sidebarLight: '#1A7A3D',
    sidebarDark: '#123E27',
    darkBackground: '#101C15',
    darkPanel: '#14251B',
    darkCard: '#1A2F22',
  },
  purple: {
    id: 'purple',
    nameKey: 'purpleElegant',
    primary: '#6B3BB2',
    primaryStrong: '#4F258E',
    soft: '#F3ECFB',
    sidebarLight: '#5A2E99',
    sidebarDark: '#35204E',
    darkBackground: '#17131E',
    darkPanel: '#20192B',
    darkCard: '#2A2038',
  },
  orange: {
    id: 'orange',
    nameKey: 'orangeGray',
    primary: '#EA6A0A',
    primaryStrong: '#C65300',
    soft: '#FFF1E6',
    sidebarLight: '#252C32',
    sidebarDark: '#1D2429',
    darkBackground: '#14191D',
    darkPanel: '#1B2227',
    darkCard: '#222B31',
  },
};

const translations = {
  es: {
    university: 'Universidad Mariano Gálvez de Guatemala',
    welcome: 'Bienvenido',
    dashboard: 'Dashboard',
    analytics: 'Analítica',
    reports: 'Reportes',
    settings: 'Configuración',
    logout: 'Cerrar sesión',
    monthSales: 'Ventas del mes',
    salesPerMonth: 'Ventas por mes',
    topProducts: 'Productos más vendidos',
    product: 'Producto',
    sales: 'Ventas',
    stock: 'Existencias',
    status: 'Estado',
    active: 'Activo',
    analyticsTitle: 'Analítica',
    analyticsText: 'Vista de analítica preparada para integrar indicadores y métricas del sistema.',
    reportsTitle: 'Reportes',
    reportsText: 'Vista de reportes preparada para integrar exportaciones y consultas.',
    appearance: 'Apariencia',
    appearanceText: 'Personaliza los colores, el modo de visualización y el idioma de la interfaz.',
    themeColor: 'Color de la interfaz',
    chooseTheme: 'Elige una de las cuatro paletas definidas para el proyecto.',
    blueProfessional: 'Azul Profesional',
    greenTechnology: 'Verde Tecnológico',
    purpleElegant: 'Morado Elegante',
    orangeGray: 'Naranja + Gris',
    displayMode: 'Modo de visualización',
    displayModeText: 'El sistema detecta el modo del equipo la primera vez y permite cambiarlo manualmente.',
    lightMode: 'Modo claro',
    darkMode: 'Modo oscuro',
    language: 'Idioma',
    languageText: 'El idioma inicial se detecta automáticamente desde el navegador.',
    spanish: 'Español',
    english: 'English',
    chartVisibility: 'Personalizar gráficas del Dashboard',
    showMonthSales: 'Mostrar “Ventas del mes”',
    showSalesPerMonth: 'Mostrar “Ventas por mes”',
    showTopProducts: 'Mostrar “Productos más vendidos”',
    systemDetected: 'Detección automática inicial',
    selected: 'Seleccionado',
    currentTheme: 'Tema actual',
  },
  en: {
    university: 'Mariano Gálvez University of Guatemala',
    welcome: 'Welcome',
    dashboard: 'Dashboard',
    analytics: 'Analytics',
    reports: 'Reports',
    settings: 'Settings',
    logout: 'Log out',
    monthSales: 'Month sales',
    salesPerMonth: 'Sales per month',
    topProducts: 'Top products',
    product: 'Product',
    sales: 'Sales',
    stock: 'Stock',
    status: 'Status',
    active: 'Active',
    analyticsTitle: 'Analytics',
    analyticsText: 'Analytics view ready to integrate system indicators and metrics.',
    reportsTitle: 'Reports',
    reportsText: 'Reports view ready to integrate exports and queries.',
    appearance: 'Appearance',
    appearanceText: 'Customize interface colors, display mode, and language.',
    themeColor: 'Interface color',
    chooseTheme: 'Choose one of the four palettes defined for the project.',
    blueProfessional: 'Professional Blue',
    greenTechnology: 'Technology Green',
    purpleElegant: 'Elegant Purple',
    orangeGray: 'Orange + Gray',
    displayMode: 'Display mode',
    displayModeText: 'The system detects the device mode the first time and lets you change it manually.',
    lightMode: 'Light mode',
    darkMode: 'Dark mode',
    language: 'Language',
    languageText: 'The initial language is automatically detected from the browser.',
    spanish: 'Español',
    english: 'English',
    chartVisibility: 'Customize Dashboard charts',
    showMonthSales: 'Show “Month sales”',
    showSalesPerMonth: 'Show “Sales per month”',
    showTopProducts: 'Show “Top products”',
    systemDetected: 'Initial automatic detection',
    selected: 'Selected',
    currentTheme: 'Current theme',
  },
};

const readStorage = (key) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const writeStorage = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // La interfaz sigue funcionando aunque el navegador bloquee el almacenamiento local.
  }
};

const detectLanguage = () => {
  const saved = readStorage('umg-language');
  if (saved === 'es' || saved === 'en') return saved;
  return navigator.language?.toLowerCase().startsWith('es') ? 'es' : 'en';
};

const detectDarkMode = () => {
  const saved = readStorage('umg-dark-mode');
  if (saved === 'true') return true;
  if (saved === 'false') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
};

const detectTheme = () => {
  const saved = readStorage('umg-color-theme');
  return THEMES[saved] ? saved : 'blue';
};

export const DashboardProvider = ({ children }) => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [themeId, setThemeId] = useState(detectTheme);
  const [isDarkMode, setIsDarkMode] = useState(detectDarkMode);
  const [language, setLanguage] = useState(detectLanguage);
  const [visibleCharts, setVisibleCharts] = useState({
    monthSales: true,
    salesPerMonth: true,
    topProducts: true,
  });

  const theme = THEMES[themeId];
  const t = translations[language];

  const colors = useMemo(() => ({
    page: isDarkMode ? theme.darkBackground : '#EEF2F5',
    panel: isDarkMode ? theme.darkPanel : '#FFFFFF',
    card: isDarkMode ? theme.darkCard : '#FFFFFF',
    cardSoft: isDarkMode ? theme.darkCard : '#F8FAFC',
    text: isDarkMode ? '#F8FAFC' : '#172033',
    muted: isDarkMode ? '#AEBBC9' : '#637083',
    border: isDarkMode ? 'rgba(255,255,255,0.09)' : '#E1E7EE',
    grid: isDarkMode ? '#526174' : '#A4AFBC',
    accentSoft: isDarkMode ? `${theme.primary}24` : theme.soft,
    sidebar: isDarkMode ? theme.sidebarDark : theme.sidebarLight,
  }), [isDarkMode, theme]);

  useEffect(() => {
    document.documentElement.style.colorScheme = isDarkMode ? 'dark' : 'light';
    document.documentElement.dataset.theme = isDarkMode ? 'dark' : 'light';
    writeStorage('umg-dark-mode', String(isDarkMode));
  }, [isDarkMode]);

  useEffect(() => {
    writeStorage('umg-language', language);
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    writeStorage('umg-color-theme', themeId);
  }, [themeId]);

  const toggleChart = (chartName) => {
    setVisibleCharts((prev) => ({ ...prev, [chartName]: !prev[chartName] }));
  };

  return (
    <DashboardContext.Provider
      value={{
        activeTab,
        setActiveTab,
        theme,
        themeId,
        setThemeId,
        themes: THEMES,
        colors,
        isDarkMode,
        setIsDarkMode,
        language,
        setLanguage,
        t,
        visibleCharts,
        toggleChart,
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
};
