import { useContext, useMemo } from 'react';
import { DashboardContext } from '../context/DashboardContext';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, BarChart, Bar } from 'recharts';

const products = [
  { product: 'Producto A', sales: 256, stock: 45 },
  { product: 'Producto B', sales: 189, stock: 32 },
  { product: 'Producto C', sales: 145, stock: 28 },
];

const CustomTooltip = ({ active, payload, label, colors }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border px-3 py-2 text-sm shadow-lg" style={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.text }}>
      <div className="font-semibold">{label}</div>
      <div style={{ color: colors.muted }}>{payload[0].value}</div>
    </div>
  );
};

export const DashboardView = () => {
  const { visibleCharts, theme, colors, t, language } = useContext(DashboardContext);

  const sampleData = useMemo(() => {
    const months = language === 'es' ? ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun'] : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    const values = [210, 335, 390, 640, 515, 730];
    return months.map((name, index) => ({ name, sales: values[index] }));
  }, [language]);

  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border };

  return (
    <div className="space-y-6">
      <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
        {t.dashboard}
      </h2>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 lg:gap-6">
        {visibleCharts.monthSales && (
          <section className="p-5 rounded-2xl border shadow-sm h-72 transition-colors duration-300" style={cardStyle}>
            <h3 className="font-bold mb-3" style={{ color: theme.primary }}>{t.monthSales}</h3>
            <ResponsiveContainer width="100%" height="82%">
              <LineChart data={sampleData} margin={{ top: 5, right: 18, left: -15, bottom: 0 }}>
                <CartesianGrid stroke={colors.grid} strokeOpacity={0.15} vertical={false} />
                <XAxis dataKey="name" stroke={colors.muted} tick={{ fill: colors.muted, fontSize: 12 }} axisLine={{ stroke: colors.border }} tickLine={false} />
                <YAxis stroke={colors.muted} tick={{ fill: colors.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip colors={colors} />} />
                <Line type="monotone" dataKey="sales" stroke={theme.primary} strokeWidth={3} dot={{ r: 4, fill: theme.primary, strokeWidth: 0 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </section>
        )}

        {visibleCharts.salesPerMonth && (
          <section className="p-5 rounded-2xl border shadow-sm h-72 transition-colors duration-300" style={cardStyle}>
            <h3 className="font-bold mb-3" style={{ color: theme.primary }}>{t.salesPerMonth}</h3>
            <ResponsiveContainer width="100%" height="82%">
              <BarChart data={sampleData} margin={{ top: 5, right: 18, left: -15, bottom: 0 }}>
                <CartesianGrid stroke={colors.grid} strokeOpacity={0.15} vertical={false} />
                <XAxis dataKey="name" stroke={colors.muted} tick={{ fill: colors.muted, fontSize: 12 }} axisLine={{ stroke: colors.border }} tickLine={false} />
                <YAxis stroke={colors.muted} tick={{ fill: colors.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip colors={colors} />} />
                <Bar dataKey="sales" fill={theme.primary} radius={[7, 7, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>
        )}
      </div>

      {visibleCharts.topProducts && (
        <section className="rounded-2xl border shadow-sm overflow-hidden transition-colors duration-300" style={cardStyle}>
          <div className="px-5 py-4 border-b" style={{ borderColor: colors.border }}>
            <h3 className="font-bold" style={{ color: theme.primary }}>{t.topProducts}</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead style={{ backgroundColor: colors.cardSoft, color: colors.muted }}>
                <tr>
                  <th className="text-left px-5 py-3 font-semibold">{t.product}</th>
                  <th className="text-left px-5 py-3 font-semibold">{t.sales}</th>
                  <th className="text-left px-5 py-3 font-semibold">{t.stock}</th>
                  <th className="text-left px-5 py-3 font-semibold">{t.status}</th>
                </tr>
              </thead>
              <tbody style={{ color: colors.text }}>
                {products.map((row) => (
                  <tr key={row.product} className="border-t" style={{ borderColor: colors.border }}>
                    <td className="px-5 py-3 font-medium">{language === 'es' ? row.product : row.product.replace('Producto', 'Product')}</td>
                    <td className="px-5 py-3">{row.sales}</td>
                    <td className="px-5 py-3">{row.stock}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex px-2.5 py-1 rounded-full text-xs font-bold" style={{ color: theme.primaryStrong, backgroundColor: colors.accentSoft }}>
                        {t.active}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
