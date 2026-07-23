import { type LucideIcon } from "lucide-react";

export function EmptyState({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8">
      <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-secondary/20 backdrop-blur-sm border border-dashed border-border">
        <Icon size={20} className="text-muted-foreground/50" />
      </div>
      <span className="text-xs-minus text-muted-foreground/50">{label}</span>
    </div>
  );
}
