import { useContext, useEffect, useMemo, useState } from 'react';
import { Expand, GripVertical, Minimize2, X } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';

const readJson = (key, fallback) => {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch { return fallback; }
};

export const EditableDashboardGrid = ({ storageId, items, columns = 'xl:grid-cols-2', sharedCanvas = null }) => {
  const { editMode, colors, theme, language } = useContext(DashboardContext);
  const canvasId = sharedCanvas || storageId;
  const orderKey = `kenneth-dashboard-order-${canvasId}`;
  const sizeKey = `kenneth-dashboard-size-${canvasId}`;
  const registryKey = `kenneth-dashboard-registry-${canvasId}`;
  const [order, setOrder] = useState(()=>readJson(orderKey, []));
  const [sizes, setSizes] = useState(()=>readJson(sizeKey, {}));
  const [dragging, setDragging] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  useEffect(() => {
    if (!expandedId) return;
    const onKeyDown = (event) => { if (event.key === 'Escape') setExpandedId(null); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [expandedId]);

  useEffect(()=>{
    const existing=readJson(registryKey, []);
    const next=[...existing];
    items.forEach((item)=>{ if(!next.includes(item.id)) next.push(item.id); });
    try { localStorage.setItem(registryKey, JSON.stringify(next)); } catch { /* optional */ }
  },[items,registryKey]);

  useEffect(()=>{ try { localStorage.setItem(orderKey, JSON.stringify(order)); } catch { /* optional */ } },[order,orderKey]);
  useEffect(()=>{ try { localStorage.setItem(sizeKey, JSON.stringify(sizes)); } catch { /* optional */ } },[sizes,sizeKey]);

  useEffect(()=>{
    const sync=(event)=>{
      if(event.detail?.canvas!==canvasId) return;
      if(event.detail.order) setOrder(event.detail.order);
      setDragging(event.detail.dragging ?? null);
    };
    const reset=()=>{ setOrder([]); setSizes({}); setDragging(null); try { localStorage.removeItem(registryKey); } catch { /* optional */ } };
    window.addEventListener('kenneth-canvas-sync', sync);
    window.addEventListener('kenneth-layout-reset', reset);
    return ()=>{ window.removeEventListener('kenneth-canvas-sync', sync); window.removeEventListener('kenneth-layout-reset', reset); };
  },[canvasId,registryKey]);

  const effectiveOrder = useMemo(()=>{
    const registry=readJson(registryKey, []);
    const base=order.length ? order : registry;
    return [...base, ...registry.filter((id)=>!base.includes(id))];
  },[order,items,registryKey]);

  const rank = new Map(effectiveOrder.map((id,index)=>[id,index]));
  const sorted = sharedCanvas ? items : [...items].sort((a,b)=>(rank.get(a.id) ?? items.findIndex(x=>x.id===a.id))-(rank.get(b.id) ?? items.findIndex(x=>x.id===b.id)));

  const startDrag=(id)=>{
    setDragging(id);
    if(sharedCanvas) window.dispatchEvent(new CustomEvent('kenneth-canvas-sync',{detail:{canvas:canvasId,dragging:id}}));
  };

  const drop = (target) => {
    if (!dragging || dragging===target) return;
    const ids=sharedCanvas ? [...effectiveOrder] : sorted.map(x=>x.id);
    const from=ids.indexOf(dragging), to=ids.indexOf(target);
    if(from<0||to<0) return;
    const [moved]=ids.splice(from,1); ids.splice(to,0,moved);
    setOrder(ids); setDragging(null);
    if(sharedCanvas) window.dispatchEvent(new CustomEvent('kenneth-canvas-sync',{detail:{canvas:canvasId,order:ids,dragging:null}}));
  };

  return <div className={sharedCanvas ? 'contents' : `grid grid-cols-1 gap-5 ${columns}`}>{sorted.map(item=>{
    const large=item.resizable !== false && sizes[item.id]==='large';
    const sharedSpan=item.resizable===false ? (item.span || 'xl:col-span-12') : (large?'xl:col-span-12':(item.span || 'xl:col-span-6'));
    return <div key={item.id} style={sharedCanvas?{order:rank.get(item.id) ?? 999}:undefined} draggable={editMode} onDragStart={()=>startDrag(item.id)} onDragOver={(e)=>editMode&&e.preventDefault()} onDrop={()=>drop(item.id)} onDragEnd={()=>{setDragging(null);if(sharedCanvas)window.dispatchEvent(new CustomEvent('kenneth-canvas-sync',{detail:{canvas:canvasId,dragging:null}}));}} className={`${sharedCanvas?sharedSpan:(large?'xl:col-span-2':'')} ${dragging===item.id?'opacity-50 scale-[0.99]':''} transition`}>
      {editMode&&<div className="mb-2 flex items-center justify-between rounded-xl border px-3 py-2 text-xs font-bold" style={{backgroundColor:colors.accentSoft,borderColor:theme.primary+'44',color:theme.primary}}><span className="flex items-center gap-2 cursor-grab"><GripVertical size={15}/>{language==='es'?'Mover':'Move'}</span>{item.resizable !== false && <button type="button" onClick={()=>setSizes(prev=>({...prev,[item.id]:large?'normal':'large'}))} className="flex items-center gap-1.5 rounded-lg px-2 py-1 transition hover:scale-105" style={{backgroundColor:colors.card}}>{large?<Minimize2 size={14}/>:<Expand size={14}/>} {large?(language==='es'?'Normal':'Normal'):(language==='es'?'Grande':'Large')}</button>}</div>}
      <div className={item.expandable === false ? '' : 'transition-transform duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.005]'} onClick={(event)=>{if(item.expandable === false || editMode || event.target.closest('button, a, input, select, textarea, [role="button"]')) return; setExpandedId(item.id);}}>
        {item.node}
      </div>
    </div>;
  })}
    {expandedId && sorted.some(item=>item.id===expandedId) && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-3 md:p-8" onMouseDown={(event)=>{if(event.target===event.currentTarget)setExpandedId(null);}} role="presentation">
      <div role="dialog" aria-modal="true" aria-label={language==='es'?'Visualización ampliada':'Expanded visualization'} className="flex h-[min(86vh,850px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border shadow-2xl" style={{backgroundColor:colors.card,borderColor:colors.border}}>
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-3" style={{borderColor:colors.border,color:colors.text}}><span className="font-bold">{language==='es'?'Vista ampliada':'Expanded view'}</span><button type="button" autoFocus onClick={()=>setExpandedId(null)} aria-label={language==='es'?'Cerrar':'Close'} className="rounded-lg p-2 hover:opacity-70"><X size={22}/></button></div>
        <div className="kenneth-expanded-chart min-h-0 flex-1 overflow-auto p-4 md:p-6 [&_.recharts-responsive-container]:!h-[min(55vh,500px)] [&_.h-48]:!h-[min(55vh,500px)]">{sorted.find(item=>item.id===expandedId)?.node}</div>
      </div>
    </div>}
  </div>;
};
