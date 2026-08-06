import * as React from "react";
import { cn } from "@/lib/cn";
import { SampleTag } from "./SampleTag";

export interface GlowCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Flag the card as showing placeholder data — renders a SampleTag top-right. */
  sample?: boolean;
}

/** Base redesign surface: hairline border, top-lighter gradient, hover glow.
 *  Every widget in the kit builds on this. */
export const GlowCard = React.forwardRef<HTMLDivElement, GlowCardProps>(
  ({ className, sample, children, ...props }, ref) => (
    <div ref={ref} className={cn("glow-card p-5", className)} {...props}>
      {sample && <SampleTag className="absolute right-3 top-3" />}
      {children}
    </div>
  ),
);
GlowCard.displayName = "GlowCard";
