import { useEffect, useMemo, useState } from 'react';
import { exploreVisualization } from '../services/api';

export const TableExplorer = ({ definition }) => {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('value');
  const [descending, setDescending] = useState(true);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    exploreVisualization(definition, { page, page_size: 25, search, sort_by: sortBy, descending })
      .then(data => { if (active) { setResult(data); setError(''); } })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [definition, page, search, sortBy, descending]);
  const columns = result?.columns || ['dimension', 'value'];
  const total = Number(result?.total || 0);
  return <div className="flex h-full min-h-0 flex-col gap-3">
    <h3 className="font-bold">{definition.title}</h3>
    {definition.group_by && <input className="rounded-lg border p-2" placeholder="Buscar..." value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} />}
    {error && <p className="text-red-500">{error}</p>}
    <div className="min-h-0 flex-1 overflow-auto">
      <table className="w-full text-sm"><thead><tr>{columns.map(column => <th className="p-3 text-left" key={column}><button type="button" onClick={() => { setDescending(sortBy === column ? !descending : true); setSortBy(column); setPage(1); }}>{column === 'dimension' ? definition.group_by : definition.aggregation} {sortBy === column ? (descending ? '↓' : '↑') : ''}</button></th>)}</tr></thead><tbody>{(result?.data || []).map((row, i) => <tr key={i} className="border-t">{columns.map(column => <td className="p-3" key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table>
    </div>
    <div className="flex items-center justify-between gap-3 text-sm"><span>{total} resultados</span><div className="flex items-center gap-3"><button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Anterior</button><span>{page} / {Math.max(1, Math.ceil(total / 25))}</span><button disabled={page * 25 >= total} onClick={() => setPage(p => p + 1)}>Siguiente</button></div></div>
  </div>;
};

export const AutomaticTableExplorer = ({ table }) => {
  const [search, setSearch] = useState('');
  const [remoteRows, setRemoteRows] = useState(null);
  const [remoteError, setRemoteError] = useState('');
  useEffect(() => {
    if (!table.loadAll) return;
    let active = true;
    table.loadAll().then(result => { if (active) setRemoteRows(result); }).catch(error => { if (active) setRemoteError(error.message); });
    return () => { active = false; };
  }, [table.loadAll]);
  const [sortBy, setSortBy] = useState(table.columns[0]?.key || '');
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(1);
  const rows = useMemo(() => {
    const term = search.toLocaleLowerCase();
    return [...(remoteRows || table.rows || [])].filter(row => !term || table.columns.some(col => String(row[col.key] ?? '').toLocaleLowerCase().includes(term)))
      .sort((a, b) => {
        const x = a[sortBy], y = b[sortBy];
        const nx = Number(x), ny = Number(y);
        const result = x != null && y != null && String(x).trim() !== '' && String(y).trim() !== '' && Number.isFinite(nx) && Number.isFinite(ny)
          ? nx - ny : String(x ?? '').localeCompare(String(y ?? ''), undefined, {numeric:true});
        return descending ? -result : result;
      });
  }, [table, remoteRows, search, sortBy, descending]);
  const pages = Math.max(1, Math.ceil(rows.length / 25));
  return <div className="flex h-full min-h-0 flex-col gap-3">
    <h3 className="font-bold">{table.title}</h3>
    {table.loadAll && remoteRows === null && !remoteError && <p className="text-sm opacity-70">Consultando todos los registros...</p>}
    {remoteError && <p className="text-sm text-red-600">No se pudieron cargar los registros adicionales: {remoteError}</p>}
    <div className="flex flex-wrap items-center justify-between gap-2">
      <input className="rounded-lg border px-3 py-2 text-sm" placeholder="Buscar en la tabla..." value={search} onChange={e => {setSearch(e.target.value);setPage(1);}} />
      <span className="text-sm opacity-70">{rows.length} registros</span>
    </div>
    <div className="min-h-0 flex-1 overflow-auto">
      <table className="w-full text-sm"><thead className="sticky top-0 bg-white text-gray-800"><tr>{table.columns.map(col => <th key={col.key} className="px-3 py-3 text-left"><button type="button" onClick={() => {setDescending(sortBy===col.key?!descending:true);setSortBy(col.key);setPage(1);}}>{col.label} {sortBy===col.key?(descending?'↓':'↑'):''}</button></th>)}</tr></thead><tbody>{rows.slice((page-1)*25,page*25).map((row,i)=><tr key={i} className="border-t">{table.columns.map(col=><td key={col.key} className="px-3 py-3">{String(row[col.key] ?? '—')}</td>)}</tr>)}</tbody></table>
    </div>
    <div className="flex items-center justify-between text-sm"><span>{rows.length ? (page-1)*25+1 : 0}–{Math.min(page*25,rows.length)} de {rows.length}</span><div className="flex gap-4"><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Anterior</button><span>{page}/{pages}</span><button disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>Siguiente</button></div></div>
  </div>;
};
