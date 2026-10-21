// Defaults to the current origin, with explicit override for remote deployments.
const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const REVISION_HEADER = 'X-Kenneth-Source-Revision';
let activeRevision = null;
let activeIdentity = null;
let hasObservedSource = false;

export const SOURCE_CHANGED_MESSAGE = 'La fuente activa cambió. Se limpiaron los resultados anteriores; vuelve a intentar la consulta.';

const observeSource = (status) => {
  const nextRevision = status?.revision || null;
  const nextIdentity = status?.source_identity || null;
  if (!hasObservedSource || nextRevision !== activeRevision || nextIdentity !== activeIdentity) {
    hasObservedSource = true;
    activeRevision = nextRevision;
    activeIdentity = nextIdentity;
    window.dispatchEvent(new CustomEvent('kenneth-source-changed', {
      detail: { ...status, revision: nextRevision, source_identity: nextIdentity },
    }));
  }
  return status;
};

export async function getDatabaseStatus() {
  return observeSource(await parseResponse(await fetch(`${API_URL}/api/database/status`, {
    cache: 'no-store',
  })));
}

async function guardedFetch(url, options = {}) {
  const expected = activeRevision;
  const headers = new Headers(options.headers || {});
  if (expected) headers.set(REVISION_HEADER, expected);
  const response = await fetch(url, { ...options, headers, cache: 'no-store' });
  const current = response.headers.get(REVISION_HEADER);
  if ((current && current !== expected) || response.status === 409) {
    // The server has already switched, or the generation was rejected.
    await getDatabaseStatus().catch(() => {});
    throw new Error(SOURCE_CHANGED_MESSAGE);
  }
  if (expected !== activeRevision) throw new Error(SOURCE_CHANGED_MESSAGE);
  return response;
}

async function activationRequest(url, options = {}) {
  // A successfully activated source must invalidate all mounted data even
  // if its optional semantic analysis fails after the engine was replaced.
  try {
    return await parseResponse(await fetch(url, { ...options, cache: 'no-store' }));
  } finally {
    await getDatabaseStatus().catch(() => {});
  }
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || `Error HTTP: ${response.status}`);
  return data;
}

export async function askDatabase(question, history = []) { const response = await guardedFetch(`${API_URL}/ask-db`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, history }) }); return parseResponse(response); }
export async function getAllTopProducts() { return parseResponse(await guardedFetch(`${API_URL}/api/dashboard/top-products/all`)); }
export async function getDashboard() { return parseResponse(await guardedFetch(`${API_URL}/api/dashboard`)); }
export async function getAdaptiveDashboard() { return parseResponse(await guardedFetch(`${API_URL}/api/dashboard/adaptive`)); }
export async function getAdaptiveAnalytics() { return parseResponse(await guardedFetch(`${API_URL}/api/analytics/adaptive`)); }

export async function getForecast(horizon = 3) { return parseResponse(await guardedFetch(`${API_URL}/api/ai/forecast?horizon=${encodeURIComponent(horizon)}`)); }
export async function getAnomalies() { return parseResponse(await guardedFetch(`${API_URL}/api/ai/anomalies`)); }
export async function getBusinessDomain() { return parseResponse(await guardedFetch(`${API_URL}/api/database/domain`)); }
export async function getSemanticModel() { return parseResponse(await guardedFetch(`${API_URL}/api/database/semantic-model`)); }
export async function getVisualizationSemanticCatalog() { return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/semantic-catalog`)); }
export async function getVisualizationFilterValues(table, column, search = '') {
  const params = new URLSearchParams({ table, column, search });
  return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/filter-values?${params}`));
}
export async function exploreVisualization(definition, options = {}) { return postJson('/api/visualizations/explore', { definition, ...options }); }
export async function previewVisualization(definition) { return postJson('/api/visualizations/preview', definition); }
export async function getSavedVisualizations(destination = '') {
  const suffix = destination ? `?destination=${encodeURIComponent(destination)}` : '';
  return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/saved${suffix}`));
}
export async function updateSavedVisualization(id, definition, placement) {
  return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/saved/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ definition, placement }) }));
}
export async function updateVisualizationPlacement(id, placement) {
  return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/saved/${encodeURIComponent(id)}/placement`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(placement) }));
}
export async function deleteSavedVisualization(id) {
  return parseResponse(await guardedFetch(`${API_URL}/api/visualizations/saved/${encodeURIComponent(id)}`, { method: 'DELETE' }));
}
export async function saveVisualization(definition, placement) {
  return postJson('/api/visualizations/saved', { definition, placement });
}

export async function getReportOptions() {
  return parseResponse(await guardedFetch(`${API_URL}/api/reports/options`));
}
export async function previewConfiguredReport(configuration) {
  return postJson('/api/reports/preview', configuration);
}
export async function downloadConfiguredReport(configuration) {
  const response = await guardedFetch(`${API_URL}/api/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(configuration),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'No fue posible generar el documento PDF.');
  }
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await response.blob(), filename: match?.[1] || 'informe_kenneth.pdf' };
}

export async function downloadReportPdf(type) {
  const response = await guardedFetch(`${API_URL}/api/reports/pdf?type=${encodeURIComponent(type)}`);
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data?.detail || `Error HTTP: ${response.status}`); }
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await response.blob(), filename: match?.[1] || `reporte_${type}.pdf` };
}

async function postJson(path, config) {
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) };
  if (path === '/api/database/connect' || path === '/api/database/connect/postgresql') {
    return activationRequest(`${API_URL}${path}`, init);
  }
  return parseResponse(await guardedFetch(`${API_URL}${path}`, init));
}
export const testDatabaseConnection = (config) => postJson('/api/database/test', config);
export const connectDatabase = (config) => postJson('/api/database/connect', config);
export const testPostgreSQLConnection = (config) => postJson('/api/database/test/postgresql', config);
export const connectPostgreSQL = (config) => postJson('/api/database/connect/postgresql', config);

async function uploadFile(path, file) {
  const formData = new FormData();
  formData.append('file', file);
  const init = { method: 'POST', body: formData };
  if (path !== '/api/database/upload/excel/inspect') {
    return activationRequest(`${API_URL}${path}`, init);
  }
  return parseResponse(await guardedFetch(`${API_URL}${path}`, init));
}
export const uploadSqlServerBackup = (file) => uploadFile('/api/database/upload/sqlserver-bak', file);
export const uploadPostgreSQLBackup = (file) => uploadFile('/api/database/upload/postgresql-backup', file);
export const getPostgreSQLBackupSettings = async () => parseResponse(await guardedFetch(`${API_URL}/api/database/postgresql-backup/settings`));
export const setPostgreSQLBackupEnabled = async (enabled) => parseResponse(await guardedFetch(`${API_URL}/api/database/postgresql-backup/settings`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled }) }));
export const inspectExcel = (file) => uploadFile('/api/database/upload/excel/inspect', file);
export const uploadExcel = (file) => uploadFile('/api/database/upload/excel', file);
