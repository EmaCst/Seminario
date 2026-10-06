import { useContext, useEffect, useState } from 'react';
import { Expand, GripVertical, Minimize2 } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';

const readJson = (key, fallback) => {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch { return fallback; }
};

export const EditableDashboardGrid = ({ storageId, items, columns = 'xl:grid-cols-2' }) => {
  const { editMode, colors, theme, language } = useContext(DashboardContext);
  const orderKey = `kenneth-dashboard-order-${storageId}`;
  const sizeKey = `kenneth-dashboard-size-${storageId}`;
  const [order, setOrder] = useState(()=>readJson(orderKey, []));
  const [sizes, setSizes] = useState(()=>readJson(sizeKey, {}));
  const [dragging, setDragging] = useState(null);

  useEffect(()=>{ try { localStorage.setItem(orderKey, JSON.stringify(order)); } catch { /* optional */ } },[order,orderKey]);
  useEffect(()=>{ try { localStorage.setItem(sizeKey, JSON.stringify(sizes)); } catch { /* optional */ } },[sizes,sizeKey]);

  const rank = new Map(order.map((id,index)=>[id,index]));
  const sorted = [...items].sort((a,b)=>(rank.get(a.id) ?? items.findIndex(x=>x.id===a.id))-(rank.get(b.id) ?? items.findIndex(x=>x.id===b.id)));

  const drop = (target) => {
    if (!dragging || dragging===target) return;
    const ids=sorted.map(x=>x.id);
    const from=ids.indexOf(dragging), to=ids.indexOf(target);
    const [moved]=ids.splice(from,1); ids.splice(to,0,moved);
    setOrder(ids); setDragging(null);
  };

  return <div className={`grid grid-cols-1 gap-5 ${columns}`}>{sorted.map(item=>{
    const large=sizes[item.id]==='large';
    return <div key={item.id} draggable={editMode} onDragStart={()=>setDragging(item.id)} onDragOver={(e)=>editMode&&e.preventDefault()} onDrop={()=>drop(item.id)} onDragEnd={()=>setDragging(null)} className={`${large?'xl:col-span-2':''} ${dragging===item.id?'opacity-50 scale-[0.99]':''} transition`}>
      {editMode&&<div className="mb-2 flex items-center justify-between rounded-xl border px-3 py-2 text-xs font-bold" style={{backgroundColor:colors.accentSoft,borderColor:theme.primary+'44',color:theme.primary}}><span className="flex items-center gap-2 cursor-grab"><GripVertical size={15}/>{language==='es'?'Mover':'Move'}</span><button type="button" onClick={()=>setSizes(prev=>({...prev,[item.id]:large?'normal':'large'}))} className="flex items-center gap-1.5 rounded-lg px-2 py-1 transition hover:scale-105" style={{backgroundColor:colors.card}}>{large?<Minimize2 size={14}/>:<Expand size={14}/>} {large?(language==='es'?'Normal':'Normal'):(language==='es'?'Grande':'Large')}</button></div>}
      {item.node}
    </div>;
  })}</div>;
};
