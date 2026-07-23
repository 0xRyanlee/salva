import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        // Active/pressed/toggled state: pass native `aria-pressed` (no custom prop needed) —
        // mirrors Tabs' `data-[state=active]:` convention. See docs/DESIGN_SYSTEM.md §8.1.
        // Only fires when the attribute is present, so non-active ghost buttons are unaffected.
        ghost:
          "hover:bg-secondary hover:text-foreground aria-pressed:bg-primary/20 aria-pressed:text-primary aria-pressed:hover:bg-primary/20 aria-pressed:hover:text-primary",
        outline: "border border-border bg-transparent hover:bg-secondary",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        // Pill CTA recipe: 100%-opacity accent-colored stroke + 30%-opacity accent fill —
        // deliberately lighter than `default`'s solid fill for a primary action that
        // shouldn't visually shout (e.g. "Start fresh" repeated down a session list).
        // See docs/DESIGN_SYSTEM.md "Pill / accent-tint CTA" for the canonical spec.
        soft: "border border-primary bg-primary/30 text-primary hover:bg-primary/40",
        // Inline text action (e.g. "Change key", "Remove") — no box/padding, underline on hover.
        // Always pair with size="auto"; the default/sm sizes' fixed height+padding win via
        // twMerge last-wins since `size` classes concatenate after `variant` classes.
        link: "text-primary underline-offset-2 hover:underline bg-transparent",
        // Neutral tinted button — used by the pulled-in shadcn chat components (bubble/marker
        // actions). Distinct from `ghost` (transparent) by carrying a secondary fill.
        secondary: "bg-secondary text-foreground hover:bg-secondary/80",
      },
      size: {
        default: "h-7 px-3 py-1",
        sm: "h-6 px-2",
        icon: "h-7 w-7",
        // Smaller square icon buttons the shadcn chat components ask for (attachment remove,
        // scroll controls). Additive — no existing call site uses these.
        "icon-sm": "h-6 w-6",
        "icon-xs": "h-5 w-5",
        auto: "h-auto p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
