const API_URL = 'http://127.0.0.1:8000';

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || `Error HTTP: ${response.status}`);
  return data;
}

export async function askDatabase(question, history = []) { const response = await fetch(`${API_URL}/ask-db`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, history }) }); return parseResponse(response); }
export async function getDashboard() { return parseResponse(await fetch(`${API_URL}/api/dashboard`)); }
export async function getAdaptiveDashboard() { return parseResponse(await fetch(`${API_URL}/api/dashboard/adaptive`)); }
export async function getAdaptiveAnalytics() { return parseResponse(await fetch(`${API_URL}/api/analytics/adaptive`)); }
export async function getDatabaseStatus() { return parseResponse(await fetch(`${API_URL}/api/database/status`)); }
export async function getForecast(horizon = 3) { return parseResponse(await fetch(`${API_URL}/api/ai/forecast?horizon=${encodeURIComponent(horizon)}`)); }
export async function getAnomalies() { return parseResponse(await fetch(`${API_URL}/api/ai/anomalies`)); }
export async function getBusinessDomain() { return parseResponse(await fetch(`${API_URL}/api/database/domain`)); }
export async function getSemanticModel() { return parseResponse(await fetch(`${API_URL}/api/database/semantic-model`)); }

export async function downloadReportPdf(type) {
  const response = await fetch(`${API_URL}/api/reports/pdf?type=${encodeURIComponent(type)}`);
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data?.detail || `Error HTTP: ${response.status}`); }
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await response.blob(), filename: match?.[1] || `reporte_${type}.pdf` };
}

async function postJson(path, config) {
  return parseResponse(await fetch(`${API_URL}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }));
}
export const testDatabaseConnection = (config) => postJson('/api/database/test', config);
export const connectDatabase = (config) => postJson('/api/database/connect', config);
export const testPostgreSQLConnection = (config) => postJson('/api/database/test/postgresql', config);
export const connectPostgreSQL = (config) => postJson('/api/database/connect/postgresql', config);

async function uploadFile(path, file) {
  const formData = new FormData();
  formData.append('file', file);
  return parseResponse(await fetch(`${API_URL}${path}`, { method: 'POST', body: formData }));
}
export const uploadSqlServerBackup = (file) => uploadFile('/api/database/upload/sqlserver-bak', file);
export const inspectExcel = (file) => uploadFile('/api/database/upload/excel/inspect', file);
export const uploadExcel = (file) => uploadFile('/api/database/upload/excel', file);
