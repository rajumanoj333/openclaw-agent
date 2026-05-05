import { cn } from "@/lib/cn";

const STEPS = ["Business URL", "Confirm details", "Define agent"] as const;

export function StepIndicator({ active }: { active: 0 | 1 | 2 }) {
  return (
    <ol className="flex items-center gap-2 mb-6">
      {STEPS.map((label, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "w-7 h-7 rounded-full text-xs flex items-center justify-center border",
                done && "bg-accent text-bg border-accent",
                current && "bg-accent/20 text-accent border-accent",
                !done && !current && "bg-panel text-white/40 border-border",
              )}
            >
              {done ? "✓" : i + 1}
            </span>
            <span
              className={cn(
                "text-xs",
                current ? "text-white" : "text-white/40",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span className="w-6 h-px bg-border mx-1" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
