import { useContext, useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { LayoutDashboard, RefreshCw } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { getSavedVisualizations, previewVisualization } from '../services/api';

const formatValue = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

export const CustomVisualizationWidget = ({ item }) => {
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

  return <section className="min-h-[250px] rounded-2xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md" style={cardStyle}>
    <div className="mb-4 flex items-start justify-between gap-3">
      <div><p className="text-[11px] font-bold uppercase tracking-wider" style={{color:theme.primary}}>{language==='es'?'Personalizada':'Custom'}</p><h3 className="font-extrabold" style={{color:colors.text}}>{item.definition.title}</h3></div>
      {item.placement?.dashboard && <LayoutDashboard size={17} style={{color:theme.primary}}/>}
    </div>
    {error ? <p className="text-sm text-red-500">{error}</p> : !preview ? <div className="flex h-44 items-center justify-center" style={{color:colors.muted}}><RefreshCw className="animate-spin" size={18}/></div> :
      type === 'kpi' ? <div className="flex h-40 items-center justify-center text-5xl font-black" style={{color:theme.primary}}>{formatValue(data[0]?.value)}</div> :
      type === 'table' ? <div className="max-h-48 overflow-auto"><table className="w-full text-sm"><tbody>{data.map((row,i)=><tr key={i} className="border-b" style={{borderColor:colors.border}}>{Object.values(row).map((v,j)=><td key={j} className="px-2 py-2" style={{color:colors.text}}>{String(v)}</td>)}</tr>)}</tbody></table></div> :
      <div className="h-48"><ResponsiveContainer width="100%" height="100%">{type === 'line' ? <LineChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension" tick={{fill:colors.muted,fontSize:11}}/><YAxis tick={{fill:colors.muted,fontSize:11}}/><Tooltip/><Line dataKey="value" stroke={theme.primary} strokeWidth={3}/></LineChart> : <BarChart data={data}><CartesianGrid stroke={colors.grid} strokeOpacity={0.15}/><XAxis dataKey="dimension" tick={{fill:colors.muted,fontSize:11}}/><YAxis tick={{fill:colors.muted,fontSize:11}}/><Tooltip/><Bar dataKey="value" fill={theme.primary} radius={[6,6,0,0]}/></BarChart>}</ResponsiveContainer></div>}
  </section>;
