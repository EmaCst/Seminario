import { useContext, useEffect, useMemo, useState } from 'react';
import { Expand, GripVertical, Minimize2 } from 'lucide-react';
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
    const sharedSpan=item.resizable===false ? 'xl:col-span-12' : (large?'xl:col-span-12':'xl:col-span-6');
    return <div key={item.id} style={sharedCanvas?{order:rank.get(item.id) ?? 999}:undefined} draggable={editMode} onDragStart={()=>startDrag(item.id)} onDragOver={(e)=>editMode&&e.preventDefault()} onDrop={()=>drop(item.id)} onDragEnd={()=>{setDragging(null);if(sharedCanvas)window.dispatchEvent(new CustomEvent('kenneth-canvas-sync',{detail:{canvas:canvasId,dragging:null}}));}} className={`${sharedCanvas?sharedSpan:(large?'xl:col-span-2':'')} ${dragging===item.id?'opacity-50 scale-[0.99]':''} transition`}>
      {editMode&&<div className="mb-2 flex items-center justify-between rounded-xl border px-3 py-2 text-xs font-bold" style={{backgroundColor:colors.accentSoft,borderColor:theme.primary+'44',color:theme.primary}}><span className="flex items-center gap-2 cursor-grab"><GripVertical size={15}/>{language==='es'?'Mover':'Move'}</span>{item.resizable !== false && <button type="button" onClick={()=>setSizes(prev=>({...prev,[item.id]:large?'normal':'large'}))} className="flex items-center gap-1.5 rounded-lg px-2 py-1 transition hover:scale-105" style={{backgroundColor:colors.card}}>{large?<Minimize2 size={14}/>:<Expand size={14}/>} {large?(language==='es'?'Normal':'Normal'):(language==='es'?'Grande':'Large')}</button>}</div>}
      {item.node}
    </div>;
  })}</div>;
};
