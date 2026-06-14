function resolveApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    const isDevelopment = process.env.NODE_ENV === 'development';

    if (isDevelopment) {
      if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
        return 'http://localhost:8000/api';
      }
      return `http://${host}:8000/api`;
    }

    return 'https://xeno-backend.onrender.com/api';
  }

  // Fallback for server-side execution
  return 'http://localhost:8000/api';
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const API_BASE_URL = resolveApiBaseUrl();
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  const response = await fetch(url, { ...defaultOptions, ...options });

  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // Ignore
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
