import { useContext, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Building2,
  Bus,
  Database,
  GraduationCap,
  HeartPulse,
  Hotel,
  Layers3,
  PackageSearch,
  Route,
  Stethoscope,
  TableProperties,
  Utensils,
  Users,
  WalletCards,
  Wrench,
} from 'lucide-react';

import { DashboardContext } from '../context/DashboardContext';
import { getSemanticModel } from '../services/api';
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
  diagnoses: ['Diagnósticos', 'Diagnoses'],
  treatments: ['Tratamientos', 'Treatments'],
  prescriptions: ['Recetas', 'Prescriptions'],
  admissions: ['Admisiones', 'Admissions'],
  students: ['Estudiantes', 'Students'],
  teachers: ['Docentes', 'Teachers'],
  courses: ['Cursos / Materias', 'Courses / Subjects'],
  enrollments: ['Inscripciones', 'Enrollments'],
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
  menu_items: ['Menú / Platos', 'Menu items'],
  tables: ['Mesas', 'Tables'],
  orders: ['Órdenes', 'Orders'],
  order_details: ['Detalle de órdenes', 'Order details'],
  ingredients: ['Ingredientes', 'Ingredients'],
  services: ['Servicios', 'Services'],
  clients: ['Clientes', 'Clients'],
  projects: ['Proyectos / Trabajos', 'Projects / Jobs'],
  invoices: ['Facturas', 'Invoices'],
  payments: ['Pagos', 'Payments'],
  accounts: ['Cuentas', 'Accounts'],
  transactions: ['Transacciones', 'Transactions'],
  journal_entries: ['Asientos contables', 'Journal entries'],
  products: ['Productos', 'Products'],
  materials: ['Materiales', 'Materials'],
  machines: ['Maquinaria', 'Machines'],
  production_orders: ['Órdenes de producción', 'Production orders'],
  inventory: ['Inventario', 'Inventory'],
  suppliers: ['Proveedores', 'Suppliers'],
  employees: ['Empleados', 'Employees'],
  payroll: ['Nómina', 'Payroll'],
  departments: ['Departamentos', 'Departments'],
  shifts: ['Turnos', 'Shifts'],
};

const roleLabel = (role, language) => {
  const pair = ROLE_LABELS[role];
  if (pair) return language === 'es' ? pair[0] : pair[1];
  return role.replaceAll('_', ' ');
};

const confidenceLabel = (confidence, language) => {
  const labels = {
    high: language === 'es' ? 'Alta' : 'High',
    medium: language === 'es' ? 'Media' : 'Medium',
    low: language === 'es' ? 'Baja' : 'Low',
    insufficient: language === 'es' ? 'Insuficiente' : 'Insufficient',
  };
  return labels[confidence] || confidence || '-';
};

