import { useContext, useEffect, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Building2,
  Bus,
  Database,
  GraduationCap,
  HeartPulse,
  Hotel,
  PackageSearch,
  Utensils,
  Users,
  WalletCards,
  Wrench,
} from 'lucide-react';

import { DashboardContext } from '../context/DashboardContext';
import { getAdaptiveDashboard, getSemanticModel } from '../services/api';
import { DashboardView } from './DashboardView';

const DOMAIN_META = {
  retail: { es: 'Comercio / Retail', en: 'Retail / Commerce', Icon: PackageSearch },
  education: { es: 'Educación', en: 'Education', Icon: GraduationCap },
  healthcare: { es: 'Salud / Hospital', en: 'Healthcare / Hospital', Icon: HeartPulse },
  transportation: { es: 'Transporte / Aerolínea', en: 'Transportation / Airline', Icon: Bus },
  hospitality: { es: 'Hotelería', en: 'Hospitality', Icon: Hotel },
  restaurant: { es: 'Restaurante', en: 'Restaurant', Icon: Utensils },
  professional_services: { es: 'Servicios profesionales', en: 'Professional services', Icon: Wrench },
  finance_accounting: { es: 'Finanzas / Contabilidad', en: 'Finance / Accounting', Icon: WalletCards },
  manufacturing: { es: 'Manufactura', en: 'Manufacturing', Icon: Building2 },
  human_resources: { es: 'Recursos humanos', en: 'Human resources', Icon: Users },
};

const ROLE_LABELS = {
  patients: ['Pacientes', 'Patients'],
  doctors: ['Médicos', 'Doctors'],
  appointments: ['Citas / Consultas', 'Appointments / Visits'],
  admissions: ['Hospitalizaciones', 'Admissions'],
  treatments: ['Tratamientos', 'Treatments'],
  students: ['Estudiantes', 'Students'],
  teachers: ['Docentes', 'Teachers'],
  courses: ['Cursos / Materias', 'Courses / Subjects'],
  enrollments: ['Inscripciones / Matrículas', 'Enrollments'],
  grades: ['Calificaciones', 'Grades'],
  attendance: ['Asistencia', 'Attendance'],
  vehicles: ['Vehículos / Aeronaves', 'Vehicles / Aircraft'],
  drivers: ['Conductores / Tripulación', 'Drivers / Crew'],
  routes: ['Rutas', 'Routes'],
  trips: ['Viajes / Vuelos', 'Trips / Flights'],
  passengers: ['Pasajeros', 'Passengers'],
  tickets: ['Boletos / Tickets', 'Tickets'],
  rooms: ['Habitaciones', 'Rooms'],
  guests: ['Huéspedes', 'Guests'],
  reservations: ['Reservas', 'Reservations'],
  stays: ['Estadías', 'Stays'],
  menu_items: ['Platos / Menú', 'Menu items'],
  tables: ['Mesas', 'Tables'],
  orders: ['Órdenes', 'Orders'],
  ingredients: ['Ingredientes', 'Ingredients'],
  services: ['Servicios', 'Services'],
  clients: ['Clientes', 'Clients'],
  projects: ['Proyectos', 'Projects'],
  invoices: ['Facturas', 'Invoices'],
  payments: ['Pagos', 'Payments'],
  accounts: ['Cuentas', 'Accounts'],
  transactions: ['Transacciones', 'Transactions'],
  journal_entries: ['Asientos contables', 'Journal entries'],
  products: ['Productos', 'Products'],
  materials: ['Materiales', 'Materials'],
  machines: ['Maquinaria', 'Machines'],
  production_orders: ['Órdenes de producción', 'Production orders'],
  employees: ['Empleados', 'Employees'],
  departments: ['Departamentos', 'Departments'],
  payroll: ['Nómina', 'Payroll'],
};

const roleLabel = (role, language) => {
  const pair = ROLE_LABELS[role];
  if (!pair) return role?.replaceAll('_', ' ') || '-';
  return language === 'es' ? pair[0] : pair[1];
};

