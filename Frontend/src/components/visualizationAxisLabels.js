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
    x: definition?.time_granularity === 'month'
      ? (isSpanish ? 'Mes y año' : 'Month and year')
      : definition?.time_granularity === 'year'
        ? (isSpanish ? 'Año' : 'Year')
        : dimension?.label || definition?.group_by || (isSpanish ? 'Categoría' : 'Category'),
    y: aggregation === 'count'
      ? aggregationNames.count
      : `${aggregationNames[aggregation] || aggregation} · ${metric?.label || definition?.metric || (isSpanish ? 'valor' : 'value')}`,
  };
};