const EntityCard = ({ role, entity, colors, theme, language }) => {
  const columns = Object.entries(entity.columns || {});

  return (
    <section
      className="rounded-2xl border p-5 shadow-sm"
      style={{ backgroundColor: colors.card, borderColor: colors.border }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-bold text-base" style={{ color: theme.primary }}>
            {roleLabel(role, language)}
          </p>
          <p className="mt-1 text-sm" style={{ color: colors.muted }}>
            {language === 'es' ? 'Tabla detectada:' : 'Detected table:'}{' '}
            <span className="font-semibold" style={{ color: colors.text }}>{entity.table}</span>
          </p>
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-xs font-bold"
          style={{ backgroundColor: colors.accentSoft, color: theme.primaryStrong || theme.primary }}
        >
          {confidenceLabel(entity.confidence, language)}
        </span>
      </div>

      {columns.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {columns.map(([semanticName, column]) => (
            <span
              key={`${role}-${semanticName}`}
              className="rounded-lg border px-2.5 py-1.5 text-xs"
              style={{ borderColor: colors.border, backgroundColor: colors.cardSoft, color: colors.text }}
            >
              <strong>{semanticName}</strong>: {column}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-xs" style={{ color: colors.muted }}>
          {language === 'es'
            ? 'La entidad fue reconocida, pero aún no se mapearon columnas principales.'
            : 'The entity was recognized, but no main columns have been mapped yet.'}
        </p>
      )}
    </section>
  );
};

const AdaptiveDashboard = ({ analysis }) => {
  const { theme, colors, language, t } = useContext(DashboardContext);
  const semantic = analysis?.semantic_model || {};
  const entities = Object.entries(semantic.entities || {});
  const relations = semantic.relations || [];
  const unmapped = semantic.unmapped_tables || [];
  const domain = semantic.domain || analysis?.business_domain?.primary;
  const meta = DOMAIN_META[domain] || { es: domain || 'Desconocido', en: domain || 'Unknown', Icon: Database };
  const DomainIcon = meta.Icon;

  return (
    <div className="space-y-6">
      <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: theme.primary }}>
        {t.dashboard}
      </h2>

      <section
        className="rounded-2xl border p-5 sm:p-6 shadow-sm"
        style={{ backgroundColor: colors.card, borderColor: colors.border }}
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
              style={{ backgroundColor: colors.accentSoft, color: theme.primary }}
            >
              <DomainIcon size={25} />
            </div>
            <div>
              <p className="text-sm font-semibold" style={{ color: colors.muted }}>
                {language === 'es' ? 'Tipo de negocio detectado' : 'Detected business domain'}
              </p>
              <h3 className="mt-1 text-2xl font-extrabold" style={{ color: colors.text }}>
                {language === 'es' ? meta.es : meta.en}
              </h3>
              <p className="mt-1 text-sm" style={{ color: colors.muted }}>
                {language === 'es'
                  ? 'El dashboard se está adaptando a las entidades encontradas en esta base de datos.'
                  : 'The dashboard is adapting to the entities detected in this database.'}
              </p>
            </div>
          </div>
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: colors.border, backgroundColor: colors.cardSoft, color: colors.text }}
          >
            <span style={{ color: colors.muted }}>{language === 'es' ? 'Confianza:' : 'Confidence:'}</span>{' '}
            <strong>{confidenceLabel(semantic.domain_confidence || analysis?.business_domain?.confidence, language)}</strong>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { Icon: Layers3, value: entities.length, labelEs: 'Entidades reconocidas', labelEn: 'Recognized entities' },
          { Icon: Route, value: relations.length, labelEs: 'Relaciones detectadas', labelEn: 'Detected relationships' },
          { Icon: TableProperties, value: unmapped.length, labelEs: 'Tablas sin mapear', labelEn: 'Unmapped tables' },
        ].map(({ Icon, value, labelEs, labelEn }) => (
          <section key={labelEn} className="rounded-2xl border p-5 shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: colors.accentSoft, color: theme.primary }}>
                <Icon size={20} />
              </div>
              <div>
                <div className="text-2xl font-extrabold" style={{ color: theme.primary }}>{value}</div>
                <div className="text-sm" style={{ color: colors.muted }}>{language === 'es' ? labelEs : labelEn}</div>
              </div>
            </div>
          </section>
        ))}
      </div>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Activity size={20} style={{ color: theme.primary }} />
          <h3 className="text-lg font-bold" style={{ color: colors.text }}>
            {language === 'es' ? 'Módulos disponibles' : 'Available modules'}
          </h3>
        </div>

        {entities.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {entities.map(([role, entity]) => (
              <EntityCard
                key={role}
                role={role}
                entity={entity}
                colors={colors}
                theme={theme}
                language={language}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border p-6 text-center" style={{ backgroundColor: colors.card, borderColor: colors.border, color: colors.muted }}>
            {language === 'es'
              ? 'La base fue conectada, pero todavía no se reconocieron entidades con suficiente confianza.'
              : 'The database is connected, but no entities have been recognized with enough confidence yet.'}
          </div>
        )}
      </section>

      {relations.length > 0 && (
        <section className="overflow-hidden rounded-2xl border shadow-sm" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
          <div className="border-b px-5 py-4" style={{ borderColor: colors.border }}>
            <h3 className="font-bold" style={{ color: theme.primary }}>
              {language === 'es' ? 'Relaciones semánticas' : 'Semantic relationships'}
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead style={{ backgroundColor: colors.cardSoft, color: colors.muted }}>
                <tr>
                  <th className="px-5 py-3 text-left">{language === 'es' ? 'Origen' : 'Source'}</th>
                  <th className="px-5 py-3 text-left">{language === 'es' ? 'Columna' : 'Column'}</th>
                  <th className="px-5 py-3 text-left">{language === 'es' ? 'Destino' : 'Target'}</th>
                  <th className="px-5 py-3 text-left">{language === 'es' ? 'Columna' : 'Column'}</th>
                </tr>
              </thead>
              <tbody style={{ color: colors.text }}>
                {relations.map((relation, index) => (
                  <tr key={`${relation.from_table}-${relation.to_table}-${index}`} className="border-t" style={{ borderColor: colors.border }}>
                    <td className="px-5 py-3 font-medium">{relation.from_role ? roleLabel(relation.from_role, language) : relation.from_table}</td>
                    <td className="px-5 py-3">{relation.from_column}</td>
                    <td className="px-5 py-3 font-medium">{relation.to_role ? roleLabel(relation.to_role, language) : relation.to_table}</td>
                    <td className="px-5 py-3">{relation.to_column}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="rounded-2xl border p-5" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
        <div className="flex items-start gap-3">
          <Stethoscope size={20} style={{ color: theme.primary }} />
          <div>
            <p className="font-bold" style={{ color: colors.text }}>
              {language === 'es' ? 'Siguiente nivel del dashboard' : 'Next dashboard level'}
            </p>
            <p className="mt-1 text-sm" style={{ color: colors.muted }}>
              {language === 'es'
                ? 'Esta vista ya se adapta a la estructura. Cuando agreguemos datos, construiremos KPIs y gráficas específicas usando estas mismas entidades detectadas.'
                : 'This view already adapts to the schema. Once data is added, we will build domain-specific KPIs and charts from these detected entities.'}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

export const UniversalDashboard = () => {
  const { colors, language } = useContext(DashboardContext);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadSemanticModel() {
      try {
        setLoading(true);
        const data = await getSemanticModel();
        if (active) {
          setAnalysis(data);
          setError(null);
        }
      } catch (err) {
        console.error('Error cargando modelo semántico:', err);
        if (active) setError(err.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadSemanticModel();
    return () => { active = false; };
  }, []);

  const domain = useMemo(
    () => analysis?.semantic_model?.domain || analysis?.business_domain?.primary,
    [analysis]
  );

  if (loading) {
    return <div className="p-6" style={{ color: colors.text }}>{language === 'es' ? 'Analizando base de datos...' : 'Analyzing database...'}</div>;
  }

  // Si el análisis semántico todavía no está disponible, conservamos el dashboard
  // comercial anterior para no romper la experiencia existente.
  if (error || !analysis) {
    return <DashboardView />;
  }

  // Retail mantiene el dashboard comercial completo que ya funcionaba.
  if (domain === 'retail') {
    return <DashboardView />;
  }

  return <AdaptiveDashboard analysis={analysis} />;
};
