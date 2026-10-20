import { useContext, useEffect, useMemo, useState } from 'react';
import { BarChart3, LineChart, Sigma, Table2, X } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart as ReLineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DashboardContext } from '../context/DashboardContext';
import { ChartAxisHint } from './ChartAxisHint';
import { visualizationAxisLabels } from './visualizationAxisLabels';
import { VisualizationResultTable } from './VisualizationResultTable';
import { TableExplorer } from './TableExplorer';
import { getDatabaseStatus, getVisualizationSemanticCatalog, getVisualizationFilterValues, previewVisualization, saveVisualization, updateSavedVisualization } from '../services/api';

const ICONS = { kpi: Sigma, bar: BarChart3, line: LineChart, area: LineChart, donut: BarChart3, table: Table2 };
const sameSource = (expected, actual) => !expected || (
  expected.database === actual.database &&
  expected.provider === actual.provider &&
  (!expected.server || expected.server === actual.server) &&
  (!expected.host || expected.host === actual.host) &&
  (!expected.port || expected.port === actual.port)
);

export const VisualizationBuilder = ({ open, onClose, onSaved, initialItem = null, mode = 'create' }) => {
  const { colors, theme, language } = useContext(DashboardContext);
  const [catalog, setCatalog] = useState(null);
  const [entityKey, setEntityKey] = useState('');
  const [metric, setMetric] = useState('');
  const [metricEntityKey, setMetricEntityKey] = useState('');
  const [dimensionEntityKey, setDimensionEntityKey] = useState('');
  const [aggregation, setAggregation] = useState('count');
  const [dimension, setDimension] = useState('');
  const [timeGranularity, setTimeGranularity] = useState('raw');
  const [rowLimit, setRowLimit] = useState(20);
  const [sortDirection, setSortDirection] = useState('desc');
  const [timeDirection, setTimeDirection] = useState('asc');
  const [groupIdentity, setGroupIdentity] = useState(null);
  const [sourceMismatch, setSourceMismatch] = useState(false);
  const [visualization, setVisualization] = useState('bar');
  const [tableMode, setTableMode] = useState('aggregate');
  const [detailColumns, setDetailColumns] = useState([]);
  const [title, setTitle] = useState('');
  const [filters, setFilters] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [preview, setPreview] = useState(null);
  const [exploring, setExploring] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveToAnalytics, setSaveToAnalytics] = useState(true);
  const [saveToDashboard, setSaveToDashboard] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    Promise.all([getVisualizationSemanticCatalog(), getDatabaseStatus()])
      .then(([data, status]) => {
        if (!active) return;
        setCatalog(data);
        setSourceMismatch(!sameSource(initialItem?.source, status));
        if (data.entities?.[0]) setEntityKey(data.entities[0].key);
      })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [open, initialItem]);

  const entity = useMemo(() => catalog?.entities?.find((item) => item.key === entityKey), [catalog, entityKey]);
  const relatedEntities = useMemo(() => {
    if (!catalog || !entity) return [];
    // Only expose safe child->parent paths. A reverse join can multiply
    // fact rows and corrupt counts or sums in all business domains.
    const reachable = new Set([entity.table]);
    let changed = true;
    while (changed) {
      changed = false;
      (catalog.relationships || []).forEach((rel) => {
        const parent = catalog.entities.find(e => e.table === rel.to_table);
        if (reachable.has(rel.from_table) && parent?.primary_key?.includes(rel.to_column)
            && !reachable.has(rel.to_table)) {
          reachable.add(rel.to_table);
          changed = true;
        }
      });
    }
    return (catalog.entities || []).filter((item) => reachable.has(item.table));
  }, [catalog, entity]);
  const metricEntity = relatedEntities.find((item) => item.key === metricEntityKey) || entity;
  const dimensionEntity = relatedEntities.find((item) => item.key === dimensionEntityKey) || entity;
  const isDetailTable = visualization === 'table' && tableMode === 'detail';
  const needsDimension = ['bar', 'line', 'area', 'donut'].includes(visualization);
  const supportsDimension = !isDetailTable && (needsDimension || visualization === 'table');
  const selectedDimensionField = dimensionEntity?.dimensions?.find(field => field.key === dimension);
  const dimensionIsDate = selectedDimensionField?.kind === 'date' || selectedDimensionField?.semantic === 'date';
  const metricOptions = metricEntity?.metrics?.find(field => field.key === metric)?.aggregations || [];
  const effectiveAggregation = metric ? (metricOptions.includes(aggregation) ? aggregation : (metricOptions.includes('sum') ? 'sum' : metricOptions[0] || 'count')) : 'count';

  useEffect(() => {
    if (!open || !catalog) return;
    const def = initialItem?.definition;
    if (!def) return;
    const source = catalog.entities?.find(e => e.table === def.table);
    if (!source) return;
    let active = true;
    // Defer initialization so the effect does not synchronously cascade renders.
    queueMicrotask(() => {
      if (!active) return;
      setEntityKey(source.key);
      setMetricEntityKey(catalog.entities.find(e => e.table === (def.metric_table || def.table))?.key || source.key);
      setDimensionEntityKey(catalog.entities.find(e => e.table === (def.group_by_table || def.table))?.key || source.key);
      setMetric(def.metric || '');
      setDimension(def.group_by || '');
      setTimeGranularity(def.time_granularity || 'raw');
      setRowLimit(def.limit || 20);
      setSortDirection(def.sort_direction || 'desc');
      setTimeDirection(def.time_direction || 'asc');
      setGroupIdentity(def.group_by_identity || null);
      setAggregation(def.aggregation || 'count');
      setVisualization(def.visualization || 'bar');
      setTableMode(def.table_mode || 'aggregate');
      setDetailColumns(def.detail_columns || []);
      setTitle(mode === 'duplicate' ? `${def.title} (copia)` : def.title || '');
      setFilters((def.filters || []).map(item => ({ ...item, table: item.table || def.table, value: Array.isArray(item.value) ? item.value.join(',') : String(item.value ?? '') })));
      setShowFilters(Boolean(def.filters?.length));
      setSaveToAnalytics(initialItem.placement?.analytics ?? true);
      setSaveToDashboard(initialItem.placement?.dashboard ?? false);
      setPreview(initialItem.preview || null);
    });
    return () => { active = false; };
  }, [open, catalog, initialItem, mode]);
  useEffect(() => {
    if (!open || initialItem) return;
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setMetric(''); setDimension(''); setMetricEntityKey(entityKey);
      setDimensionEntityKey(entityKey); setFilters([]); setTimeGranularity('raw'); setPreview(null);
      setTableMode('aggregate'); setDetailColumns([]);
      setGroupIdentity(null); setSortDirection('desc'); setTimeDirection('asc');
    });
    return () => { active = false; };
  }, [entityKey, open, initialItem]);
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      if (visualization === 'kpi') setDimension('');
    });
    return () => { active = false; };
  }, [visualization]);

  if (!open) return null;

  const definition = () => ({
    title: title || (language === 'es' ? 'Análisis de ' : 'Analysis of ') + (entity?.label || ''),
    visualization, table: entity?.table,
    metric: isDetailTable ? null : (metric || null),
    metric_table: metricEntity?.table || entity?.table,
    aggregation: isDetailTable ? 'count' : effectiveAggregation,
    group_by: isDetailTable ? null : (dimension || null), group_by_table: dimensionEntity?.table || entity?.table,
    group_by_identity: isDetailTable ? null : (groupIdentity || null),
    sort_direction: sortDirection,
    time_direction: timeDirection,
    table_mode: isDetailTable ? 'detail' : 'aggregate',
    detail_columns: isDetailTable ? detailColumns : [],
    time_granularity: dimensionIsDate ? timeGranularity : 'raw', filters: filters.map(({table,column,operator,value,value_table}) => ({table,column,operator,
      value:['in','between'].includes(operator)
        ? value.split(',').map(v=>v.trim()).filter(Boolean)
        : value.trim(),
      value_table:operator.endsWith('_field')?(value_table||table):null})), limit: rowLimit,
  });

  const runPreview = async () => {
    if (sourceMismatch) {
      setError(language === 'es' ? 'Cambió la fuente de datos. Cierra y vuelve a solicitar la gráfica.' : 'Data source changed. Please request the chart again.');
      return;
    }
    try {
      setLoading(true); setError(''); setPreview(null);
      setPreview(await previewVisualization(definition()));
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  const saveCurrent = async () => {
    if (!saveToAnalytics && !saveToDashboard && mode !== 'edit') {
      setError(language === 'es' ? 'Selecciona al menos un destino.' : 'Select at least one destination.');
      return;
    }
    if (sourceMismatch) {
      setError(language === 'es' ? 'La fuente activa no coincide con la propuesta. Solicita una nueva.' : 'The active source does not match this draft.');
      return;
    }
    try {
      setSaving(true); setError('');
      // Validate again at the exact point of saving: data and source may have
      // changed since the chat preview. Never persist an empty visualization.
      // The backend connection is globally active; re-check immediately before
      // saving in case another browser session switched databases meanwhile.
      if (!sameSource(initialItem?.source, await getDatabaseStatus())) {
        throw new Error(language === 'es'
          ? 'La fuente de datos cambió mientras editabas. Solicita nuevamente la gráfica.'
          : 'The data source changed while editing. Please request the chart again.');
      }
      const fresh = await previewVisualization(definition());
      if (!(fresh.data || []).length) {
        throw new Error(language === 'es'
          ? 'No hay datos para estos campos y filtros. Modifica la propuesta antes de guardarla.'
          : 'No data for these fields and filters. Adjust the draft before saving.');
      }
      const saved = mode === 'edit' && initialItem ? await updateSavedVisualization(initialItem.id, definition(), { analytics: saveToAnalytics, dashboard: saveToDashboard }) : await saveVisualization(definition(), { analytics: saveToAnalytics, dashboard: saveToDashboard });
      onSaved?.(saved);
      onClose();
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };

  const data = preview?.data || [];
  const axes = visualizationAxisLabels(preview?.definition || { table: entity?.table, group_by: dimension, group_by_table: dimensionEntity?.table, metric, metric_table: metricEntity?.table, aggregation: effectiveAggregation }, catalog, language);
  const canPreview = entity && (
    isDetailTable ? detailColumns.length > 0
      : (!needsDimension || dimension) && (
          effectiveAggregation === 'count' || Boolean(metric)
        )
  ) && filters.every(f =>
    f.column && (['is_null', 'not_null'].includes(f.operator) || String(f.value ?? '').trim())
  );

  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <div className="max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-[26px] border shadow-2xl" style={{ backgroundColor: colors.panel, borderColor: colors.border }}>
      <header className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: colors.border }}>
        <div><p className="text-xs font-bold uppercase tracking-[0.18em]" style={{ color: theme.primary }}>{language === 'es' ? 'Constructor visual' : 'Visual builder'}</p><h2 className="mt-1 text-2xl font-extrabold" style={{ color: colors.text }}>{language === 'es' ? 'Crea tu propia visualización' : 'Create your own visualization'}</h2><p className="mt-1 text-sm" style={{ color: colors.muted }}>{language === 'es' ? 'Elige conceptos del negocio, sin escribir SQL.' : 'Choose business concepts without writing SQL.'}</p></div>
        <button onClick={onClose} className="rounded-xl border p-2 transition hover:scale-105" style={{ borderColor: colors.border, color: colors.text }}><X size={20}/></button>
      </header>
      <div className="grid max-h-[calc(92vh-104px)] overflow-y-auto lg:grid-cols-[380px_1fr]">
        <div className="space-y-5 border-r p-6" style={{ borderColor: colors.border }}>
          <Field label={language === 'es' ? '¿Qué quieres analizar?' : 'What do you want to analyze?'} colors={colors}><select value={entityKey} onChange={(e)=>setEntityKey(e.target.value)} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{(catalog?.entities||[]).map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select></Field>
          <div><span className="mb-2 block text-sm font-bold" style={{color:colors.text}}>{language === 'es' ? 'Visualización' : 'Visualization'}</span><div className="grid grid-cols-6 gap-2">{(catalog?.builder?.visualizations||[]).map(item=>{const Icon=ICONS[item.key]||BarChart3; const selected=visualization===item.key; return <button key={item.key} title={item.label} onClick={()=>{setVisualization(item.key);setPreview(null)}} className="flex aspect-square items-center justify-center rounded-xl border transition hover:scale-105" style={{borderColor:selected?theme.primary:colors.border,backgroundColor:selected?colors.accentSoft:colors.card,color:selected?theme.primary:colors.muted}}><Icon size={20}/></button>})}</div></div>
          {visualization === 'table' && (
            <Field label={language === 'es' ? 'Tipo de tabla' : 'Table mode'} colors={colors}>
              <select value={tableMode} onChange={e=>{
                const next=e.target.value;
                setTableMode(next);
                setPreview(null);
                if (next==='detail' && !detailColumns.length) {
                  setDetailColumns((entity?.fields||[]).filter(field=>!field.is_identifier)
                    .slice(0,4).map(field=>({table:entity.table,column:field.key})));
                }
              }} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>
                <option value="aggregate">{language==='es'?'Resumen agrupado (dimensión + medida)':'Aggregated summary'}</option>
                <option value="detail">{language==='es'?'Registros detallados (columnas)':'Detailed records (columns)'}</option>
              </select>
            </Field>
          )}
          {isDetailTable && (
            <div className="rounded-xl border p-3" style={{borderColor:colors.border}}>
              <p className="mb-1 text-sm font-bold" style={{color:colors.text}}>
                {language==='es'?'Columnas a mostrar (máximo 8)':'Columns to show (up to 8)'}
              </p>
              <p className="mb-3 text-xs" style={{color:colors.muted}}>
                {language==='es'
                  ? 'Elige campos reales de la fuente; no se mostrarán columnas que no selecciones.'
                  : 'Choose real source fields; unselected columns are never displayed.'}
              </p>
              <div className="max-h-44 space-y-2 overflow-y-auto">
                {relatedEntities.map(src=>(
                  <div key={src.table}>
                    <p className="text-xs font-bold" style={{color:theme.primary}}>{src.label}</p>
                    {src.fields?.map(field=>{
                      const checked=detailColumns.some(item=>item.table===src.table&&item.column===field.key);
                      return <label key={field.key} className="mt-1 flex items-center gap-2 text-xs" style={{color:colors.text}}>
                        <input type="checkbox" checked={checked}
                          disabled={!checked&&detailColumns.length>=8}
                          onChange={event=>{
                            setDetailColumns(old=>event.target.checked
                              ? [...old,{table:src.table,column:field.key}]
                              : old.filter(item=>!(item.table===src.table&&item.column===field.key)));
                            setPreview(null);
                          }}/>
                        {field.label}
                      </label>;
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}
          {!isDetailTable && <Field label={language === 'es' ? '¿Qué quieres medir?' : 'What do you want to measure?'} colors={colors}><div className="space-y-2"><select value={metricEntity?.key || ''} onChange={(e)=>{setMetricEntityKey(e.target.value);setMetric('');setAggregation('count');setPreview(null)}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{relatedEntities.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select><select value={metric} onChange={(e)=>{
              const next=e.target.value;
              const field=metricEntity?.metrics?.find(item=>item.key===next);
              setMetric(next);
              setAggregation(field?.aggregations?.includes('sum')?'sum'
                :field?.aggregations?.includes('distinct_count')?'distinct_count':'count');
              setPreview(null);
            }} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}><option value="">{language === 'es' ? 'Cantidad de registros' : 'Record count'}</option>{(metricEntity?.metrics||[]).map(field=><option key={field.key} value={field.key}>{field.label}</option>)}</select></div></Field>}
          {!isDetailTable && metric && <Field label={language === 'es' ? 'Cálculo' : 'Calculation'} colors={colors}><select value={effectiveAggregation} onChange={(e)=>{setAggregation(e.target.value);setPreview(null)}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{metricOptions.map(key=><option key={key} value={key}>{catalog?.builder?.aggregations?.[key]||key}</option>)}</select></Field>}
          {supportsDimension && <Field label={language === 'es' ? '¿Cómo quieres agruparlo?' : 'How should it be grouped?'} colors={colors}><div className="space-y-2"><select value={dimensionEntity?.key || ''} onChange={(e)=>{setDimensionEntityKey(e.target.value);setDimension('');setGroupIdentity(null);setPreview(null)}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>{relatedEntities.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select><select value={dimension} onChange={(e)=>{setDimension(e.target.value);setTimeGranularity('raw');setGroupIdentity(null);setPreview(null)}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}><option value="">{language === 'es' ? 'Selecciona una dimensión' : 'Select a dimension'}</option>{(dimensionEntity?.dimensions||[]).map(field=><option key={field.key} value={field.key}>{field.label}</option>)}</select></div></Field>}
          {dimensionIsDate && supportsDimension && (
            <Field label={language === 'es' ? 'Agrupación temporal' : 'Time grouping'} colors={colors}>
              <select value={timeGranularity} onChange={(e)=>{setTimeGranularity(e.target.value);setPreview(null)}} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>
                <option value="raw">{language === 'es' ? 'Cada fecha' : 'Each date'}</option>
                <option value="month">{language === 'es' ? 'Por mes (AAAA-MM)' : 'By month (YYYY-MM)'}</option>
                <option value="quarter">{language === 'es' ? 'Por trimestre (AAAA-Qn)' : 'By quarter (YYYY-Qn)'}</option>
                <option value="year">{language === 'es' ? 'Por año' : 'By year'}</option>
              </select>
            </Field>
          )}
          <div className="rounded-2xl border p-4" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>
            <button type="button" onClick={()=>setShowFilters(!showFilters)} className="flex w-full justify-between text-sm font-bold" style={{color:colors.text}}><span>{language==='es'?'Filtros (opcional)':'Filters (optional)'} ({filters.length})</span><span>{showFilters?'−':'+'}</span></button>
            {showFilters&&<div className="mt-3 space-y-3">
              {filters.map((filter,index)=>{
                const source=relatedEntities.find(e=>e.table===filter.table)||entity;
                const field=source?.filters?.find(f=>f.key===filter.column);
                const ops=field?.kind==='text'?['eq','neq','contains','in','is_null','not_null']
                  :field?.kind==='number'
                    ? ['eq','neq','gt','gte','lt','lte','in','between','lt_field','lte_field','gt_field','gte_field','is_null','not_null']
                    : ['eq','neq','gt','gte','lt','lte','in','between','is_null','not_null'];
                const names={eq:language==='es'?'Igual a':'Equals',neq:language==='es'?'Distinto de':'Not equal',gt:'>',gte:'≥',lt:'<',lte:'≤',contains:language==='es'?'Contiene':'Contains',in:language==='es'?'Uno de (comas)':'One of (commas)',
                  lt_field:language==='es'?'Menor que columna':'Less than field',
                  lte_field:language==='es'?'Menor o igual que columna':'Less than or equal to field',
                  gt_field:language==='es'?'Mayor que columna':'Greater than field',
                  gte_field:language==='es'?'Mayor o igual que columna':'Greater than or equal to field',
                  between:language==='es'?'Entre dos valores':'Between two values',
                  is_null:language==='es'?'Sin valor':'Empty (null)',
                  not_null:language==='es'?'Con valor':'Not empty'};
                const update=patch=>{setFilters(old=>old.map((f,i)=>i===index?{...f,...patch}:f));setPreview(null)};
                return <div key={index} className="space-y-2 rounded-xl border p-3" style={{borderColor:colors.border,backgroundColor:colors.card}}>
                  <div className="flex justify-between"><span className="text-xs" style={{color:colors.muted}}>{language==='es'?'Condición':'Condition'}</span><button type="button" className="text-xs text-red-500" onClick={()=>{setFilters(old=>old.filter((_,i)=>i!==index));setPreview(null)}}>{language==='es'?'Quitar':'Remove'}</button></div>
                  <select aria-label="Filter entity" value={source?.table||''} onChange={e=>{const next=relatedEntities.find(x=>x.table===e.target.value);update({table:e.target.value,column:next?.filters?.[0]?.key||'',operator:'eq',value:'',value_table:null})}} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{relatedEntities.map(e=><option key={e.table} value={e.table}>{e.label}</option>)}</select>
                  <select aria-label="Filter field" value={filter.column} onChange={e=>update({column:e.target.value,operator:'eq',value:'',value_table:null})} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{(source?.filters||[]).map(f=><option key={f.key} value={f.key}>{f.label}</option>)}</select>
                  <select aria-label="Filter operator" value={filter.operator} onChange={e=>update({operator:e.target.value,value:'',value_table:null})} className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>{ops.map(op=><option key={op} value={op}>{names[op]}</option>)}</select>
                  <FilterValueInput key={`${source?.table}:${field?.key}:${filter.operator}`} table={source?.table} field={field} operator={filter.operator} value={filter.value} onChange={value=>update({value})} colors={colors} language={language} numericFields={relatedEntities.filter(item=>item.table===source?.table
                    || (catalog?.relationships||[]).some(rel=>rel.from_table===source?.table&&rel.to_table===item.table))
                    .flatMap(item=>(item.filters||[]).filter(f=>f.kind==='number'&&!f.is_identifier
                      && !(item.table===source?.table&&f.key===field?.key))
                      .map(f=>({...f,table:item.table,sourceLabel:item.label})))}
                    valueTable={filter.value_table}
                    onComparisonChange={(table,value)=>update({value,value_table:table})}/>
                </div>;
              })}
              <button type="button" onClick={()=>{setFilters(old=>[...old,{table:entity?.table||'',column:entity?.filters?.[0]?.key||'',operator:'eq',value:''}]);setPreview(null)}} className="w-full rounded-lg border px-3 py-2 text-sm font-semibold" style={{borderColor:theme.primary,color:theme.primary}}>{language==='es'?'+ Agregar filtro':'+ Add filter'}</button>
              {filters.length>1&&<p className="text-xs" style={{color:colors.muted}}>{language==='es'?'Se deben cumplir todas las condiciones (Y).':'All conditions must match (AND).'}</p>}
            </div>}
          </div>
          {supportsDimension && dimensionIsDate && (
            <Field label={language==='es'?'Orden temporal':'Chronological order'} colors={colors}>
              <select value={timeDirection} onChange={e=>{setTimeDirection(e.target.value);setPreview(null)}}
                className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>
                <option value="asc">{language==='es'?'Del más antiguo al más reciente':'Oldest first'}</option>
                <option value="desc">{language==='es'?'Del más reciente al más antiguo':'Newest first'}</option>
              </select>
            </Field>
          )}
          {(isDetailTable || (supportsDimension && !dimensionIsDate)) && (
            <Field label={language === 'es' ? 'Orden de resultados' : 'Result order'} colors={colors}>
              <select value={sortDirection} onChange={(e)=>{setSortDirection(e.target.value);setPreview(null)}}
                className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}>
                <option value="desc">{language === 'es' ? 'Mayor a menor' : 'Highest to lowest'}</option>
                <option value="asc">{language === 'es' ? 'Menor a mayor' : 'Lowest to highest'}</option>
              </select>
            </Field>
          )}
          {groupIdentity && <p className="text-xs leading-5" style={{ color: colors.muted }}>
            {language === 'es'
              ? 'Se conserva el identificador verificado para no combinar elementos con nombres iguales.'
              : 'A verified identifier is preserved to avoid merging items with identical names.'}
          </p>}
          <Field label={language === 'es' ? (isDetailTable ? 'Máximo de filas' : 'Máximo de grupos') : (isDetailTable ? 'Maximum rows' : 'Maximum groups')} colors={colors}>
            <input type="number" min={1} max={100} value={rowLimit}
              onChange={(e)=>{setRowLimit(Math.max(1,Math.min(100,Number(e.target.value)||1)));setPreview(null)}}
              className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)} />
          </Field>
          <Field label={language === 'es' ? 'Título' : 'Title'} colors={colors}><input value={title} onChange={(e)=>{setTitle(e.target.value);setPreview(null)}} placeholder={language === 'es'?'Ej. Ventas por canal':'E.g. Sales by channel'} className="w-full rounded-xl border px-3 py-3" style={inputStyle(colors)}/></Field>
          <button disabled={!canPreview||loading||sourceMismatch} onClick={runPreview} className="w-full rounded-xl px-4 py-3 font-bold text-white transition enabled:hover:scale-[1.02] disabled:opacity-40" style={{backgroundColor:theme.primary}}>{loading?(language==='es'?'Generando...':'Generating...'):(language==='es'?'Generar vista previa':'Generate preview')}</button>
          {preview && <div className="rounded-2xl border p-4" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>
            <p className="mb-3 text-sm font-bold" style={{color:colors.text}}>{language==='es'?'¿Dónde quieres mostrarla?':'Where do you want to show it?'}</p>
            <label className="mb-2 flex cursor-pointer items-center gap-3 text-sm" style={{color:colors.text}}><input type="checkbox" checked={saveToAnalytics} onChange={(e)=>setSaveToAnalytics(e.target.checked)} className="h-4 w-4 accent-current"/><span>{language==='es'?'Analítica':'Analytics'} <small style={{color:colors.muted}}>({language==='es'?'predeterminado':'default'})</small></span></label>
            <label className="flex cursor-pointer items-center gap-3 text-sm" style={{color:colors.text}}><input type="checkbox" checked={saveToDashboard} onChange={(e)=>setSaveToDashboard(e.target.checked)} className="h-4 w-4 accent-current"/><span>Dashboard</span></label>
            <button disabled={saving||sourceMismatch||(!saveToAnalytics&&!saveToDashboard&&mode!=='edit')} onClick={saveCurrent} className="mt-4 w-full rounded-xl px-4 py-3 font-bold text-white transition enabled:hover:scale-[1.02] disabled:opacity-40" style={{backgroundColor:theme.primary}}>{saving?(language==='es'?'Guardando...':'Saving...'):(language==='es'?(mode==='edit'?'Guardar cambios':mode==='duplicate'?'Guardar copia':'Guardar visualización'):(mode==='edit'?'Save changes':mode==='duplicate'?'Save copy':'Save visualization'))}</button>
          </div>}
          {sourceMismatch && <p role="alert" className="text-sm text-red-500">{language === 'es' ? 'La fuente activa cambió; esta propuesta no puede guardarse.' : 'Active source changed; this draft cannot be saved.'}</p>}
          {error&&<p className="text-sm text-red-500">{error}</p>}
        </div>
        <div className="min-h-[560px] p-6"><div className="flex h-full min-h-[500px] flex-col rounded-2xl border p-5" style={{backgroundColor:colors.card,borderColor:colors.border}}>
          <p className="text-xs font-semibold uppercase tracking-wider" style={{color:colors.muted}}>{language==='es'?'Vista previa':'Preview'}</p><h3 className="mt-1 text-xl font-extrabold" style={{color:colors.text}}>{preview?.definition?.title||title||(language==='es'?'Tu visualización aparecerá aquí':'Your visualization will appear here')}</h3>
          {!preview?<div className="flex flex-1 items-center justify-center text-sm" style={{color:colors.muted}}>{language==='es'?'Configura la visualización y genera una vista previa.':'Configure the visualization and generate a preview.'}</div>:visualization==='kpi'?<div className="flex flex-1 items-center justify-center"><div className="text-6xl font-black" style={{color:theme.primary}}>{Number(data[0]?.value||0).toLocaleString()}</div></div>:visualization==='table'?<div className="mt-6 min-w-0 flex-1"><VisualizationResultTable key={JSON.stringify(preview?.definition)} preview={preview} colors={colors} language={language}/>
              <button type="button" onClick={()=>setExploring(true)}
                className="mt-3 rounded-lg border px-3 py-2 text-sm font-bold"
                style={{borderColor:theme.primary,color:theme.primary}}>
                {language==='es'?'Explorar todos los registros':'Explore all records'}
              </button>
            </div>:<div className="mt-6 flex min-h-0 flex-1 flex-col">{visualization==='donut'?<p className="mb-2 text-xs" style={{color:colors.muted}}>{language==='es'?'Categoría':'Category'}: {axes.x} · {language==='es'?'Valor':'Value'}: {axes.y}</p>:<ChartAxisHint className="mb-2" x={axes.x} y={axes.y} language={language} colors={colors} />}<div className="min-h-0 flex-1"><ResponsiveContainer width="100%" height="100%">{visualization==='donut'?<PieChart><Pie data={data} dataKey="value" nameKey="dimension" cx="50%" cy="50%" innerRadius="43%" outerRadius="72%" paddingAngle={2}>{data.map((row,i)=><Cell key={`${row.dimension}-${i}`} fill={['#2563eb','#0891b2','#16a34a','#d97706','#9333ea','#db2777'][i%6]}/>)}</Pie><Tooltip/></PieChart>:visualization==='line'?<ReLineChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension"/><YAxis/><Tooltip/><Line dataKey="value" stroke={theme.primary} strokeWidth={3}/></ReLineChart>:visualization==='area'?<AreaChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension"/><YAxis/><Tooltip/><Area type="monotone" dataKey="value" stroke={theme.primary} fill={theme.primary} fillOpacity={0.22}/></AreaChart>:<BarChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension"/><YAxis/><Tooltip/><Bar dataKey="value" fill={theme.primary} radius={[7,7,0,0]}/></BarChart>}</ResponsiveContainer></div></div>}
        </div></div>
      </div>
    </div>
    {exploring && preview?.definition && (
      <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4"
        role="presentation" onMouseDown={e=>e.target===e.currentTarget&&setExploring(false)}>
        <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border p-5 shadow-xl"
          role="dialog" aria-modal="true"
          aria-label={language==='es'?'Explorador de tabla':'Table explorer'}
          style={{backgroundColor:colors.panel,borderColor:colors.border}}>
          <button type="button" onClick={()=>setExploring(false)}
            className="mb-3 self-end rounded-lg border px-3 py-1.5 text-sm font-bold"
            style={{color:colors.text,borderColor:colors.border}}>
            {language==='es'?'Cerrar':'Close'}
          </button>
          <div className="min-h-0 flex-1">
            <TableExplorer definition={preview.definition}/>
          </div>
        </div>
      </div>
    )}
  </div>;
};

const inputStyle=(colors)=>({backgroundColor:colors.card,borderColor:colors.border,color:colors.text});
const Field=({label,colors,children})=><label className="block"><span className="mb-2 block text-sm font-bold" style={{color:colors.text}}>{label}</span>{children}</label>;


const FilterValueInput = ({table, field, operator, value, onChange, colors, language, numericFields=[], valueTable, onComparisonChange}) => {
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const supportsOptions = ['eq','neq','in'].includes(operator) && ['text','boolean'].includes(field?.kind);
  useEffect(() => {
    if (!supportsOptions || !table || !field?.key) return;
    let active = true;
    const delay = setTimeout(() => {
      if (!active) return;
      setBusy(true); setLoadError(false);
      getVisualizationFilterValues(table, field.key, search)
        .then(data => { if (active) setOptions(data.values || []); })
        .catch(() => { if (active) { setOptions([]); setLoadError(true); } })
        .finally(() => { if (active) setBusy(false); });
    }, 250);
    return () => { active = false; clearTimeout(delay); };
  }, [table, field?.key, search, supportsOptions]);
  const selected = value.split(',').map(v => v.trim()).filter(Boolean);
  if (operator==='is_null'||operator==='not_null') return (
    <p className="text-xs" style={{color:colors.muted}}>
      {language==='es'?'Esta condición no necesita un valor adicional.':'No additional value is required.'}
    </p>
  );
  if (operator==='between') return (
    <div className="grid grid-cols-2 gap-2">
      {['Inicio','Final'].map((label,index)=>(
        <input key={label} aria-label={language==='es'?label:index?'End':'Start'}
          type={field?.kind==='date'?'date':field?.kind==='number'?'number':'text'}
          value={value.split(',')[index]||''}
          onChange={e=>{
            const next=value.split(',');
            next[index]=e.target.value;
            onChange(`${next[0]||''},${next[1]||''}`);
          }}
          placeholder={language==='es'?label:(index?'End':'Start')}
          className="w-full rounded-lg border p-2 text-xs" style={inputStyle(colors)}/>
      ))}
    </div>
  );
  if (operator.endsWith('_field')) return <select
    aria-label={language==='es'?'Columna numérica de comparación':'Comparison numeric field'}
    value={value ? JSON.stringify([valueTable||table,value]) : ''}
    onChange={e=>{
      const picked=numericFields.find(item=>JSON.stringify([item.table,item.key])===e.target.value);
      if (picked) onComparisonChange(picked.table,picked.key);
      else onComparisonChange(null,'');
    }}
    className="w-full rounded-lg border p-2 text-sm" style={inputStyle(colors)}>
    <option value="">{language==='es'?'Selecciona una columna numérica':'Select a numeric field'}</option>
    {numericFields.map(item=><option key={JSON.stringify([item.table,item.key])}
      value={JSON.stringify([item.table,item.key])}>{item.sourceLabel} · {item.label}</option>)}
  </select>;
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
