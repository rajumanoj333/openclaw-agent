"use client";

import { Send } from "lucide-react";
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
    <form
      onSubmit={submit}
      className="border-t border-border bg-panel/60 backdrop-blur p-3 flex items-end gap-2"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKey}
        placeholder="Send your business URL, or ask me to design a poster…"
        rows={1}
        disabled={disabled}
        className={cn(
          "flex-1 resize-none bg-bg border border-border rounded-xl px-3 py-2 text-sm",
          "outline-none focus:border-accent/60 max-h-32",
        )}
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className={cn(
          "h-9 w-9 flex items-center justify-center rounded-xl",
          "bg-accent/80 hover:bg-accent text-bg disabled:opacity-30 disabled:cursor-not-allowed",
        )}
        aria-label="Send"
      >
        <Send size={16} />
      </button>
    </form>
  );
}
