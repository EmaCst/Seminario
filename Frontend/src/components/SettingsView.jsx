import { useContext, useState } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { Check, Moon, Sun, Languages, Palette, ChartNoAxesCombined, Database, Server, FileSpreadsheet } from 'lucide-react';
import { DatabaseConfig } from './DatabaseConfig';
import { DatabaseUpload } from './DatabaseUpload';
import { PostgreSQLConfig } from './PostgreSQLConfig';
import { ExcelImport } from './ExcelImport';

const DataSourceSwitcher = ({ source, setSource, theme, colors, language }) => {
  const options = [
    { id:'sqlserver', label:'SQL Server', icon:Database },
    { id:'postgresql', label:'PostgreSQL', icon:Server },
    { id:'excel', label:'Excel', icon:FileSpreadsheet },
  ];
  return <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{backgroundColor:colors.card,borderColor:colors.border}}>
    <div className="flex items-start gap-3 mb-5"><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><Database size={20}/></div><div><h3 className="text-lg font-bold" style={{color:colors.text}}>{language==='es'?'Fuente de datos':'Data source'}</h3><p className="text-sm" style={{color:colors.muted}}>{language==='es'?'Selecciona el origen que deseas conectar o cargar en Kenneth.':'Choose the source you want to connect or upload to Kenneth.'}</p></div></div>
    <div className="grid grid-cols-1 sm:grid-cols-3 overflow-hidden rounded-xl border" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>{options.map((o,i)=>{const selected=source===o.id;const Icon=o.icon;return <button key={o.id} type="button" onClick={()=>setSource(o.id)} className="relative px-4 py-4 sm:py-3.5 transition-all text-left sm:text-center flex sm:flex-col items-center justify-between sm:justify-center gap-2" style={{backgroundColor:selected?theme.primary:'transparent',color:selected?'#fff':colors.text,borderLeft:i>0?`1px solid ${colors.border}`:undefined}}><div className="flex items-center gap-2 font-bold"><Icon size={18}/><span>{o.label}</span></div><span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{backgroundColor:selected?'rgba(255,255,255,.16)':colors.accentSoft,color:selected?'#fff':theme.primary}}>{language==='es'?'Disponible':'Available'}</span>{selected&&<span className="hidden sm:block absolute -bottom-2 left-1/2 -translate-x-1/2 rotate-45 w-4 h-4" style={{backgroundColor:theme.primary}}/>}</button>})}</div>
  </section>;
};

export const SettingsView = () => {
  const { theme,themeId,themes,setThemeId,colors,visibleCharts,toggleChart,isDarkMode,setIsDarkMode,language,setLanguage,t }=useContext(DashboardContext);
  const [dataSource,setDataSource]=useState('sqlserver');
  const cardStyle={backgroundColor:colors.card,borderColor:colors.border};
  const settings=[{key:'monthSales',label:t.showMonthSales},{key:'salesPerMonth',label:t.showSalesPerMonth},{key:'topProducts',label:t.showTopProducts}];
  return <div className="space-y-6 max-w-5xl">
    <div><h2 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{color:theme.primary}}>{t.settings}</h2><p className="mt-2" style={{color:colors.muted}}>{t.appearanceText}</p></div>
    <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}><div className="flex items-start gap-3 mb-5"><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><Palette size={20}/></div><div><h3 className="text-lg font-bold" style={{color:colors.text}}>{t.themeColor}</h3><p className="text-sm" style={{color:colors.muted}}>{t.chooseTheme}</p></div></div><div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">{Object.values(themes).map(p=>{const selected=p.id===themeId;return <button key={p.id} onClick={()=>setThemeId(p.id)} className="rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md" style={{borderColor:selected?p.primary:colors.border,backgroundColor:colors.cardSoft}}><div className="flex items-center justify-between gap-2 mb-4"><span className="w-11 h-11 rounded-xl shadow-sm" style={{backgroundColor:p.primary}}/>{selected&&<span className="w-7 h-7 rounded-full flex items-center justify-center text-white" style={{backgroundColor:p.primary}}><Check size={16}/></span>}</div><div className="font-bold" style={{color:colors.text}}>{t[p.nameKey]}</div></button>})}</div></section>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}><div className="flex items-start gap-3 mb-5"><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}>{isDarkMode?<Moon size={20}/>:<Sun size={20}/>}</div><div><h3 className="text-lg font-bold" style={{color:colors.text}}>{t.displayMode}</h3><p className="text-sm" style={{color:colors.muted}}>{t.displayModeText}</p></div></div><div className="grid grid-cols-2 gap-3">{[[false,Sun,t.lightMode],[true,Moon,t.darkMode]].map(([dark,Icon,label])=><button key={String(dark)} onClick={()=>setIsDarkMode(dark)} className="rounded-xl border p-4 flex items-center justify-center gap-2 font-bold" style={isDarkMode===dark?{backgroundColor:theme.primary,color:'#fff',borderColor:theme.primary}:{color:colors.text,borderColor:colors.border,backgroundColor:colors.cardSoft}}><Icon size={18}/>{label}</button>)}</div></section>
      <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}><div className="flex items-start gap-3 mb-5"><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><Languages size={20}/></div><div><h3 className="text-lg font-bold" style={{color:colors.text}}>{t.language}</h3><p className="text-sm" style={{color:colors.muted}}>{t.languageText}</p></div></div><div className="grid grid-cols-2 gap-3">{[['es',t.spanish],['en',t.english]].map(([id,label])=><button key={id} onClick={()=>setLanguage(id)} className="rounded-xl border p-4 font-bold" style={language===id?{backgroundColor:theme.primary,color:'#fff',borderColor:theme.primary}:{color:colors.text,borderColor:colors.border,backgroundColor:colors.cardSoft}}>{label}</button>)}</div></section>
    </div>
    <DataSourceSwitcher source={dataSource} setSource={setDataSource} theme={theme} colors={colors} language={language}/>
    {dataSource==='sqlserver'&&<><DatabaseUpload/><DatabaseConfig/></>}
    {dataSource==='postgresql'&&<PostgreSQLConfig/>}
    {dataSource==='excel'&&<ExcelImport theme={theme} colors={colors} language={language}/>} 
    <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={cardStyle}><div className="flex items-start gap-3 mb-5"><div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><ChartNoAxesCombined size={20}/></div><h3 className="text-lg font-bold" style={{color:colors.text}}>{t.chartVisibility}</h3></div><div className="space-y-3">{settings.map(item=><label key={item.key} className="flex items-center justify-between gap-4 rounded-xl border px-4 py-3 cursor-pointer" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}><span className="font-medium" style={{color:colors.text}}>{item.label}</span><input type="checkbox" checked={visibleCharts[item.key]} onChange={()=>toggleChart(item.key)} className="w-5 h-5" style={{accentColor:theme.primary}}/></label>)}</div></section>
  </div>;
};
