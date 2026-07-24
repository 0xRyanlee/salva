import * as React from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;
const PopoverPortal = PopoverPrimitive.Portal;
const PopoverClose = PopoverPrimitive.Close;

function PopoverContent({
  className,
  sideOffset = 6,
  align = "end",
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPortal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        sideOffset={sideOffset}
        align={align}
        className={cn(
          "z-50 w-72 rounded-lg border border-border/40 bg-popover text-popover-foreground p-3 shadow-md focus:outline-none",
          className
        )}
        {...props}
      />
    </PopoverPortal>
  );
}

export { Popover, PopoverTrigger, PopoverPortal, PopoverClose, PopoverContent };
