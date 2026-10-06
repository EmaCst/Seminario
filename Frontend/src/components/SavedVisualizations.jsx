import { useContext, useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Expand, GripVertical, LayoutDashboard, Minimize2, RefreshCw } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { getSavedVisualizations, previewVisualization } from '../services/api';

const formatValue = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

export const CustomVisualizationWidget = ({ item, draggable, dragging, large, onToggleSize, onDragStart, onDragOver, onDrop, onDragEnd }) => {
  const { colors, theme, language } = useContext(DashboardContext);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    previewVisualization(item.definition).then((result) => active && setPreview(result)).catch((err) => active && setError(err.message));
    return () => { active = false; };
  }, [item]);

  const data = preview?.data || [];
  const type = item.definition.visualization;
  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border };

  return <section draggable={draggable} onDragStart={onDragStart} onDragOver={onDragOver} onDrop={onDrop} onDragEnd={onDragEnd} className={`min-h-[250px] rounded-2xl border p-5 shadow-sm transition ${draggable ? 'cursor-grab active:cursor-grabbing' : 'hover:-translate-y-0.5 hover:shadow-md'} ${dragging ? 'scale-[0.98] opacity-50' : ''}`} style={{...cardStyle, outline: draggable ? `1px dashed ${theme.primary}55` : 'none'}}>
    {draggable && <div className="mb-3 flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-xs font-bold" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><span className="flex items-center gap-2"><GripVertical size={15}/>{language==='es'?'Mover':'Move'}</span><button type="button" onClick={(e)=>{e.stopPropagation();onToggleSize();}} className="flex items-center gap-1.5 rounded-lg px-2 py-1 transition hover:scale-105" style={{backgroundColor:colors.card,color:theme.primary}}>{large?<Minimize2 size={14}/>:<Expand size={14}/>} {large?(language==='es'?'Normal':'Normal'):(language==='es'?'Grande':'Large')}</button></div>}
    <div className="mb-4 flex items-start justify-between gap-3">
      <div><p className="text-[11px] font-bold uppercase tracking-wider" style={{color:theme.primary}}>{language==='es'?'Personalizada':'Custom'}</p><h3 className="font-extrabold" style={{color:colors.text}}>{item.definition.title}</h3></div>
      {item.placement?.dashboard && <LayoutDashboard size={17} style={{color:theme.primary}}/>}
    </div>
    {error ? <p className="text-sm text-red-500">{error}</p> : !preview ? <div className="flex h-44 items-center justify-center" style={{color:colors.muted}}><RefreshCw className="animate-spin" size={18}/></div> :
      type === 'kpi' ? <div className="flex h-40 items-center justify-center text-5xl font-black" style={{color:theme.primary}}>{formatValue(data[0]?.value)}</div> :
      type === 'table' ? <div className="max-h-48 overflow-auto"><table className="w-full text-sm"><tbody>{data.map((row,i)=><tr key={i} className="border-b" style={{borderColor:colors.border}}>{Object.values(row).map((v,j)=><td key={j} className="px-2 py-2" style={{color:colors.text}}>{String(v)}</td>)}</tr>)}</tbody></table></div> :
      <div className="h-48"><ResponsiveContainer width="100%" height="100%">{type === 'line' ? <LineChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension" tick={{fill:colors.muted,fontSize:11}}/><YAxis tick={{fill:colors.muted,fontSize:11}}/><Tooltip/><Line dataKey="value" stroke={theme.primary} strokeWidth={3}/></LineChart> : <BarChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension" tick={{fill:colors.muted,fontSize:11}}/><YAxis tick={{fill:colors.muted,fontSize:11}}/><Tooltip/><Bar dataKey="value" fill={theme.primary} radius={[6,6,0,0]}/></BarChart>}</ResponsiveContainer></div>}
  </section>;
};

export const SavedVisualizations = ({ destination, refreshKey = 0 }) => {
  const { colors, language, editMode, theme } = useContext(DashboardContext);
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [draggingId, setDraggingId] = useState(null);
  const storageKey = `kenneth-layout-${destination}`;
  const sizeKey = `kenneth-layout-sizes-${destination}`;
  const [sizes, setSizes] = useState(()=>{ try { return JSON.parse(localStorage.getItem(sizeKey) || '{}'); } catch { return {}; } });

  useEffect(() => {
    let active = true;
    getSavedVisualizations(destination).then((result)=>{
      if (!active) return;
      const incoming = result.items || [];
      let order = [];
      try { order = JSON.parse(localStorage.getItem(storageKey) || '[]'); } catch { order = []; }
      const rank = new Map(order.map((id, index) => [id, index]));
      setItems([...incoming].sort((a,b)=>(rank.get(a.id) ?? 9999) - (rank.get(b.id) ?? 9999)));
    }).catch((err)=>active&&setError(err.message));
    return ()=>{active=false};
  }, [destination, refreshKey]);

  const persistOrder = (next) => {
    setItems(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next.map((item)=>item.id))); } catch { /* localStorage opcional */ }
  };

  const toggleSize = (id) => {
    const next = { ...sizes, [id]: sizes[id] === 'large' ? 'normal' : 'large' };
    setSizes(next);
    try { localStorage.setItem(sizeKey, JSON.stringify(next)); } catch { /* localStorage opcional */ }
  };

  const dropOn = (targetId) => {
    if (!draggingId || draggingId === targetId) return;
    const next = [...items];
    const from = next.findIndex((item)=>item.id===draggingId);
    const to = next.findIndex((item)=>item.id===targetId);
    if (from < 0 || to < 0) return;
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    persistOrder(next);
    setDraggingId(null);
  };

  useEffect(()=>{
    const reset=()=>{
      setSizes({});
      try { localStorage.removeItem(storageKey); localStorage.removeItem(sizeKey); } catch { /* optional */ }
      setItems((current)=>[...current].sort((a,b)=>String(a.created_at||'').localeCompare(String(b.created_at||''))));
      setDraggingId(null);
    };
    window.addEventListener('kenneth-layout-reset', reset);
    return ()=>window.removeEventListener('kenneth-layout-reset', reset);
  },[storageKey,sizeKey]);

  if (error) return <div className="rounded-xl border p-3 text-sm text-red-500" style={{borderColor:colors.border}}>{error}</div>;
  if (!items.length) return null;

  return <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">{items.map(item=>{const large=sizes[item.id]==='large';return <div key={item.id} className={large?'xl:col-span-2':''}><CustomVisualizationWidget item={item} draggable={editMode} dragging={draggingId===item.id} large={large} onToggleSize={()=>toggleSize(item.id)} onDragStart={()=>setDraggingId(item.id)} onDragOver={(e)=>editMode&&e.preventDefault()} onDrop={()=>dropOn(item.id)} onDragEnd={()=>setDraggingId(null)}/></div>})}</div>;
};
