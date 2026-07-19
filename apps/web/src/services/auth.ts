import axios from "axios";
import type { AuthResponse, LoginRequest, RegisterRequest } from "@neo/shared-types";
import { env } from "@/lib/env";
import { http } from "@/services/http";

// A separate axios instance for refresh — bypasses the interceptor to avoid
// recursion (refresh failing → interceptor tries to refresh → infinite loop).
const rawHttp = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

export async function register(body: RegisterRequest): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>("/api/v1/auth/register", body);
  return data;
}

export async function login(body: LoginRequest): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>("/api/v1/auth/login", body);
  return data;
}

export async function refresh(refreshToken: string): Promise<AuthResponse> {
  const { data } = await rawHttp.post<AuthResponse>("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await http.post("/api/v1/auth/logout", { refresh_token: refreshToken });
}
