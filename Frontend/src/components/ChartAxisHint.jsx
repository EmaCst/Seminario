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

