const API_URL = 'http://127.0.0.1:8000';

export async function askDatabase(question) {
  const response = await fetch(`${API_URL}/ask-db`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
    }),
  });

  if (!response.ok) {
    throw new Error(`Error HTTP: ${response.status}`);
  }

  return response.json();
}