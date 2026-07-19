import axios, { type AxiosInstance } from "axios";
import { env } from "@/lib/env";

export const http: AxiosInstance = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  config.headers["X-Request-ID"] = crypto.randomUUID();
  return config;
});

http.interceptors.response.use(
  (r) => r,
  (error) => Promise.reject(error),
);
