"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const schema = z.object({
  displayName: z.string().min(1, "Required").max(64),
  defaultModel: z.enum(["claude", "gpt", "gemini", "ollama"]),
});

type FormValues = z.infer<typeof schema>;

export function SettingsView() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { displayName: "", defaultModel: "claude" },
  });

  // ponytail: local echo only. Wire to PATCH /users/me when auth + persistence land.
  const onSubmit = handleSubmit(async (values) => {
    // eslint-disable-next-line no-console
    console.log("settings submit", values);
  });

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="displayName">
              Display name
            </label>
            <Input id="displayName" {...register("displayName")} />
            {errors.displayName && (
              <p className="text-xs text-red-500">{errors.displayName.message}</p>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="defaultModel">
              Default model
            </label>
            <select
              id="defaultModel"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              {...register("defaultModel")}
            >
              <option value="claude">Claude</option>
              <option value="gpt">GPT</option>
              <option value="gemini">Gemini</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>
          <Button type="submit" disabled={isSubmitting}>
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
