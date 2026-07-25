"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ApiErrorEnvelope } from "@neo/shared-types";
import { AuthShell } from "@/features/auth/auth-shell";
import { Button } from "@/components/ui/button";
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
    <AuthShell
      title="Create your account"
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent underline underline-offset-2">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium text-foreground">
            Email
          </label>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <p className="text-xs text-danger">{errors.email.message}</p>}
        </div>
        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium text-foreground">
            Password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...register("password")}
          />
          {errors.password && <p className="text-xs text-danger">{errors.password.message}</p>}
        </div>
        <div className="space-y-1">
          <label htmlFor="organization_name" className="text-sm font-medium text-foreground">
            Organization <span className="text-faint">(optional)</span>
          </label>
          <Input
            id="organization_name"
            type="text"
            autoComplete="organization"
            {...register("organization_name")}
          />
          {errors.organization_name && (
            <p className="text-xs text-danger">{errors.organization_name.message}</p>
          )}
        </div>
        {serverError && (
          <p
            role="alert"
            className="rounded-control border border-danger/40 bg-danger/15 px-3 py-2 text-sm text-danger"
          >
            {serverError}
          </p>
        )}
        <Button type="submit" variant="gradient" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}

function extractApiMessage(err: unknown): string | null {
  if (!axios.isAxiosError(err)) return null;
  const body = err.response?.data as ApiErrorEnvelope | undefined;
  return body?.error?.message ?? null;
}
