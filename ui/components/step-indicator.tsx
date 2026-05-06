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
          <li key={label} className="flex items-center gap-2.5">
            <div
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center font-mono text-[11px] font-medium transition",
                done && "bg-ink text-bg-elev",
                current && "bg-ink text-bg-elev shadow-ink",
                !done && !current &&
                  "bg-bg-elev border border-border text-text-mute",
              )}
            >
              {done ? <Check size={12} strokeWidth={2.6} /> : i + 1}
            </div>
            <span
              className={cn(
                "text-[13px] font-medium",
                current || done ? "text-ink" : "text-text-mute",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span
                className={cn(
                  "w-8 h-px",
                  done ? "bg-ink/40" : "bg-border",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
