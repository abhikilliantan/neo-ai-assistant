import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { env } from "@/lib/env";
import { clearAndRedirect, refreshOnce } from "@/services/session-refresh";
import { useSessionStore } from "@/store/session";

export const http: AxiosInstance = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  config.headers["X-Request-ID"] = crypto.randomUUID();
  const token = useSessionStore.getState().accessToken;
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    const url = original?.url ?? "";

    if (status !== 401 || !original || original._retry) return Promise.reject(error);
    // Don't loop on refresh/logout itself — those failing means credentials are dead.
    if (url.includes("/auth/refresh") || url.includes("/auth/logout")) {
      clearAndRedirect();
      return Promise.reject(error);
    }

    original._retry = true;
    const newToken = await refreshOnce();
    if (!newToken) {
      clearAndRedirect();
      return Promise.reject(error);
    }
    original.headers.Authorization = `Bearer ${newToken}`;
    return http(original);
  },
);
