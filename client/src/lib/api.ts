import axios, { AxiosError, type AxiosRequestConfig } from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach the JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("sar_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, clear session and redirect to login
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("sar_token");
      localStorage.removeItem("sar_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

/** Extract a human-readable error message from an API error. */
export function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string | Array<{ msg: string }> };
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail.length) {
      return data.detail.map((d) => d.msg).join("; ");
    }
    if (error.message) return error.message;
  }
  return "An unexpected error occurred";
}

export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.get<T>(url, config);
  return res.data;
}

export async function apiPost<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.post<T>(url, data, config);
  return res.data;
}

export async function apiPatch<T>(url: string, data?: unknown): Promise<T> {
  const res = await api.patch<T>(url, data);
  return res.data;
}

export async function apiDelete<T>(url: string): Promise<T> {
  const res = await api.delete<T>(url);
  return res.data;
}

export { api };