const confidenceLabel = (value, language) => {
  const labels = {
    high: ['Alta', 'High'],
    medium: ['Media', 'Medium'],
    low: ['Baja', 'Low'],
    insufficient: ['Insuficiente', 'Insufficient'],
  };
  const pair = labels[value] || [value || '-', value || '-'];
  return language === 'es' ? pair[0] : pair[1];
};

const monthNames = {
  es: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
};

const BusinessDashboard = ({ data }) => {
  const { theme, colors, language, t } = useContext(DashboardContext);
  const domain = data?.domain;
  const meta = DOMAIN_META[domain] || { es: domain || 'Desconocido', en: domain || 'Unknown', Icon: Database };
  const DomainIcon = meta.Icon;

  const trend = useMemo(() => {
    return (data?.trend?.data || []).map((item) => ({
      name: `${monthNames[language][item.month - 1]} ${item.year}`,
      total: item.total,
    }));
  }, [data, language]);

  const status = data?.status_distribution?.data || [];
  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border };

  return (
    <div className="space-y-6">
      <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
        {t.dashboard}
      </h2>

      <section className="rounded-2xl border p-5 shadow-sm" style={cardStyle}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
              <DomainIcon size={25} />
            </div>
            <div>
              <p className="text-sm" style={{ color: colors.muted }}>
                {language === 'es' ? 'Tipo de negocio detectado' : 'Detected business domain'}
              </p>
              <h3 className="text-2xl font-extrabold" style={{ color: colors.text }}>
                {language === 'es' ? meta.es : meta.en}
              </h3>
            </div>
          </div>
          <div className="rounded-xl border px-4 py-2 text-sm" style={{ borderColor: colors.border, backgroundColor: colors.cardSoft, color: colors.text }}>
            {language === 'es' ? 'Confianza' : 'Confidence'}: <strong>{confidenceLabel(data?.domain_confidence, language)}</strong>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {(data?.kpis || []).map((kpi) => (
          <section key={kpi.role} className="rounded-2xl border p-5 shadow-sm" style={cardStyle}>
            <div className="text-sm font-semibold" style={{ color: colors.muted }}>
              {roleLabel(kpi.role, language)}
            </div>
            <div className="mt-1 text-3xl font-extrabold" style={{ color: theme.primary }}>
              {Number(kpi.value || 0).toLocaleString()}
            </div>
            <div className="mt-1 text-xs" style={{ color: colors.muted }}>
              {language === 'es' ? 'Registros detectados' : 'Detected records'}
            </div>
          </section>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className="rounded-2xl border p-5 shadow-sm h-80" style={cardStyle}>
          <h3 className="font-bold mb-3" style={{ color: theme.primary }}>
            {data?.trend?.available
              ? `${roleLabel(data.trend.role, language)} ${language === 'es' ? 'por mes' : 'by month'}`
              : (language === 'es' ? 'Evolución mensual' : 'Monthly trend')}
          </h3>
          {data?.trend?.available && trend.length > 0 ? (
            <ResponsiveContainer width="100%" height="86%">
              <LineChart data={trend} margin={{ top: 5, right: 18, left: -15, bottom: 0 }}>
                <CartesianGrid stroke={colors.grid} strokeOpacity={0.15} vertical={false} />
                <XAxis dataKey="name" tick={{ fill: colors.muted, fontSize: 12 }} tickLine={false} />
                <YAxis tick={{ fill: colors.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
                <Tooltip />
                <Line type="monotone" dataKey="total" stroke={theme.primary} strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[86%] flex items-center justify-center text-center text-sm" style={{ color: colors.muted }}>
              {language === 'es'
                ? 'No hay una columna de fecha utilizable o todavía no existen registros.'
                : 'No usable date column was found or there are no records yet.'}
            </div>
          )}
        </section>

        <section className="rounded-2xl border p-5 shadow-sm h-80" style={cardStyle}>
          <h3 className="font-bold mb-3" style={{ color: theme.primary }}>
            {data?.status_distribution?.available
              ? `${roleLabel(data.status_distribution.role, language)} — ${language === 'es' ? 'distribución por estado' : 'status distribution'}`
              : (language === 'es' ? 'Distribución por estado' : 'Status distribution')}
          </h3>
          {data?.status_distribution?.available && status.length > 0 ? (
            <ResponsiveContainer width="100%" height="86%">
              <BarChart data={status} margin={{ top: 5, right: 18, left: -15, bottom: 0 }}>
                <CartesianGrid stroke={colors.grid} strokeOpacity={0.15} vertical={false} />
                <XAxis dataKey="label" tick={{ fill: colors.muted, fontSize: 12 }} tickLine={false} />
                <YAxis tick={{ fill: colors.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="total" fill={theme.primary} radius={[7, 7, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[86%] flex items-center justify-center text-center text-sm" style={{ color: colors.muted }}>
              {language === 'es'
                ? 'No se encontró una columna de estado utilizable o todavía no existen registros.'
                : 'No usable status column was found or there are no records yet.'}
            </div>
          )}
        </section>
      </div>

      <section className="overflow-hidden rounded-2xl border shadow-sm" style={cardStyle}>
        <div className="border-b px-5 py-4" style={{ borderColor: colors.border }}>
          <h3 className="font-bold" style={{ color: theme.primary }}>
            {language === 'es' ? 'Resumen de módulos del negocio' : 'Business modules summary'}
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead style={{ backgroundColor: colors.cardSoft, color: colors.muted }}>
              <tr>
                <th className="px-5 py-3 text-left">{language === 'es' ? 'Módulo' : 'Module'}</th>
                <th className="px-5 py-3 text-left">{language === 'es' ? 'Registros' : 'Records'}</th>
                <th className="px-5 py-3 text-left">{language === 'es' ? 'Tabla' : 'Table'}</th>
                <th className="px-5 py-3 text-left">{language === 'es' ? 'Confianza' : 'Confidence'}</th>
              </tr>
            </thead>
            <tbody style={{ color: colors.text }}>
              {(data?.entity_counts || []).map((item) => (
                <tr key={item.role} className="border-t" style={{ borderColor: colors.border }}>
                  <td className="px-5 py-3 font-medium">{roleLabel(item.role, language)}</td>
                  <td className="px-5 py-3">{Number(item.value || 0).toLocaleString()}</td>
                  <td className="px-5 py-3">{item.table}</td>
                  <td className="px-5 py-3">{confidenceLabel(item.confidence, language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export const UniversalDashboard = () => {
  const { colors, language } = useContext(DashboardContext);
  const [semantic, setSemantic] = useState(null);
  const [adaptive, setAdaptive] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const semanticData = await getSemanticModel();
        if (!active) return;
        setSemantic(semanticData);

        const domain = semanticData?.semantic_model?.domain || semanticData?.business_domain?.primary;
        if (domain === 'retail') {
          setAdaptive(null);
        } else {
          const adaptiveData = await getAdaptiveDashboard();
          if (active) setAdaptive(adaptiveData);
        }
        if (active) setError(null);
      } catch (err) {
        console.error('Error cargando dashboard universal:', err);
        if (active) setError(err.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => { active = false; };
  }, []);

  const domain = semantic?.semantic_model?.domain || semantic?.business_domain?.primary;

  if (loading) {
    return <div style={{ color: colors.text }}>{language === 'es' ? 'Analizando base de datos...' : 'Analyzing database...'}</div>;
  }

  if (error) {
    return <div style={{ color: colors.text }}>{error}</div>;
  }

  if (domain === 'retail') {
    return <DashboardView />;
  }

  if (!adaptive) {
    return (
      <div className="rounded-2xl border p-6" style={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.muted }}>
        {language === 'es'
          ? 'La base fue conectada, pero todavía no hay suficiente información para construir un dashboard.'
          : 'The database is connected, but there is not enough information to build a dashboard yet.'}
      </div>
    );
  }

  return <BusinessDashboard data={adaptive} />;
};
