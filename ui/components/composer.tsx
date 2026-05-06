"use client";

import { ArrowUp, Globe, Mic, Plus } from "lucide-react";
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
    <form onSubmit={submit} className="px-5 py-4">
      <div className="card p-3.5">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask anything — design a poster, draft a caption…"
          rows={1}
          disabled={disabled}
          className="w-full resize-none bg-transparent outline-none text-[15px] py-1 max-h-32 placeholder:text-text-mute"
        />
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-text-dim hover:bg-bg transition"
              aria-label="Attach"
            >
              <Plus size={14} />
            </button>
            <div className="flex items-center gap-1.5 text-text-mute text-xs px-2 py-1 rounded-full hover:bg-bg cursor-default">
              <Globe size={12} />
              Search
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-text-dim hover:bg-bg transition"
              aria-label="Voice"
            >
              <Mic size={14} />
            </button>
            <button
              type="submit"
              disabled={disabled || !value.trim()}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center transition",
                disabled || !value.trim()
                  ? "bg-border-strong text-bg cursor-not-allowed opacity-60"
                  : "bg-text text-bg hover:bg-text/90",
              )}
              aria-label="Send"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
