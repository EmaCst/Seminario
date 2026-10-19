import { useContext, useEffect, useState } from 'react';
import { Copy, Pencil, Plus, Pin, PinOff, Trash2 } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { deleteSavedVisualization, getSavedVisualizations, updateVisualizationPlacement } from '../services/api';
import { VisualizationBuilder } from './VisualizationBuilder';

export const VisualizationLibrary = () => {
  const { colors, theme, language } = useContext(DashboardContext);
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState('edit');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
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
  const notifyChanged = () => window.dispatchEvent(new Event('kenneth-custom-visualizations-changed'));
  const togglePlacement = async (item, destination) => {
    setBusyId(item.id); setError('');
    try {
      await updateVisualizationPlacement(item.id, { ...item.placement, [destination]: !item.placement?.[destination] });
      await refresh(); notifyChanged();
    } catch (err) { setError(err.message); }
    finally { setBusyId(null); }
  };
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id); setError('');
    try {
      await deleteSavedVisualization(deleteTarget.id);
      setDeleteTarget(null);
      await refresh(); notifyChanged();
    } catch (err) { setError(err.message); }
    finally { setBusyId(null); }
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
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={()=>launch(item,'edit')} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:colors.border,color:theme.primary}}><Pencil size={15}/>{language==='es'?'Editar':'Edit'}</button>
          <button type="button" onClick={()=>launch(item,'duplicate')} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:colors.border,color:theme.primary}}><Copy size={15}/>{language==='es'?'Duplicar':'Duplicate'}</button>
          {['dashboard','analytics'].map(destination => {
            const pinned = Boolean(item.placement?.[destination]);
            const name = destination === 'dashboard' ? 'Dashboard' : (language === 'es' ? 'Analítica' : 'Analytics');
            return <button key={destination} type="button" disabled={busyId===item.id} onClick={()=>togglePlacement(item,destination)} title={pinned ? (language==='es'?'Desanclar de ':'Unpin from ')+name : (language==='es'?'Anclar a ':'Pin to ')+name} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-50" style={{borderColor:colors.border,color:pinned?theme.primary:colors.muted}}>{pinned?<PinOff size={15}/>:<Pin size={15}/>} {pinned?(language==='es'?'Quitar de ':'Remove from '):(language==='es'?'Anclar a ':'Pin to ')}{name}</button>;
          })}
          <button type="button" disabled={busyId===item.id} onClick={()=>setDeleteTarget(item)} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold text-red-600 disabled:opacity-50" style={{borderColor:colors.border}}><Trash2 size={15}/>{language==='es'?'Eliminar':'Delete'}</button>
        </div>
      </article>)}
    </div>
    {deleteTarget&&<div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 p-4" role="presentation">
      <div role="dialog" aria-modal="true" aria-labelledby="delete-visualization-title" className="w-full max-w-md rounded-2xl border p-6 shadow-2xl" style={{backgroundColor:colors.panel,borderColor:colors.border}}>
        <h3 id="delete-visualization-title" className="text-xl font-extrabold" style={{color:colors.text}}>{language==='es'?'¿Eliminar visualización?':'Delete visualization?'}</h3>
        <p className="mt-3 text-sm" style={{color:colors.muted}}>{language==='es'?'Se eliminará definitivamente':'This will permanently delete'} <strong style={{color:colors.text}}>{deleteTarget.definition?.title}</strong>. {language==='es'?'También desaparecerá de Dashboard y Analítica.':'It will also disappear from Dashboard and Analytics.'}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" disabled={Boolean(busyId)} onClick={()=>setDeleteTarget(null)} className="rounded-xl border px-4 py-2 text-sm font-semibold" style={{borderColor:colors.border,color:colors.text}}>{language==='es'?'Cancelar':'Cancel'}</button>
          <button type="button" disabled={Boolean(busyId)} onClick={confirmDelete} className="rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{busyId?(language==='es'?'Eliminando...':'Deleting...'):(language==='es'?'Sí, eliminar':'Yes, delete')}</button>
        </div>
      </div>
    </div>}
    {open&&<VisualizationBuilder open={open} initialItem={selected} mode={mode} onClose={()=>setOpen(false)} onSaved={saved}/>}
  </section>;
};
