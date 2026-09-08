const API_URL = 'http://127.0.0.1:8000';

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data?.detail || `Error HTTP: ${response.status}`;
    throw new Error(detail);
  }

  return data;
}

export async function askDatabase(question) {
  const response = await fetch(`${API_URL}/ask-db`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  return parseResponse(response);
}

export async function getDashboard() {
  const response = await fetch(`${API_URL}/api/dashboard`);
  return parseResponse(response);
}

export async function getDatabaseStatus() {
  const response = await fetch(`${API_URL}/api/database/status`);
  return parseResponse(response);
}

export async function testDatabaseConnection(config) {
  const response = await fetch(`${API_URL}/api/database/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  });

  return parseResponse(response);
}

export async function connectDatabase(config) {
  const response = await fetch(`${API_URL}/api/database/connect`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  });

  return parseResponse(response);
}

export async function getBusinessDomain() {
  const response = await fetch(`${API_URL}/api/database/domain`);
  return parseResponse(response);
}

export async function getSemanticModel() {
  const response = await fetch(`${API_URL}/api/database/semantic-model`);
  return parseResponse(response);
}
