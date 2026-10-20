import { Bar, BarChart, CartesianGrid, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CheckCheck, SlidersHorizontal } from 'lucide-react';
import { ChartAxisHint } from './ChartAxisHint';

const formatNumber = (value) => Number(value ?? 0).toLocaleString('es-GT', { maximumFractionDigits: 2 });

/** Read-only proposal. The only action is opening the existing manual editor. */
export const ChatVisualizationDraft = ({ draft, colors, theme, language, onReview }) => {
  const definition = draft?.definition;
  if (!definition) return null;
  const rows = (draft.preview?.data || []).slice(0, 12);
  const type = definition.visualization;
  const es = language === 'es';

  return (
    <section className="mt-3 min-w-0 overflow-hidden rounded-xl border p-3" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
      <p className="text-xs font-bold uppercase tracking-wide" style={{ color: theme.primary }}>
        {es ? 'Propuesta · aún no guardada' : 'Draft · not saved'}
      </p>
      <h3 className="mt-1 break-words text-sm font-extrabold" style={{ color: colors.text }}>
        {definition.title}
      </h3>
      <p className="mt-1 text-[11px]" style={{ color: colors.muted }}>
        {draft.source?.database || ''} · {definition.filters?.length || 0} {es ? 'filtros' : 'filters'} · {rows.length} {es ? 'resultados mostrados' : 'results shown'}
      </p>

      {['bar', 'line'].includes(type) && rows.length > 0 ? (
        <div className="mt-3 min-w-0">
          <ChartAxisHint className="mb-1" x={draft.axes?.x} y={draft.axes?.y} colors={colors} language={language} />
          <div className="h-44 min-w-0" role="img" aria-label={es ? 'Previsualización de los datos consultados' : 'Preview of queried data'}>
            <ResponsiveContainer width="100%" height="100%">
              {type === 'line' ? (
                <LineChart data={rows} margin={{ top: 6, right: 6, left: -20, bottom: 8 }}>
                  <CartesianGrid stroke={colors.border} strokeOpacity={0.35}/>
                  <XAxis dataKey="dimension" tick={{ fontSize: 9, fill: colors.muted }} interval="preserveStartEnd"/>
                  <YAxis tick={{ fontSize: 9, fill: colors.muted }}/>
                  <Tooltip/>
                  <Line dataKey="value" type="monotone" stroke={theme.primary} strokeWidth={2} dot={false}/>
                </LineChart>
              ) : (
                <BarChart data={rows} margin={{ top: 6, right: 6, left: -20, bottom: 8 }}>
                  <CartesianGrid stroke={colors.border} strokeOpacity={0.35}/>
                  <XAxis dataKey="dimension" tick={{ fontSize: 9, fill: colors.muted }} interval="preserveStartEnd"/>
                  <YAxis tick={{ fontSize: 9, fill: colors.muted }}/>
                  <Tooltip/>
                  <Bar dataKey="value" fill={theme.primary} radius={[4, 4, 0, 0]}/>
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>
      ) : type === 'donut' && rows.length ? (
        <div className="mt-2 h-44" role="img" aria-label={es ? 'Distribución previa' : 'Distribution preview'}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={rows} dataKey="value" nameKey="dimension" cx="50%" cy="50%" outerRadius={65} fill={theme.primary} label={false}/>
              <Tooltip/>
            </PieChart>
          </ResponsiveContainer>
          <p className="text-[11px]" style={{ color: colors.muted }}>
            {es ? 'Categoría' : 'Category'}: {draft.axes?.x} · {es ? 'Valor' : 'Value'}: {draft.axes?.y}
          </p>
        </div>
      ) : type === 'kpi' && rows.length ? (
        <div className="my-4 text-center text-3xl font-black" style={{ color: theme.primary }}>
          {formatNumber(rows[0].value)}
        </div>
      ) : type === 'table' && rows.length ? (
        <div className="mt-3 max-h-44 overflow-auto rounded-lg border" style={{ borderColor: colors.border }}>
          <table className="w-full text-xs">
            <thead><tr>
              {definition.group_by && <th className="p-2 text-left">{draft.axes?.x}</th>}
              <th className="p-2 text-right">{draft.axes?.y}</th>
            </tr></thead>
            <tbody>{rows.map((item, i) => (
              <tr key={i} className="border-t" style={{ borderColor: colors.border }}>
                {definition.group_by && <td className="p-2">{String(item.dimension ?? '—')}</td>}
                <td className="p-2 text-right">{formatNumber(item.value)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-xs" style={{ color: colors.muted }}>
          {es ? 'No hay registros para los filtros solicitados. Puedes editarlos en el creador.' : 'No records match these filters. Edit them in the builder.'}
        </p>
      )}
      {draft.notes?.length > 0 && <p className="mt-2 text-[11px] leading-4" style={{ color: colors.muted }}>{draft.notes.join(' ')}</p>}
      <button type="button" onClick={onReview}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-bold text-white"
        style={{ backgroundColor: theme.primary }}>
        <SlidersHorizontal size={15} />
        {es ? 'Revisar y editar en el creador' : 'Review and edit in builder'}
      </button>
      <p className="mt-2 flex items-center gap-1 text-[11px]" style={{ color: colors.muted }}>
        <CheckCheck size={13}/>
        {es ? 'Solo se guardará cuando confirmes en el creador.' : 'Only saved after your confirmation in the builder.'}
      </p>
    </section>
  );
};
