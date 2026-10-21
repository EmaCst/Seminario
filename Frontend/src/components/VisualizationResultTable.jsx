import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Search } from 'lucide-react';

/** All preview tables share consistent, labelled and accessible columns.
 * This is a bounded preview; searching and CSV export cover loaded rows only.
 */
export const VisualizationResultTable = ({
  preview, colors, language = 'es', compact = false, pageSize = 10,
}) => {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(null);
  const es = language === 'es';
  const rows = useMemo(() => preview?.data || [], [preview]);
  const definition = preview?.definition || {};
  const columns = useMemo(() => {
    if (preview?.meta?.columns?.length) return preview.meta.columns;
    if (definition.table_mode === 'detail' && definition.detail_columns?.length) {
      return definition.detail_columns.map((field, index) => ({
        key: `field_${index}`, label: field.column.replaceAll('_', ' '),
      }));
    }
    return [
      ...(definition.group_by ? [{
        key: 'dimension', label: definition.group_by.replaceAll('_', ' '),
      }] : []),
      { key: 'value', label: es ? 'Valor' : 'Value' },
    ];
  }, [preview, definition.group_by, definition.table_mode, definition.detail_columns, es]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    const subset = needle ? rows.filter(row =>
      columns.some(col => String(row[col.key] ?? '').toLocaleLowerCase().includes(needle))
    ) : [...rows];
    if (sort) {
      subset.sort((a, b) => {
        const av = a[sort.key], bv = b[sort.key];
        if (av == null) return 1;
        if (bv == null) return -1;
        const compared = typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv), language);
        return sort.desc ? -compared : compared;
      });
    }
    return subset;
  }, [rows, columns, search, sort, language]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const activePage = Math.min(page, pages);
  const current = filtered.slice((activePage - 1) * pageSize, activePage * pageSize);

  const exportPreview = () => {
    const safeCsv = value => {
      const text = value == null ? '' : String(value);
      // Formula injection prevention for spreadsheet viewers; numeric negatives
      // are actual numbers and can be left untouched.
      const safe = typeof value !== 'number' && /^[\s\t\r]*[=+\-@]/.test(text)
        ? `'${text}` : text;
      return '"' + safe.replaceAll('"', '""') + '"';
    };
    const lines = [
      columns.map(col => safeCsv(col.label)).join(','),
      ...filtered.map(row => columns.map(col => safeCsv(row[col.key])).join(',')),
    ];
    const blob = new Blob(['\ufeff', lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'kenneth_vista_previa.csv';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const display = value => value == null ? '—'
    : typeof value === 'number'
      ? value.toLocaleString(language === 'es' ? 'es-GT' : 'en-US', { maximumFractionDigits: 3 })
      : typeof value === 'boolean'
        ? (value ? (es ? 'Sí' : 'Yes') : 'No')
        : String(value);

  return (
    <div className="min-w-0 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg border px-2 py-1.5"
          style={{ borderColor: colors.border, color: colors.muted }}>
          <Search size={14} aria-hidden="true" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder={es ? 'Buscar en la vista previa' : 'Search loaded rows'}
            aria-label={es ? 'Buscar en la vista previa' : 'Search loaded rows'}
            className="min-w-0 flex-1 bg-transparent text-xs outline-none"
            style={{ color: colors.text }} />
        </label>
        <button type="button" onClick={exportPreview}
          disabled={!rows.length} aria-label={es ? 'Exportar vista previa en CSV' : 'Export preview to CSV'}
          className="flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs disabled:opacity-40"
          style={{ borderColor: colors.border, color: colors.text }}>
          <Download size={13} aria-hidden="true" /> CSV
        </button>
      </div>
      <div className={`overflow-auto rounded-lg border ${compact ? 'max-h-44' : 'max-h-80'}`}
        style={{ borderColor: colors.border }}>
        <table className="w-full min-w-[250px] border-collapse text-xs">
          <thead className="sticky top-0 z-10" style={{ backgroundColor: colors.card }}>
            <tr>{columns.map(col => (
              <th key={col.key} scope="col" className="border-b px-2 py-2 text-left font-bold"
                style={{ borderColor: colors.border, color: colors.text }}>
                <button type="button" className="flex items-center gap-1 text-left"
                  onClick={() => {
                    setSort(old => ({ key: col.key, desc: old?.key === col.key ? !old.desc : false }));
                    setPage(1);
                  }}>
                  {col.label} {sort?.key === col.key ? (sort.desc ? '↓' : '↑') : ''}
                </button>
              </th>
            ))}</tr>
          </thead>
          <tbody>
            {current.map((row, index) => (
              <tr key={index} className="border-b last:border-b-0" style={{ borderColor: colors.border }}>
                {columns.map(col => (
                  <td key={col.key} className="max-w-[320px] break-words px-2 py-2"
                    style={{ color: colors.text }}>{display(row[col.key])}</td>
                ))}
              </tr>
            ))}
            {!current.length && (
              <tr><td colSpan={columns.length} className="px-3 py-5 text-center"
                style={{ color: colors.muted }}>
                {es ? 'No hay resultados que coincidan.' : 'No matching results.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between gap-2 text-[11px]" style={{ color: colors.muted }}>
        <span>
          {filtered.length} {es ? 'filas cargadas' : 'loaded rows'}
          {preview?.meta?.limited ? ` · ${es ? 'máximo' : 'max'} ${preview.meta.limit || definition.limit}` : ''}
        </span>
        {pages > 1 && (
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setPage(Math.max(1, activePage - 1))}
              disabled={activePage === 1} aria-label={es ? 'Página anterior' : 'Previous page'}>
              <ChevronLeft size={16} />
            </button>
            <span>{activePage}/{pages}</span>
            <button type="button" onClick={() => setPage(Math.min(pages, activePage + 1))}
              disabled={activePage === pages} aria-label={es ? 'Página siguiente' : 'Next page'}>
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
