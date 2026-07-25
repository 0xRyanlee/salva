import { useState } from "react";
import type { ReactNode } from "react";
import { ChipToggle } from "@/components/ui/ChipToggle";
import { Input } from "@/components/ui/input";

interface RetentionPickerProps {
  value: number | null;
  onChange: (value: number | null) => void;
  presets?: number[];
  presetLabel?: (days: number) => string;
  indefiniteLabel?: string;
  hint?: ReactNode;
}

export function RetentionPicker({
  value,
  onChange,
  presets = [7, 30, 90],
  presetLabel = (days) => `${days} 天`,
  indefiniteLabel = "無限期",
  hint,
}: RetentionPickerProps) {
  const [customValue, setCustomValue] = useState(
    value != null && !presets.includes(value) ? String(value) : "",
  );

  function selectPreset(days: number) {
    setCustomValue("");
    onChange(days);
  }

  function selectIndefinite() {
    setCustomValue("");
    onChange(null);
  }

  function handleCustomChange(raw: string) {
    setCustomValue(raw);
    const n = Number(raw);
    if (raw && n >= 1) onChange(n);
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        {presets.map((days) => (
          <ChipToggle key={days} selected={value === days} onClick={() => selectPreset(days)}>
            {presetLabel(days)}
          </ChipToggle>
        ))}
        <ChipToggle selected={value === null} onClick={selectIndefinite}>
          {indefiniteLabel}
        </ChipToggle>
      </div>
      <div className="flex items-center gap-2">
        <span className="type-caption text-muted-foreground shrink-0">自訂天數</span>
        <Input
          type="number"
          min={1}
          value={customValue}
          onChange={(e) => handleCustomChange(e.target.value)}
          placeholder="例：14"
          className="w-24"
        />
      </div>
      {hint && <p className="type-caption text-muted-foreground">{hint}</p>}
    </div>
  );
}
