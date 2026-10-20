import { useContext, useEffect, useMemo, useState } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { exploreVisualization } from '../services/api';

export const TableExplorer = ({ definition }) => {
  const { colors, language } = useContext(DashboardContext);
  const es = language === 'es';
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('value');
  const [descending, setDescending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (!active) return null;
      setLoading(true);
      setError('');
      return exploreVisualization(definition, {
        page, page_size: 25, search, sort_by: sortBy, descending,
      });
    }).then(data => {
      if (active && data) setResult(data);
    }).catch(err => {
      if (active) setError(err.message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [definition, page, search, sortBy, descending]);

  const columns = (result?.columns || []).map(item =>
    typeof item === 'string'
      ? { key: item, label: item.replaceAll('_', ' ') }
      : item
  );
  const total = Number(result?.total || 0);
  const pages = Math.max(1, Math.ceil(total / 25));

  return <div className="flex h-full min-h-0 flex-col gap-3" style={{ color: colors.text }}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-bold">{definition.title}</h3>
      <span className="text-xs" style={{ color: colors.muted }}>
        {es ? 'Consulta paginada de la base activa' : 'Paginated active database query'}
      </span>
    </div>
    <input type="search" className="w-full rounded-lg border p-2 text-sm"
      style={{ color: colors.text, backgroundColor: colors.card, borderColor: colors.border }}
      aria-label={es ? 'Buscar en todos los resultados' : 'Search all matching rows'}
      placeholder={es ? 'Buscar en todos los resultados...' : 'Search all matching rows...'}
      value={search} onChange={event => {
        setSearch(event.target.value);
        setPage(1);
      }} />
    {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
    {loading && <p className="text-xs" style={{ color: colors.muted }}>
      {es ? 'Consultando registros...' : 'Fetching rows...'}
    </p>}
    <div className="min-h-0 flex-1 overflow-auto rounded-xl border" style={{ borderColor: colors.border }}>
      <table className="w-full min-w-[350px] text-sm">
        <thead className="sticky top-0" style={{ backgroundColor: colors.card }}>
          <tr>{columns.map(column => (
            <th className="border-b p-3 text-left" style={{ borderColor: colors.border }} key={column.key}>
              <button type="button" onClick={() => {
                setDescending(sortBy === column.key ? !descending : false);
                setSortBy(column.key);
                setPage(1);
              }} className="flex items-center gap-1 font-semibold">
                {column.label}
                {sortBy === column.key ? (descending ? '↓' : '↑') : ''}
              </button>
            </th>
          ))}</tr>
        </thead>
        <tbody>
          {(result?.data || []).map((row, i) => (
            <tr key={i} className="border-t" style={{ borderColor: colors.border }}>
              {columns.map(column => (
                <td className="max-w-[280px] break-words p-3" key={column.key}>
                  {String(row[column.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
          {!loading && !result?.data?.length && (
            <tr><td colSpan={Math.max(columns.length, 1)} className="p-6 text-center"
              style={{ color: colors.muted }}>
              {es ? 'No se encontraron registros.' : 'No matching rows.'}
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <span style={{ color: colors.muted }}>
        {total ? (page - 1) * 25 + 1 : 0}–{Math.min(page * 25, total)} {es ? 'de' : 'of'} {total}
      </span>
      <div className="flex items-center gap-3">
        <button type="button" disabled={loading || page <= 1}
          className="disabled:opacity-40" onClick={() => setPage(p => p - 1)}>
          {es ? 'Anterior' : 'Previous'}
        </button>
        <span>{page}/{pages}</span>
        <button type="button" disabled={loading || page >= pages}
          className="disabled:opacity-40" onClick={() => setPage(p => p + 1)}>
          {es ? 'Siguiente' : 'Next'}
        </button>
      </div>
    </div>
  </div>;
};

export const AutomaticTableExplorer = ({ table }) => {
  const [search, setSearch] = useState('');
  const [remoteRows, setRemoteRows] = useState(null);
  const [remoteError, setRemoteError] = useState('');
  const [remoteLoading, setRemoteLoading] = useState(Boolean(table.loadAll));
  const loadAll = table.loadAll;
  useEffect(() => {
    if (!loadAll) return;
    let active = true;
    // Schedule the loading state outside the synchronous effect body.
    Promise.resolve().then(() => {
      if (!active) return null;
      setRemoteLoading(true);
      setRemoteError('');
      setRemoteRows(null);
      return loadAll();
    }).then(result => {
      if (!active) return;
      if (!Array.isArray(result)) throw new Error('El servidor no devolvió una lista válida.');
      setRemoteRows(result);
    }).catch(error => { if (active) setRemoteError(error.message); })
      .finally(() => { if (active) setRemoteLoading(false); });
    return () => { active = false; };
  }, [loadAll]);
  const [sortBy, setSortBy] = useState(table.columns[0]?.key || '');
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(1);
  const rows = useMemo(() => {
    const term = search.toLocaleLowerCase();
    return [...(table.loadAll ? (remoteRows || []) : (table.rows || []))].filter(row => !term || table.columns.some(col => String(row[col.key] ?? '').toLocaleLowerCase().includes(term)))
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
    {remoteLoading && <p className="text-sm opacity-70">Consultando todos los registros en la base de datos...</p>}
    {remoteError && <p role="alert" className="text-sm text-red-600">No se pudo cargar la tabla completa: {remoteError}</p>}
    {table.loadAll && !remoteLoading && !remoteError && <p className="text-xs opacity-70">Listado completo consultado desde la base de datos.</p>}
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
