import { useRef, useState } from 'react';
import { CheckCircle2, FileSpreadsheet, LoaderCircle, UploadCloud, X, AlertCircle } from 'lucide-react';
import { inspectExcel, uploadExcel } from '../services/api';

export const ExcelImport = ({ theme, colors, language }) => {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');

  const choose = async (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setError(language === 'es' ? 'Por ahora se admiten archivos .xlsx.' : 'Only .xlsx files are supported for now.');
      return;
    }
    setFile(selected); setPreview(null); setResult(null); setError(''); setLoading(true);
    try { setPreview(await inspectExcel(selected)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const activate = async () => {
    if (!file) return;
    setLoading(true); setError('');
    try { setResult(await uploadExcel(file)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const reset = () => { setFile(null); setPreview(null); setResult(null); setError(''); if (inputRef.current) inputRef.current.value=''; };
  const sheets = preview?.sheets || preview?.worksheets || preview?.tables || [];
  const domain = result?.business_domain?.primary || result?.business_domain || result?.domain;

  return <section className="p-5 sm:p-6 rounded-2xl border shadow-sm" style={{backgroundColor:colors.card,borderColor:colors.border}}>
    <div className="flex items-start gap-3 mb-5">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{backgroundColor:colors.accentSoft,color:theme.primary}}><FileSpreadsheet size={21}/></div>
      <div><h3 className="text-lg font-bold" style={{color:colors.text}}>{language==='es'?'Importar Excel':'Import Excel'}</h3><p className="text-sm" style={{color:colors.muted}}>{language==='es'?'Carga un libro .xlsx. El sistema interpreta sus hojas, activa los datos y ejecuta el análisis semántico automáticamente.':'Upload an .xlsx workbook. The system interprets its sheets, activates the data and runs semantic analysis automatically.'}</p></div>
    </div>

    {!file && <div onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);choose(e.dataTransfer.files?.[0])}} onClick={()=>inputRef.current?.click()} className="min-h-52 rounded-2xl border-2 border-dashed p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all" style={{borderColor:dragging?theme.primary:colors.border,backgroundColor:dragging?colors.accentSoft:colors.cardSoft}}>
      <UploadCloud size={36} style={{color:theme.primary}}/><div className="font-extrabold text-lg mt-3" style={{color:colors.text}}>{language==='es'?'Arrastra tu archivo Excel aquí':'Drop your Excel file here'}</div><div className="text-sm mt-1" style={{color:colors.muted}}>{language==='es'?'o haz clic para seleccionarlo · .xlsx':'or click to select it · .xlsx'}</div>
    </div>}
    <input ref={inputRef} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="hidden" onChange={e=>choose(e.target.files?.[0])}/>

    {file && <div className="rounded-2xl border p-4" style={{borderColor:colors.border,backgroundColor:colors.cardSoft}}>
      <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-3 min-w-0"><FileSpreadsheet style={{color:theme.primary}}/><div className="min-w-0"><div className="font-bold truncate" style={{color:colors.text}}>{file.name}</div><div className="text-xs" style={{color:colors.muted}}>{(file.size/1024).toFixed(1)} KB</div></div></div><button onClick={reset} className="p-2 rounded-lg"><X size={18}/></button></div>
      {loading && <div className="mt-4 flex items-center gap-2 text-sm font-semibold" style={{color:theme.primary}}><LoaderCircle className="animate-spin" size={18}/>{language==='es'?'Interpretando archivo...':'Interpreting workbook...'}</div>}
      {preview && !result && <div className="mt-4"><div className="text-sm font-bold mb-2" style={{color:colors.text}}>{language==='es'?'Archivo interpretado correctamente':'Workbook interpreted successfully'}</div><div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm"><div className="rounded-xl border p-3" style={{borderColor:colors.border}}><span style={{color:colors.muted}}>{language==='es'?'Hojas detectadas':'Detected sheets'}</span><div className="text-xl font-extrabold" style={{color:theme.primary}}>{preview.sheet_count ?? sheets.length ?? '—'}</div></div><div className="rounded-xl border p-3 col-span-1 sm:col-span-2" style={{borderColor:colors.border}}><span style={{color:colors.muted}}>{language==='es'?'Listo para':'Ready for'}</span><div className="font-bold" style={{color:colors.text}}>{language==='es'?'Activación + análisis semántico':'Activation + semantic analysis'}</div></div></div><button disabled={loading} onClick={activate} className="w-full mt-4 rounded-xl py-3 font-extrabold text-white" style={{backgroundColor:theme.primary}}>{language==='es'?'Usar este Excel y analizar':'Use this Excel and analyze'}</button></div>}
      {result && <div className="mt-4 rounded-xl border p-4" style={{borderColor:'#86efac',backgroundColor:'#f0fdf4'}}><div className="flex items-center gap-2 font-extrabold text-green-700"><CheckCircle2 size={20}/>{language==='es'?'Excel activado correctamente':'Excel activated successfully'}</div><div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3 text-sm"><div><span className="text-gray-500">{language==='es'?'Base activa':'Active source'}</span><div className="font-bold text-gray-900">{result.database || file.name}</div></div><div><span className="text-gray-500">{language==='es'?'Dominio':'Domain'}</span><div className="font-bold text-gray-900">{domain || '—'}</div></div><div><span className="text-gray-500">{language==='es'?'Tablas':'Tables'}</span><div className="font-bold text-gray-900">{result.tables?.length ?? result.table_count ?? '—'}</div></div></div><p className="text-xs text-green-800 mt-3">{language==='es'?'Dashboard, Analítica y Kenneth ya pueden trabajar con esta fuente activa.':'Dashboard, Analytics and Kenneth can now use this active source.'}</p></div>}
    </div>}
    {error && <div className="mt-4 rounded-xl border border-red-300 bg-red-50 text-red-700 p-3 flex gap-2 text-sm"><AlertCircle size={18} className="shrink-0"/><span>{error}</span></div>}
  </section>;
};
