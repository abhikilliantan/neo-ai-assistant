// Framework-free transport contracts shared across web + tooling.
// No business types — those live in feature packages.

export type ApiEnvelope<T> = {
  data: T;
  requestId: string;
};

export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type Pagination = {
  page: number;
  pageSize: number;
  total: number;
};

export type HealthStatus = {
  status: "ok" | "degraded";
  version: string;
};
