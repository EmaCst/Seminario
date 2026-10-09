import { useContext, useEffect, useMemo, useState } from 'react';
import { BarChart3, LineChart, Sigma, Table2, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Line, LineChart as ReLineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DashboardContext } from '../context/DashboardContext';
import { getVisualizationSemanticCatalog, getVisualizationFilterValues, previewVisualization, saveVisualization, updateSavedVisualization } from '../services/api';

const ICONS = { kpi: Sigma, bar: BarChart3, line: LineChart, donut: BarChart3, table: Table2 };

export const VisualizationBuilder = ({ open, onClose, onSaved, initialItem = null, mode = 'create' }) => {
  const { colors, theme, language } = useContext(DashboardContext);
  const [catalog, setCatalog] = useState(null);
  const [entityKey, setEntityKey] = useState('');
  const [metric, setMetric] = useState('');
  const [metricEntityKey, setMetricEntityKey] = useState('');
  const [dimensionEntityKey, setDimensionEntityKey] = useState('');
  const [aggregation, setAggregation] = useState('count');
  const [dimension, setDimension] = useState('');
  const [visualization, setVisualization] = useState('bar');
  const [title, setTitle] = useState('');
  const [filters, setFilters] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveToAnalytics, setSaveToAnalytics] = useState(true);
  const [saveToDashboard, setSaveToDashboard] = useState(false);

  useEffect(() => {
    if (!open) return;
    getVisualizationSemanticCatalog().then((data) => {
      setCatalog(data);
      if (data.entities?.[0]) setEntityKey(data.entities[0].key);
    }).catch((err) => setError(err.message));
  }, [open]);

  const entity = useMemo(() => catalog?.entities?.find((item) => item.key === entityKey), [catalog, entityKey]);
  const relatedEntities = useMemo(() => {
    if (!catalog || !entity) return [];
    const reachable = new Set([entity.table]);
    let changed = true;
    while (changed) {
      changed = false;
      (catalog.relationships || []).forEach((rel) => {
        if (reachable.has(rel.from_table) && !reachable.has(rel.to_table)) { reachable.add(rel.to_table); changed = true; }
        if (reachable.has(rel.to_table) && !reachable.has(rel.from_table)) { reachable.add(rel.from_table); changed = true; }
      });
    }
    return (catalog.entities || []).filter((item) => reachable.has(item.table));
  }, [catalog, entity]);
  const metricEntity = relatedEntities.find((item) => item.key === metricEntityKey) || entity;
  const dimensionEntity = relatedEntities.find((item) => item.key === dimensionEntityKey) || entity;
  const needsDimension = ['bar', 'line', 'donut'].includes(visualization);

  useEffect(() => {
    if (!open || !catalog) return;
    const def = initialItem?.definition;
    if (!def) return;
    const source = catalog.entities?.find(e => e.table === def.table);
    if (!source) return;
    setEntityKey(source.key);
    setMetricEntityKey(catalog.entities.find(e => e.table === (def.metric_table || def.table))?.key || source.key);
    setDimensionEntityKey(catalog.entities.find(e => e.table === (def.group_by_table || def.table))?.key || source.key);
    setMetric(def.metric || '');
    setDimension(def.group_by || '');
    setAggregation(def.aggregation || 'count');
    setVisualization(def.visualization || 'bar');
    setTitle(mode === 'duplicate' ? `${def.title} (copia)` : def.title || '');
    setFilters((def.filters || []).map(item => ({ ...item, table: item.table || def.table, value: Array.isArray(item.value) ? item.value.join(',') : String(item.value ?? '') })));
    setShowFilters(Boolean(def.filters?.length));
    setSaveToAnalytics(initialItem.placement?.analytics ?? true);
    setSaveToDashboard(initialItem.placement?.dashboard ?? false);
    setPreview(null);
  }, [open, catalog, initialItem, mode]);
  useEffect(() => {
    if (!open || initialItem) return;
    setMetric(''); setDimension(''); setMetricEntityKey(entityKey); setDimensionEntityKey(entityKey); setFilters([]); setPreview(null);
  }, [entityKey, open, initialItem]);
  useEffect(() => { if (visualization === 'kpi') setDimension(''); setPreview(null); }, [visualization]);

  if (!open) return null;

  const definition = () => ({
    title: title || (language === 'es' ? 'Análisis de ' : 'Analysis of ') + (entity?.label || ''),
    visualization, table: entity?.table, metric: metric || null, metric_table: metricEntity?.table || entity?.table, aggregation,
    group_by: dimension || null, group_by_table: dimensionEntity?.table || entity?.table, filters: filters.map(({table,column,operator,value}) => ({table,column,operator,value:operator==='in'?value.split(',').map(v=>v.trim()).filter(Boolean):value.trim()})), limit: 20,
  });

  const runPreview = async () => {
    try {
      setLoading(true); setError('');
      setPreview(await previewVisualization(definition()));
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  const saveCurrent = async () => {
    if (!saveToAnalytics && !saveToDashboard && mode !== 'edit') {
      setError(language === 'es' ? 'Selecciona al menos un destino.' : 'Select at least one destination.');
      return;
    }
    try {
      setSaving(true); setError('');
      const saved = mode === 'edit' && initialItem ? await updateSavedVisualization(initialItem.id, definition(), { analytics: saveToAnalytics, dashboard: saveToDashboard }) : await saveVisualization(definition(), { analytics: saveToAnalytics, dashboard: saveToDashboard });
      onSaved?.(saved);
      onClose();
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };

  const data = preview?.data || [];
  const canPreview = entity && (!needsDimension || dimension) && (aggregation === 'count' || metric) && filters.every(f=>f.column&&f.value.trim());

  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <div className="max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-[26px] border shadow-2xl" style={{ backgroundColor: colors.panel, borderColor: colors.border }}>
      <header className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: colors.border }}>
        <div><p className="text-xs font-bold uppercase tracking-[0.18em]" style={{ color: theme.primary }}>{language === 'es' ? 'Constructor visual' : 'Visual builder'}</p><h2 className="mt-1 text-2xl font-extrabold" style={{ color: colors.text }}>{language === 'es' ? 'Crea tu propia visualización' : 'Create your own visualization'}</h2><p className="mt-1 text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Elige conceptos del negocio, sin escribir SQL.' : 'Choose business concepts without writing SQL.'}</p></div>
        <button onClick={onClose} className="rounded-xl border p-2 transition hover:scale-105" style={{ borderColor: colors.border, color: colors.text }}><X size={20}/></button>
      </header>
      <div className="grid max-h-[calc(92vh-104px)] overflow-y-auto lg:grid-cols-[380px_1fr]">
        <div className="space-y-5 border-r p-6" style={{ borderColor: colors.border }}>
          <Field label={language === 'es' ? '¿Qué quieres analizar?' : 'What do you want to analyze?'} colors={colors}><select value={entityKey} onChange={(e)=>setEntityKey(e.target.value)} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{(catalog?.entities||[]).map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select></Field>
          <div><span className="mb-2 block text-sm font-bold" style={{color:colors.text}}>{language === 'es' ? 'Visualización' : 'Visualization'}</span><div className="grid grid-cols-5 gap-2">{(catalog?.builder?.visualizations||[]).map(item=>{const Icon=ICONS[item.key]||BarChart3; const selected=visualization===item.key; return <button key={item.key} title={item.label} onClick={()=>setVisualization(item.key)} className="flex aspect-square items-center justify-center rounded-xl border transition hover:scale-105" style={{borderColor:selected?theme.primary:colors.border,backgroundColor:selected?colors.accentSoft:colors.card,color:selected?theme.primary:colors.muted}}><Icon size={20}/></button>})}</div></div>
          <Field label={language === 'es' ? '¿Qué quieres medir?' : 'What do you want to measure?'} colors={colors}><div className="space-y-2"><select value={metricEntity?.key || ''} onChange={(e)=>{setMetricEntityKey(e.target.value);setMetric('');setAggregation('count')}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{relatedEntities.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select><select value={metric} onChange={(e)=>{setMetric(e.target.value);setAggregation(e.target.value?'sum':'count')}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}><option value="">{language === 'es' ? 'Cantidad de registros' : 'Record count'}</option>{(metricEntity?.metrics||[]).map(field=><option key={field.key} value={field.key}>{field.label}</option>)}</select></div></Field>
          {metric && <Field label={language === 'es' ? 'Cálculo' : 'Calculation'} colors={colors}><select value={aggregation} onChange={(e)=>setAggregation(e.target.value)} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{(metricEntity?.metrics?.find(f=>f.key===metric)?.aggregations||[]).filter(a=>a!=='count').map(key=><option key={key} value={key}>{catalog?.builder?.aggregations?.[key]||key}</option>)}</select></Field>}
          {needsDimension && <Field label={language === 'es' ? '¿Cómo quieres agruparlo?' : 'How should it be grouped?'} colors={colors}><div className="space-y-2"><select value={dimensionEntity?.key || ''} onChange={(e)=>{setDimensionEntityKey(e.target.value);setDimension('')}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{relatedEntities.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select><select value={dimension} onChange={(e)=>setDimension(e.target.value)} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}><option value="">{language === 'es' ? 'Selecciona una dimensión' : 'Select a dimension'}</option>{(dimensionEntity?.dimensions||[]).map(field=><option key={field.key} value={field.key}>{field.label}</option>)}</select></div></Field>}
          <div className="rounded-2xl border p-4" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>
            <button type="button" onClick={()=>setShowFilters(!showFilters)} className="flex w-full justify-between text-sm font-bold" style={{color:colors.text}}><span>{language==='es'?'Filtros (opcional)':'Filters (optional)'} ({filters.length})</span><span>{showFilters?'−':'+'}</span></button>
            {showFilters&&<div className="mt-3 space-y-3">
              {filters.map((filter,index)=>{
                const source=relatedEntities.find(e=>e.table===filter.table)||entity;
                const field=source?.filters?.find(f=>f.key===filter.column);
                const ops=field?.kind==='text'?['eq','neq','contains','in']:['eq','neq','gt','gte','lt','lte','in'];
                const names={eq:language==='es'?'Igual a':'Equals',neq:language==='es'?'Distinto de':'Not equal',gt:'>',gte:'≥',lt:'<',lte:'≤',contains:language==='es'?'Contiene':'Contains',in:language==='es'?'Uno de (comas)':'One of (commas)'};
                const update=patch=>{setFilters(old=>old.map((f,i)=>i===index?{...f,...patch}:f));setPreview(null)};
                return <div key={index} className="space-y-2 rounded-xl border p-3" style={{borderColor:colors.border,backgroundColor:colors.card}}>
                  <div className="flex justify-between"><span className="text-xs" style={{color:colors.muted}}>{language==='es'?'Condición':'Condition'}</span><button type="button" className="text-xs text-red-500" onClick={()=>{setFilters(old=>old.filter((_,i)=>i!==index));setPreview(null)}}>{language==='es'?'Quitar':'Remove'}</button></div>
                  <select aria-label="Filter entity" value={source?.table||''} onChange={e=>{const next=relatedEntities.find(x=>x.table===e.target.value);update({table:e.target.value,column:next?.filters?.[0]?.key||'',operator:'eq',value:''})}} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{relatedEntities.map(e=><option key={e.table} value={e.table}>{e.label}</option>)}</select>
                  <select aria-label="Filter field" value={filter.column} onChange={e=>update({column:e.target.value,operator:'eq',value:''})} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{(source?.filters||[]).map(f=><option key={f.key} value={f.key}>{f.label}</option>)}</select>
                  <select aria-label="Filter operator" value={filter.operator} onChange={e=>update({operator:e.target.value,value:''})} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{ops.map(op=><option key={op} value={op}>{names[op]}</option>)}</select>
                  <FilterValueInput table={source?.table} field={field} operator={filter.operator} value={filter.value} onChange={value=>update({value})} colors={colors} language={language}/>
                </div>;
              })}
              <button type="button" onClick={()=>{setFilters(old=>[...old,{table:entity?.table||'',column:entity?.filters?.[0]?.key||'',operator:'eq',value:''}]);setPreview(null)}} className="w-full rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:theme.primary,color:theme.primary}}>{language==='es'?'+ Agregar filtro':'+ Add filter'}</button>
              {filters.length>1&&<p className="text-xs" style={{color:colors.muted}}>{language==='es'?'Se deben cumplir todas las condiciones (Y).':'All conditions must match (AND).'}</p>}
            </div>}
          </div>
          <Field label={language === 'es' ? 'Título' : 'Title'} colors={colors}><input value={title} onChange={(e)=>setTitle(e.target.value)} placeholder={language === 'es'?'Ej. Ventas por canal':'E.g. Sales by channel'} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}/></Field>
          <button disabled={!canPreview||loading} onClick={runPreview} className="w-full rounded-xl px-4 py-3 font-bold text-white transition enabled:hover:scale-[1.02] disabled:opacity-40" style={{backgroundColor:theme.primary}}>{loading?(language==='es'?'Generando...':'Generating...'):(language==='es'?'Generar vista previa':'Generate preview')}</button>
          {preview && <div className="rounded-2xl border p-4" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>
            <p className="mb-3 text-sm font-bold" style={{color:colors.text}}>{language==='es'?'¿Dónde quieres mostrarla?':'Where do you want to show it?'}</p>
            <label className="mb-2 flex cursor-pointer items-center gap-3 text-sm" style={{color:colors.text}}><input type="checkbox" checked={saveToAnalytics} onChange={(e)=>setSaveToAnalytics(e.target.checked)} className="h-4 w-4 accent-current"/><span>{language==='es'?'Analítica':'Analytics'} <small style={{color:colors.muted}}>({language==='es'?'predeterminado':'default'})</small></span></label>
            <label className="flex cursor-pointer items-center gap-3 text-sm" style={{color:colors.text}}><input type="checkbox" checked={saveToDashboard} onChange={(e)=>setSaveToDashboard(e.target.checked)} className="h-4 w-4 accent-current"/><span>Dashboard</span></label>
            <button disabled={saving||(!saveToAnalytics&&!saveToDashboard&&mode!=='edit')} onClick={saveCurrent} className="mt-4 w-full rounded-xl px-4 py-3 font-bold text-white transition enabled:hover:scale-[1.02] disabled:opacity-40" style={{backgroundColor:theme.primary}}>{saving?(language==='es'?'Guardando...':'Saving...'):(language==='es'?(mode==='edit'?'Guardar cambios':mode==='duplicate'?'Guardar copia':'Guardar visualización'):(mode==='edit'?'Save changes':mode==='duplicate'?'Save copy':'Save visualization'))}</button>
          </div>}
          {error&&<p className="text-sm text-red-500">{error}</p>}
        </div>
        <div className="min-h-[560px] p-6"><div className="flex h-full min-h-[500px] flex-col rounded-2xl border p-5" style={{backgroundColor:colors.card,borderColor:colors.border}}>
          <p className="text-xs font-semibold uppercase tracking-wider" style={{color:colors.muted}}>{language==='es'?'Vista previa':'Preview'}</p><h3 className="mt-1 text-xl font-extrabold" style={{color:colors.text}}>{preview?.definition?.title||title||(language==='es'?'Tu visualización aparecerá aquí':'Your visualization will appear here')}</h3>
          {!preview?<div className="flex flex-1 items-center justify-center text-sm" style={{color:colors.muted}}>{language==='es'?'Configura la visualización y genera una vista previa.':'Configure the visualization and generate a preview.'}</div>:visualization==='kpi'?<div className="flex flex-1 items-center justify-center"><div className="text-6xl font-black" style={{color:theme.primary}}>{Number(data[0]?.value||0).toLocaleString()}</div></div>:visualization==='table'?<div className="mt-6 overflow-auto"><table className="w-full text-sm"><tbody>{data.map((row,i)=><tr key={i} className="border-b" style={{borderColor:colors.border}}>{Object.values(row).map((value,j)=><td key={j} className="px-3 py-3" style={{color:colors.text}}>{String(value)}</td>)}</tr>)}</tbody></table></div>:<div className="mt-6 flex-1"><ResponsiveContainer width="100%" height="100%">{visualization==='line'?<ReLineChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension"/><YAxis/><Tooltip/><Line dataKey="value" stroke={theme.primary} strokeWidth={3}/></ReLineChart>:<BarChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension"/><YAxis/><Tooltip/><Bar dataKey="value" fill={theme.primary} radius={[7,7,0,0]}/></BarChart>}</ResponsiveContainer></div>}
        </div></div>
      </div>
    </div>
  </div>;
};

const inputStyle=(colors)=>({backgroundColor:colors.card,borderColor:colors.border,color:colors.text});
const Field=({label,colors,children})=><label className="block"><span className="mb-2 block text-sm font-bold" style={{color:colors.text}}>{label}</span>{children}</label>;


const FilterValueInput = ({table, field, operator, value, onChange, colors, language}) => {
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const supportsOptions = ['eq','neq','in'].includes(operator) && ['text','boolean'].includes(field?.kind);
  useEffect(() => {
    if (!supportsOptions || !table || !field?.key) { setOptions([]); return; }
    let active = true;
    setBusy(true); setLoadError(false);
    const delay = setTimeout(() => {
      getVisualizationFilterValues(table, field.key, search)
        .then(data => { if (active) setOptions(data.values || []); })
        .catch(() => { if (active) { setOptions([]); setLoadError(true); } })
        .finally(() => { if (active) setBusy(false); });
    }, 250);
    return () => { active = false; clearTimeout(delay); };
  }, [table, field?.key, search, supportsOptions]);
  useEffect(() => { setSearch(''); }, [table, field?.key, operator]);
  const selected = value.split(',').map(v => v.trim()).filter(Boolean);
  if (!supportsOptions) return <input aria-label="Filter value" type={field?.kind==='number'&&operator!=='in'?'number':field?.kind==='date'&&operator!=='in'?'date':'text'} value={value} onChange={e=>onChange(e.target.value)} placeholder={language==='es'?'Escribe un valor':'Enter a value'} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}/>;
  return <div className="space-y-2">
    <input aria-label={language==='es'?'Buscar valores':'Search values'} value={search} onChange={e=>setSearch(e.target.value)} placeholder={language==='es'?'Buscar valores disponibles...':'Search available values...'} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}/>
    {operator==='in' ? <div className="max-h-36 space-y-1 overflow-y-auto rounded-lg border p-2" style={{borderColor:colors.border}}>
      {options.map(option=><label key={option} className="flex items-center gap-2 text-sm" style={{color:colors.text}}><input type="checkbox" checked={selected.includes(option)} onChange={e=>onChange(e.target.checked?[...selected,option].join(','):selected.filter(v=>v!==option).join(','))}/>{option}</label>)}
    </div> : <select aria-label={language==='es'?'Valor disponible':'Available value'} value={value} onChange={e=>onChange(e.target.value)} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>
      <option value="">{language==='es'?'Selecciona un valor':'Select a value'}</option>
      {value && !options.includes(value) && <option value={value}>{value}</option>}
      {options.map(option=><option key={option} value={option}>{option}</option>)}
    </select>}
    {busy&&<p className="text-xs" style={{color:colors.muted}}>{language==='es'?'Consultando valores...':'Loading values...'}</p>}
    {loadError&&<p className="text-xs text-amber-600">{language==='es'?'No se pudieron cargar los valores.':'Could not load values.'}</p>}
    {options.length===0&&!busy&&!loadError&&<p className="text-xs" style={{color:colors.muted}}>{language==='es'?'No hay valores disponibles.':'No available values.'}</p>}
  </div>;
};
