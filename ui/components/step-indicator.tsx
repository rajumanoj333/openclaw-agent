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
                "w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition",
                done && "bg-accent text-bg border-accent",
                current && "bg-accent/20 text-accent border-accent shadow-glow",
                !done && !current && "bg-panel text-text-mute border-border",
              )}
            >
              {done ? <Check size={14} /> : i + 1}
            </div>
            <span
              className={cn(
                "text-sm font-medium",
                current ? "text-text" : "text-text-mute",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span
                className={cn(
                  "w-8 h-px",
                  done ? "bg-accent" : "bg-border",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
