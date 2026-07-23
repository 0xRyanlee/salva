import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/** §8.2 accent-tint recipe: 100%-opacity border + 30%-opacity background, text in
 * the accent color itself. Central source of truth so Badge/StatusPill/StatusBar
 * pills don't each drift to their own opacity — see cc-spk-token-unify-badge-pill-recipe. */
export const pillTintClass = {
  primary: "border border-primary bg-primary/30 text-primary",
  success: "border border-success bg-success/30 text-success",
  destructive: "border border-destructive bg-destructive/30 text-destructive",
  warn: "border border-warn bg-warn/30 text-warn",
} as const;

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-1.5 py-0.5 text-xs-minus font-medium transition-colors",
  {
    variants: {
      variant: {
        default: pillTintClass.primary,
        secondary: "bg-secondary text-muted-foreground",
        outline: "border border-border text-muted-foreground",
        active: "border border-[hsl(var(--active-dot))] bg-[hsl(var(--active-dot)/0.3)] text-[hsl(var(--active-dot))]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

/** Convention: counts and status values (message/token counts, "Connected", update
 * availability, etc.) render as Badge everywhere — never as a plain <span> in one place
 * and Badge in another for the same kind of data. Labels (timestamps, branch names, free
 * text) stay plain text. Session list rows (SessionItem/PinetreeSessionItem/EntityGroupRow
 * in SessionHistorySection.tsx) previously drifted on this per view mode — see
 * cc-spk-settings-badge-text-unify. Settings-panel status pills use the separate
 * StatusPill component (components/settings/shared.tsx) rather than Badge — that's a
 * deliberate distinction (a semantic status chip vs. a plain count/tag), not drift. */
export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
