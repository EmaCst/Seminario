import {
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { DashboardContext } from '../context/DashboardContext';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

import { getDashboard } from '../services/api';


const CustomTooltip = ({
  active,
  payload,
  label,
  colors,
}) => {
  if (!active || !payload?.length) return null;

  return (
    <div
      className="rounded-lg border px-3 py-2 text-sm shadow-lg"
      style={{
        backgroundColor: colors.card,
        borderColor: colors.border,
        color: colors.text,
      }}
    >
      <div className="font-semibold">{label}</div>

      <div style={{ color: colors.muted }}>
        {payload[0].value}
      </div>
    </div>
  );
};


export const DashboardView = () => {
  const {
    visibleCharts,
    theme,
    colors,
    t,
    language,
  } = useContext(DashboardContext);

  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);


  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        const data = await getDashboard();

        setDashboard(data);
      } catch (err) {
        console.error(
          'Error cargando dashboard:',
          err
        );

        setError(
          language === 'es'
            ? 'No se pudieron cargar los datos del dashboard.'
            : 'Dashboard data could not be loaded.'
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [language]);


  const monthNames = useMemo(() => {
    return language === 'es'
      ? [
          'Ene',
          'Feb',
          'Mar',
          'Abr',
          'May',
          'Jun',
          'Jul',
          'Ago',
          'Sep',
          'Oct',
          'Nov',
          'Dic',
        ]
      : [
          'Jan',
          'Feb',
          'Mar',
          'Apr',
          'May',
          'Jun',
          'Jul',
          'Aug',
          'Sep',
          'Oct',
          'Nov',
          'Dec',
        ];
  }, [language]);


  const salesByMonth = useMemo(() => {
    if (!dashboard?.sales_by_month?.data) {
      return [];
    }

    return dashboard.sales_by_month.data.map(
      (item) => ({
        name: `${monthNames[item.month - 1]} ${item.year}`,
        sales: item.total,
      })
    );
  }, [dashboard, monthNames]);


  const topProducts = useMemo(() => {
    return dashboard?.top_products?.data || [];
  }, [dashboard]);


  const criticalInventory = useMemo(() => {
    return dashboard?.critical_inventory?.data || [];
  }, [dashboard]);


  const topCustomers = useMemo(() => {
    return dashboard?.top_customers?.data || [];
  }, [dashboard]);


  const salesByCategory = useMemo(() => {
    return dashboard?.sales_by_category?.data || [];
  }, [dashboard]);


  const cardStyle = {
    backgroundColor: colors.card,
    borderColor: colors.border,
  };


  const formatMoney = (value) => {
    return Number(value || 0).toLocaleString(
      language === 'es' ? 'es-GT' : 'en-US',
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }
    );
  };


  if (loading) {
    return (
      <div
        className="p-6"
        style={{ color: colors.text }}
      >
        {language === 'es'
          ? 'Cargando dashboard...'
          : 'Loading dashboard...'}
      </div>
    );
  }


  if (error) {
    return (
      <div
        className="p-6"
        style={{ color: colors.text }}
      >
        {error}
      </div>
    );
  }


  return (
    <div className="space-y-6">

      <h2
        className="text-3xl md:text-4xl font-extrabold tracking-tight"
        style={{ color: theme.primary }}
      >
        {t.dashboard}
      </h2>


      {/* ======================================
          KPIs PRINCIPALES
      ====================================== */}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">

        {dashboard?.total_sales?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm"
            style={cardStyle}
          >
            <div
              className="text-sm font-semibold"
              style={{ color: colors.muted }}
            >
              {language === 'es'
                ? 'Ventas totales'
                : 'Total sales'}
            </div>

            <div
              className="text-2xl font-extrabold mt-1"
              style={{ color: theme.primary }}
            >
              {formatMoney(
                dashboard.total_sales.value
              )}
            </div>
          </section>
        )}


        {dashboard?.current_month_sales?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm"
            style={cardStyle}
          >
            <div
              className="text-sm font-semibold"
              style={{ color: colors.muted }}
            >
              {language === 'es'
                ? 'Ventas del mes'
                : 'Current month sales'}
            </div>

            <div
              className="text-2xl font-extrabold mt-1"
              style={{ color: theme.primary }}
            >
              {formatMoney(
                dashboard.current_month_sales.value
              )}
            </div>
          </section>
        )}


        {dashboard?.sales_count?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm"
            style={cardStyle}
          >
            <div
              className="text-sm font-semibold"
              style={{ color: colors.muted }}
            >
              {language === 'es'
                ? 'Cantidad de ventas'
                : 'Sales count'}
            </div>

            <div
              className="text-2xl font-extrabold mt-1"
              style={{ color: theme.primary }}
            >
              {dashboard.sales_count.value}
            </div>
          </section>
        )}


        {dashboard?.average_ticket?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm"
            style={cardStyle}
          >
            <div
              className="text-sm font-semibold"
              style={{ color: colors.muted }}
            >
              {language === 'es'
                ? 'Venta promedio'
                : 'Average sale'}
            </div>

            <div
              className="text-2xl font-extrabold mt-1"
              style={{ color: theme.primary }}
            >
              {formatMoney(
                dashboard.average_ticket.value
              )}
            </div>
          </section>
        )}

      </div>


      {/* ======================================
          VENTAS POR MES / TOP PRODUCTOS
      ====================================== */}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 lg:gap-6">

        {visibleCharts.monthSales &&
          dashboard?.sales_by_month?.available && (

          <section
            className="p-5 rounded-2xl border shadow-sm h-72"
            style={cardStyle}
          >
            <h3
              className="font-bold mb-3"
              style={{ color: theme.primary }}
            >
              {t.monthSales}
            </h3>

            <ResponsiveContainer
              width="100%"
              height="82%"
            >
              <LineChart
                data={salesByMonth}
                margin={{
                  top: 5,
                  right: 18,
                  left: -15,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  stroke={colors.grid}
                  strokeOpacity={0.15}
                  vertical={false}
                />

                <XAxis
                  dataKey="name"
                  stroke={colors.muted}
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                />

                <YAxis
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip
                  content={
                    <CustomTooltip
                      colors={colors}
                    />
                  }
                />

                <Line
                  type="monotone"
                  dataKey="sales"
                  stroke={theme.primary}
                  strokeWidth={3}
                  dot={{
                    r: 4,
                    fill: theme.primary,
                    strokeWidth: 0,
                  }}
                />

              </LineChart>
            </ResponsiveContainer>
          </section>
        )}


        {dashboard?.top_products?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm h-72"
            style={cardStyle}
          >
            <h3
              className="font-bold mb-3"
              style={{ color: theme.primary }}
            >
              {language === 'es'
                ? 'Productos más vendidos'
                : 'Top products'}
            </h3>

            <ResponsiveContainer
              width="100%"
              height="82%"
            >
              <BarChart
                data={topProducts}
                margin={{
                  top: 5,
                  right: 18,
                  left: -15,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  stroke={colors.grid}
                  strokeOpacity={0.15}
                  vertical={false}
                />

                <XAxis
                  dataKey="product"
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                />

                <YAxis
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip
                  content={
                    <CustomTooltip
                      colors={colors}
                    />
                  }
                />

                <Bar
                  dataKey="quantity"
                  fill={theme.primary}
                  radius={[7, 7, 0, 0]}
                />

              </BarChart>
            </ResponsiveContainer>

          </section>
        )}

      </div>


      {/* ======================================
          TOP CLIENTES / VENTAS POR CATEGORÍA
      ====================================== */}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 lg:gap-6">

        {dashboard?.top_customers?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm h-72"
            style={cardStyle}
          >
            <h3
              className="font-bold mb-3"
              style={{ color: theme.primary }}
            >
              {language === 'es'
                ? 'Principales clientes'
                : 'Top customers'}
            </h3>

            <ResponsiveContainer
              width="100%"
              height="82%"
            >
              <BarChart
                data={topCustomers}
              >
                <CartesianGrid
                  stroke={colors.grid}
                  strokeOpacity={0.15}
                  vertical={false}
                />

                <XAxis
                  dataKey="customer"
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                />

                <YAxis
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip
                  content={
                    <CustomTooltip
                      colors={colors}
                    />
                  }
                />

                <Bar
                  dataKey="total_spent"
                  fill={theme.primary}
                  radius={[7, 7, 0, 0]}
                />

              </BarChart>
            </ResponsiveContainer>
          </section>
        )}


        {dashboard?.sales_by_category?.available && (
          <section
            className="p-5 rounded-2xl border shadow-sm h-72"
            style={cardStyle}
          >
            <h3
              className="font-bold mb-3"
              style={{ color: theme.primary }}
            >
              {language === 'es'
                ? 'Ventas por categoría'
                : 'Sales by category'}
            </h3>

            <ResponsiveContainer
              width="100%"
              height="82%"
            >
              <BarChart
                data={salesByCategory}
              >
                <CartesianGrid
                  stroke={colors.grid}
                  strokeOpacity={0.15}
                  vertical={false}
                />

                <XAxis
                  dataKey="category"
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                />

                <YAxis
                  tick={{
                    fill: colors.muted,
                    fontSize: 12,
                  }}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip
                  content={
                    <CustomTooltip
                      colors={colors}
                    />
                  }
                />

                <Bar
                  dataKey="total"
                  fill={theme.primary}
                  radius={[7, 7, 0, 0]}
                />

              </BarChart>
            </ResponsiveContainer>
          </section>
        )}

      </div>


      {/* ======================================
          INVENTARIO CRÍTICO
      ====================================== */}

      {dashboard?.critical_inventory?.available && (
        <section
          className="rounded-2xl border shadow-sm overflow-hidden"
          style={cardStyle}
        >
          <div
            className="px-5 py-4 border-b"
            style={{
              borderColor: colors.border,
            }}
          >
            <h3
              className="font-bold"
              style={{ color: theme.primary }}
            >
              {language === 'es'
                ? 'Inventario crítico'
                : 'Critical inventory'}
            </h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[500px] text-sm">

              <thead
                style={{
                  backgroundColor: colors.cardSoft,
                  color: colors.muted,
                }}
              >
                <tr>
                  <th className="text-left px-5 py-3">
                    {language === 'es'
                      ? 'Producto'
                      : 'Product'}
                  </th>

                  <th className="text-left px-5 py-3">
                    Stock
                  </th>

                  <th className="text-left px-5 py-3">
                    {language === 'es'
                      ? 'Mínimo'
                      : 'Minimum'}
                  </th>
                </tr>
              </thead>

              <tbody style={{ color: colors.text }}>

                {criticalInventory.length === 0 ? (
                  <tr>
                    <td
                      colSpan="3"
                      className="px-5 py-5 text-center"
                    >
                      {language === 'es'
                        ? 'No hay productos con inventario crítico.'
                        : 'There are no products with critical inventory.'}
                    </td>
                  </tr>
                ) : (
                  criticalInventory.map((row) => (
                    <tr
                      key={row.product}
                      className="border-t"
                      style={{
                        borderColor: colors.border,
                      }}
                    >
                      <td className="px-5 py-3 font-medium">
                        {row.product}
                      </td>

                      <td className="px-5 py-3">
                        {row.stock}
                      </td>

                      <td className="px-5 py-3">
                        {row.minimum_stock}
                      </td>
                    </tr>
                  ))
                )}

              </tbody>
            </table>
          </div>
        </section>
      )}


      {/* ======================================
          TOP PRODUCTOS - TABLA
      ====================================== */}

      {visibleCharts.topProducts &&
        dashboard?.top_products?.available && (

        <section
          className="rounded-2xl border shadow-sm overflow-hidden"
          style={cardStyle}
        >

          <div
            className="px-5 py-4 border-b"
            style={{
              borderColor: colors.border,
            }}
          >
            <h3
              className="font-bold"
              style={{ color: theme.primary }}
            >
              {t.topProducts}
            </h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px] text-sm">

              <thead
                style={{
                  backgroundColor: colors.cardSoft,
                  color: colors.muted,
                }}
              >
                <tr>
                  <th className="text-left px-5 py-3">
                    {t.product}
                  </th>

                  <th className="text-left px-5 py-3">
                    {language === 'es'
                      ? 'Unidades vendidas'
                      : 'Units sold'}
                  </th>
                </tr>
              </thead>

              <tbody style={{ color: colors.text }}>

                {topProducts.map((row) => (
                  <tr
                    key={row.product}
                    className="border-t"
                    style={{
                      borderColor: colors.border,
                    }}
                  >
                    <td className="px-5 py-3 font-medium">
                      {row.product}
                    </td>

                    <td className="px-5 py-3">
                      {row.quantity}
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