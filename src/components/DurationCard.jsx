import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export default function DurationCard({ duration, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(duration.id)}
      className={cn(
        "group relative text-left rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg",
        selected ? "border-transparent ring-2 ring-foreground shadow-lg" : "border-border hover:border-foreground/20"
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-2xl font-semibold tracking-tight">{duration.label}</span>
        {selected && (
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-foreground text-background">
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{duration.description}</p>
      <div className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs font-medium">
        <span className="font-semibold text-foreground">{duration.posts}</span> posts
      </div>
    </button>
  );
}