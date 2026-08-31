import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export default function IndustryCard({ industry, selected, onSelect }) {
  const Icon = industry.icon;
  return (
    <button
      type="button"
      onClick={() => onSelect(industry.id)}
      className={cn(
        "group relative text-left rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg",
        selected
          ? "border-transparent ring-2 shadow-lg " + industry.ring
          : "border-border hover:border-foreground/20"
      )}
    >
      <div className="flex items-start justify-between">
        <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm", industry.gradient)}>
          <Icon className="h-5 w-5" />
        </div>
        {selected && (
          <span className={cn("flex h-6 w-6 items-center justify-center rounded-full bg-foreground text-background")}>
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </span>
        )}
      </div>
      <h3 className="mt-4 text-base font-semibold tracking-tight">{industry.name}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{industry.tagline}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {industry.focus.slice(0, 4).map((f) => (
          <span key={f} className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", industry.soft, industry.text)}>
            {f}
          </span>
        ))}
        <span className="rounded-full px-2 py-0.5 text-[11px] font-medium text-muted-foreground">+{industry.focus.length - 4}</span>
      </div>
    </button>
  );
}