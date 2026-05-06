import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

const STEPS = ["Business", "Confirm", "Agent"] as const;

export function StepIndicator({ active }: { active: 0 | 1 | 2 }) {
  return (
    <ol className="flex items-center gap-3 mb-8">
      {STEPS.map((label, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <li key={label} className="flex items-center gap-3">
            <div
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-medium transition",
                done && "bg-text text-bg",
                current && "bg-text text-bg",
                !done && !current && "bg-bg border border-border text-text-mute",
              )}
            >
              {done ? <Check size={12} /> : i + 1}
            </div>
            <span
              className={cn(
                "text-[13px]",
                current || done ? "text-text font-medium" : "text-text-mute",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span className={cn("w-6 h-px", done ? "bg-text/40" : "bg-border")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
