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
      className="border-t border-border bg-bg-elev/50 backdrop-blur p-3.5"
    >
      <div className="flex items-end gap-2 bg-bg border border-border focus-within:border-accent rounded-2xl px-3.5 py-2 transition">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder="Type a message — same as WhatsApp"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent outline-none text-sm py-1 max-h-32"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className={cn(
            "h-8 w-8 flex items-center justify-center rounded-xl",
            "bg-accent hover:bg-accent/90 text-bg disabled:opacity-30 disabled:cursor-not-allowed transition",
          )}
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </div>
      <p className="text-[10px] text-text-mute mt-2 px-2">
        Press Enter to send · Shift+Enter for new line
      </p>
    </form>
  );
}
