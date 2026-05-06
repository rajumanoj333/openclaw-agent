"use client";

import { ArrowUp } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (body: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(e as unknown as FormEvent);
    }
  };

  return (
    <form onSubmit={submit} className="px-6 py-4">
      <div className="card p-3 flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask anything — design a poster, draft a caption, run a campaign…"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent outline-none text-[15px] text-ink py-2 px-2 max-h-32 placeholder:text-text-mute leading-relaxed"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className={cn(
            "w-10 h-10 rounded-full flex items-center justify-center transition shrink-0",
            disabled || !value.trim()
              ? "bg-border text-text-mute cursor-not-allowed"
              : "shadow-ink hover:opacity-90",
          )}
          style={
            disabled || !value.trim()
              ? undefined
              : { background: "hsl(220 30% 8%)", color: "#ffffff" }
          }
          aria-label="Send"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
      <p className="font-mono text-[10px] text-text-mute mt-2.5 px-2 text-center tracking-wider uppercase">
        Press Enter to send · Shift + Enter for new line
      </p>
    </form>
  );
}
