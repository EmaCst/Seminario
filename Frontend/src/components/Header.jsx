import { useContext } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';

export const Header = () => {
  const { theme, colors, t, language, setLanguage, setCustomizationOpen, editMode } = useContext(DashboardContext);
  return <header className="px-5 sm:px-6 lg:px-8 py-5 flex flex-col xl:flex-row xl:items-center justify-between gap-4 border-b transition-colors duration-300" style={{borderColor:colors.border,backgroundColor:colors.panel}}>
    <div className="min-w-0"><h1 className="text-lg sm:text-xl lg:text-2xl font-extrabold tracking-tight truncate" style={{color:theme.primary}}>{t.university}</h1><p className="text-xs sm:text-sm mt-1" style={{color:colors.muted}}>{t.welcome}: David Emanuel Castellanos Velásquez</p></div>
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      <button onClick={()=>setCustomizationOpen(true)} className="h-10 px-4 rounded-full border flex items-center gap-2 font-bold text-xs sm:text-sm transition-all hover:scale-[1.03]" style={{backgroundColor:editMode?colors.accentSoft:colors.cardSoft,borderColor:editMode?theme.primary:colors.border,color:editMode?theme.primary:colors.text}}><SlidersHorizontal className="w-4 h-4" style={{color:theme.primary}}/><span>{language==='es'?'Personalizar':'Customize'}</span>{editMode&&<span className="h-2 w-2 rounded-full" style={{backgroundColor:theme.primary}}/>}</button>
      <div className="flex p-1 rounded-full border text-xs font-bold" style={{backgroundColor:colors.cardSoft,borderColor:colors.border}}>{['es','en'].map(code=>{const active=language===code;return <button key={code} onClick={()=>setLanguage(code)} className="px-3 py-1.5 rounded-full transition-all hover:scale-105" style={active?{backgroundColor:theme.primary,color:'#fff'}:{color:colors.muted}} aria-pressed={active}>{code.toUpperCase()}</button>})}</div>
    </div>
  </header>;
};
