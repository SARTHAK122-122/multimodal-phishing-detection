import axios from 'axios';

/**
 * Single axios instance for the whole dashboard.
 * React never talks to the Python service directly - every call goes through
 * the Spring Boot API.
 *
 * Default base is the same-origin "/api" path: in dev Vite proxies it to the
 * backend (see vite.config.ts), in Docker nginx proxies it (see nginx.conf),
 * so the production bundle never hardcodes a host. Override with
 * VITE_API_BASE_URL at build time for exotic deployments.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? `${import.meta.env.BASE_URL}api`,
  withCredentials: Boolean(import.meta.env.VITE_API_BASE_URL),
  // Website scans with rendering take up to ~2 minutes end-to-end; the backend
  // read timeout is 120s, so the client must wait at least as long.
  timeout: 180000,
});

/** Extracts the server message from an axios error without leaking stack traces. */
export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { message?: string; detail?: string } | undefined;
    if (data?.message) return data.message;
    if (data?.detail) return String(data.detail);
    if (err.code === 'ECONNABORTED') return 'The request timed out.';
    if (!err.response) return 'Cannot reach the backend. Is Spring Boot running?';
    return `Request failed (HTTP ${err.response.status}).`;
  }
  return err instanceof Error ? err.message : 'Unexpected error.';
}

/**
 * Session handling: if a *protected* call comes back 401 the login session has
 * ended (expiry/logout elsewhere) and the user is sent to the login page with a
 * `next` parameter so they land back where they were. Auth endpoints themselves
 * are excluded so login/register failures stay inline in their forms, and a
 * signed-out boot (`/auth/me` 401) must never cause a redirect loop.
 */
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status;
      const url = String(err.config?.url ?? '');
      const onAuthPage = window.location.pathname === '/login'
        || window.location.pathname === '/register';
      if (status === 401 && !url.includes('/auth/') && !onAuthPage) {
        const next = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        window.location.assign(`/login?next=${next}`);
      }
    }
    return Promise.reject(err);
  },
);
