import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ChipToggleProps {
  selected: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}

export function ChipToggle({ selected, onClick, children, className }: ChipToggleProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full px-2.5 py-1 text-xs-minus border transition-colors",
        selected
          ? "border-primary bg-primary/30 text-primary"
          : "border-border/40 text-muted-foreground hover:bg-secondary/60",
        className,
      )}
    >
      {children}
    </button>
  );
}
