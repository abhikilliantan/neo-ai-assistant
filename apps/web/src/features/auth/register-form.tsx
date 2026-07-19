"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ApiErrorEnvelope } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { register as registerUser } from "@/services/auth";
import { useSessionStore } from "@/store/session";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  organization_name: z
    .string()
    .max(255, "Name is too long")
    .optional()
    .transform((v) => (v === "" ? undefined : v)),
});
type FormValues = z.infer<typeof schema>;

export function RegisterForm() {
  const router = useRouter();
  const setSession = useSessionStore((s) => s.setSession);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setServerError(null);
    try {
      const r = await registerUser(values);
      setSession({
        user: { id: r.user_id, email: r.email },
        accessToken: r.access_token,
        refreshToken: r.refresh_token,
        tenantId: r.active_tenant_id,
      });
      router.replace("/");
    } catch (e) {
      setServerError(extractApiMessage(e) ?? "Unable to create account.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            {errors.email && <p className="text-xs text-red-500">{errors.email.message}</p>}
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password && <p className="text-xs text-red-500">{errors.password.message}</p>}
          </div>
          <div className="space-y-1">
            <label htmlFor="organization_name" className="text-sm font-medium">
              Organization <span className="text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="organization_name"
              type="text"
              autoComplete="organization"
              {...register("organization_name")}
            />
            {errors.organization_name && (
              <p className="text-xs text-red-500">{errors.organization_name.message}</p>
            )}
          </div>
          {serverError && (
            <p role="alert" className="text-sm text-red-500">
              {serverError}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create account"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function extractApiMessage(err: unknown): string | null {
  if (!axios.isAxiosError(err)) return null;
  const body = err.response?.data as ApiErrorEnvelope | undefined;
  return body?.error?.message ?? null;
}
