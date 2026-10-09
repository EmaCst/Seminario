import { useContext, useEffect, useState } from 'react';
import { Copy, Pencil, Plus } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { getSavedVisualizations } from '../services/api';
import { VisualizationBuilder } from './VisualizationBuilder';

export const VisualizationLibrary = () => {
  const { colors, theme, language } = useContext(DashboardContext);
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState('edit');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const refresh = () => getSavedVisualizations().then(result => { setItems(result.items || []); setError(''); }).catch(err => setError(err.message));
  useEffect(() => {
    refresh();
    window.addEventListener('kenneth-custom-visualizations-changed', refresh);
    return () => window.removeEventListener('kenneth-custom-visualizations-changed', refresh);
  }, []);
  const launch = (item, nextMode) => { setSelected(item); setMode(nextMode); setOpen(true); };
  const saved = () => {
    setOpen(false); refresh();
    window.dispatchEvent(new Event('kenneth-custom-visualizations-changed'));
  };
  return <section className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-2xl font-extrabold" style={{color:colors.text}}>{language==='es'?'Mis visualizaciones':'My visualizations'}</h2><p className="text-sm" style={{color:colors.muted}}>{language==='es'?'Biblioteca de visualizaciones de la fuente activa.':'Visualizations saved for the active data source.'}</p></div>
      <button type="button" onClick={()=>launch(null,'create')} className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold text-white transition hover:opacity-90" style={{backgroundColor:theme.primary}}><Plus size={18}/>{language==='es'?'Nueva visualización':'New visualization'}</button>
    </div>
    {error&&<p className="text-red-500">{error}</p>}
    {!items.length&&!error&&<p style={{color:colors.muted}}>{language==='es'?'Todavía no hay visualizaciones guardadas.':'No saved visualizations yet.'}</p>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {items.map(item=><article key={item.id} className="rounded-2xl border p-4 shadow-sm" style={{backgroundColor:colors.card,borderColor:colors.border}}>
        <h3 className="font-bold" style={{color:colors.text}}>{item.definition?.title}</h3>
        <p className="mt-1 text-xs" style={{color:colors.muted}}>{item.definition?.visualization?.toUpperCase()} · {item.definition?.table}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs" style={{color:colors.muted}}>
          {item.placement?.dashboard&&<span className="rounded-lg border px-2 py-1" style={{borderColor:colors.border}}>Dashboard</span>}
          {item.placement?.analytics&&<span className="rounded-lg border px-2 py-1" style={{borderColor:colors.border}}>{language==='es'?'Analítica':'Analytics'}</span>}
          {!item.placement?.dashboard&&!item.placement?.analytics&&<span>{language==='es'?'Sin anclar':'Unpinned'}</span>}
        </div>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={()=>launch(item,'edit')} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:colors.border,color:theme.primary}}><Pencil size={15}/>{language==='es'?'Editar':'Edit'}</button>
          <button type="button" onClick={()=>launch(item,'duplicate')} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:colors.border,color:theme.primary}}><Copy size={15}/>{language==='es'?'Duplicar':'Duplicate'}</button>
        </div>
      </article>)}
    </div>
    {open&&<VisualizationBuilder open={open} initialItem={selected} mode={mode} onClose={()=>setOpen(false)} onSaved={saved}/>}
  </section>;
};
