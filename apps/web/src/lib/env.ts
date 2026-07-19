export const env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Neo AI Assistant",
} as const;
