import { useEffect, useState } from 'react';
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
