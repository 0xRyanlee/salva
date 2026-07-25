import type { ReactNode } from "react";
import { X } from "lucide-react";

interface SuccessBannerProps {
  children: ReactNode;
  onDismiss?: () => void;
}

export function SuccessBanner({ children, onDismiss }: SuccessBannerProps) {
  return (
    <div className="rounded-md border border-success/40 bg-success/10 text-success text-sm px-3 py-2 flex items-center justify-between gap-2">
      <span>{children}</span>
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="shrink-0">
          <X size={12} />
        </button>
      )}
    </div>
  );
}
