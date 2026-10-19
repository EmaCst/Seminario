/** Small, consistent axis descriptions for existing and future Kenneth charts. */
export const ChartAxisHint = ({
  x, y, language = 'es', colors, horizontal = false, className = '',
}) => {
  if (!x || !y) return null;
  const xLabel = horizontal ? y : x;
  const yLabel = horizontal ? x : y;
  return (
    <p className={`min-w-0 break-words text-[11px] leading-4 ${className}`}
      style={{ color: colors?.muted || 'inherit' }}
      aria-label={language === 'es'
        ? `Eje horizontal: ${xLabel}. Eje vertical: ${yLabel}.`
        : `Horizontal axis: ${xLabel}. Vertical axis: ${yLabel}.`}>
      <span>{language === 'es' ? 'Eje X' : 'X axis'}: {xLabel}</span>
      <span aria-hidden="true"> · </span>
      <span>{language === 'es' ? 'Eje Y' : 'Y axis'}: {yLabel}</span>
    </p>
  );
};

/** Resolve semantic catalog field names; never present raw SQL column IDs if labels exist. */
export const visualizationAxisLabels = (definition, catalog, language = 'es') => {
  const isSpanish = language === 'es';
  const entityFor = (table) => (catalog?.entities || []).find(entity => entity.table === table);
  const dimensionEntity = entityFor(definition?.group_by_table || definition?.table);
  const metricEntity = entityFor(definition?.metric_table || definition?.table);
  const dimension = dimensionEntity?.dimensions?.find(field => field.key === definition?.group_by);
  const metric = metricEntity?.metrics?.find(field => field.key === definition?.metric);
  const aggregation = definition?.aggregation || 'count';
  const aggregationNames = {
    count: isSpanish ? 'Cantidad de registros' : 'Record count',
    sum: isSpanish ? 'Suma' : 'Sum',
    avg: isSpanish ? 'Promedio' : 'Average',
    min: isSpanish ? 'Mínimo' : 'Minimum',
    max: isSpanish ? 'Máximo' : 'Maximum',
  };
  return {
    x: dimension?.label || definition?.group_by || (isSpanish ? 'Categoría' : 'Category'),
    y: aggregation === 'count'
      ? aggregationNames.count
      : `${aggregationNames[aggregation] || aggregation} · ${metric?.label || definition?.metric || (isSpanish ? 'valor' : 'value')}`,
  };
};
