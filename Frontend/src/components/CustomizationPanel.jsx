import { useContext } from 'react';
import { Check, Moon, Move, Palette, Sun, X } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';

export const CustomizationPanel = () => {
  const { customizationOpen, setCustomizationOpen, editMode, setEditMode, theme, themeId, themes, setThemeId, colors, isDarkMode, setIsDarkMode, language } = useContext(DashboardContext);
  if (!customizationOpen) return null;

  return <div className="fixed inset-0 z-[90] bg-black/30 backdrop-blur-[2px]" onMouseDown={(e)=>e.target===e.currentTarget&&setCustomizationOpen(false)}>
    <aside className="absolute right-0 top-0 h-full w-full max-w-[390px] overflow-y-auto border-l p-6 shadow-2xl" style={{backgroundColor:colors.panel,borderColor:colors.border}}>
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs font-extrabold uppercase tracking-[0.18em]" style={{color:theme.primary}}>{language==='es'?'Personalización':'Customization'}</p><h2 className="mt-1 text-2xl font-extrabold" style={{color:colors.text}}>{language==='es'?'Hazlo a tu manera':'Make it yours'}</h2><p className="mt-1 text-sm" style={{color:colors.muted}}>{language==='es'?'Apariencia y distribución del espacio de trabajo.':'Appearance and workspace layout.'}</p></div>
        <button onClick={()=>setCustomizationOpen(false)} className="rounded-xl border p-2 transition hover:scale-105" style={{borderColor:colors.border,color:colors.text}}><X size={19}/></button>
      </div>

      <section className="mt-7 rounded-2xl border p-4" style={{backgroundColor:colors.card,borderColor:colors.border}}>
        <div className="flex items-center gap-3"><div className="rounded-xl p-2" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><Move size={19}/></div><div><h3 className="font-extrabold" style={{color:colors.text}}>{language==='es'?'Modo edición':'Edit mode'}</h3><p className="text-xs" style={{color:colors.muted}}>{language==='es'?'Prepara el dashboard para mover y organizar elementos.':'Prepare the dashboard to move and organize items.'}</p></div></div>
        <button onClick={()=>setEditMode(!editMode)} className="mt-4 w-full rounded-xl border px-4 py-3 font-bold transition hover:scale-[1.02]" style={{backgroundColor:editMode?theme.primary:colors.cardSoft,borderColor:editMode?theme.primary:colors.border,color:editMode?'#fff':colors.text}}>{editMode?(language==='es'?'Salir del modo edición':'Exit edit mode'):(language==='es'?'Activar modo edición':'Enable edit mode')}</button>
      </section>

      <section className="mt-4 rounded-2xl border p-4" style={{backgroundColor:colors.card,borderColor:colors.border}}>
        <div className="mb-4 flex items-center gap-3"><Palette size={19} style={{color:theme.primary}}/><div><h3 className="font-extrabold" style={{color:colors.text}}>{language==='es'?'Color principal':'Primary color'}</h3><p className="text-xs" style={{color:colors.muted}}>{language==='es'?'Elige la identidad visual de la interfaz.':'Choose the visual identity of the interface.'}</p></div></div>
        <div className="grid grid-cols-2 gap-3">{Object.values(themes).map((palette)=><button key={palette.id} onClick={()=>setThemeId(palette.id)} className="flex items-center gap-3 rounded-xl border p-3 text-left transition hover:scale-[1.02]" style={{borderColor:themeId===palette.id?palette.primary:colors.border,backgroundColor:themeId===palette.id?colors.accentSoft:colors.cardSoft,color:colors.text}}><span className="relative h-8 w-8 shrink-0 rounded-full" style={{backgroundColor:palette.primary}}>{themeId===palette.id&&<Check className="absolute inset-0 m-auto h-4 w-4 text-white" strokeWidth={3}/>}</span><span className="text-sm font-bold">{palette.id==='blue'?(language==='es'?'Azul':'Blue'):palette.id==='green'?(language==='es'?'Verde':'Green'):palette.id==='purple'?(language==='es'?'Morado':'Purple'):(language==='es'?'Naranja':'Orange')}</span></button>)}</div>
      </section>

      <section className="mt-4 rounded-2xl border p-4" style={{backgroundColor:colors.card,borderColor:colors.border}}>
        <h3 className="font-extrabold" style={{color:colors.text}}>{language==='es'?'Tema':'Theme'}</h3><p className="mt-1 text-xs" style={{color:colors.muted}}>{language==='es'?'Cambia entre apariencia clara y oscura.':'Switch between light and dark appearance.'}</p>
        <div className="mt-4 grid grid-cols-2 gap-3"><button onClick={()=>setIsDarkMode(false)} className="flex items-center justify-center gap-2 rounded-xl border py-3 font-bold transition hover:scale-[1.02]" style={{borderColor:!isDarkMode?theme.primary:colors.border,backgroundColor:!isDarkMode?colors.accentSoft:colors.cardSoft,color:!isDarkMode?theme.primary:colors.text}}><Sun size={18}/>{language==='es'?'Claro':'Light'}</button><button onClick={()=>setIsDarkMode(true)} className="flex items-center justify-center gap-2 rounded-xl border py-3 font-bold transition hover:scale-[1.02]" style={{borderColor:isDarkMode?theme.primary:colors.border,backgroundColor:isDarkMode?colors.accentSoft:colors.cardSoft,color:isDarkMode?theme.primary:colors.text}}><Moon size={18}/>{language==='es'?'Oscuro':'Dark'}</button></div>
      </section>
    </aside>
  </div>;
};
