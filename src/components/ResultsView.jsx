import React from "react";
import { ArrowLeft, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { INDUSTRIES } from "@/lib/industries";
import PostCard from "@/components/PostCard";

export default function ResultsView({ config, posts, onBack }) {
  const industry = INDUSTRIES.find((i) => i.id === config.industry);
  const accent = industry ? `bg-gradient-to-br ${industry.gradient}` : "bg-foreground";

  const handleExport = () => {
    const lines = posts.map((p) => {
      const tags = (p.hashtags || []).map((h) => (h.startsWith("#") ? h : "#" + h)).join(" ");
      return `POST ${p.postNumber} — ${p.date}${p.focusArea ? ` (${p.focusArea})` : ""}\n\nCaption:\n${p.caption}\n\nVisual Direction:\n${p.imageDirection}\n\nHashtags:\n${tags}\n\n${"─".repeat(60)}`;
    });
    const blob = new Blob([lines.join("\n\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${industry?.name || "content"}-plan.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <button onClick={onBack} className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Back to setup
          </button>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Your content plan</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{industry?.name}</span> · {config.duration} · {posts.length} posts · {config.contentType}
          </p>
        </div>
        <Button variant="outline" onClick={handleExport} className="gap-2">
          <Download className="h-4 w-4" /> Export plan
        </Button>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        {posts.map((p, i) => (
          <PostCard key={i} post={p} accent={accent} />
        ))}
      </div>
    </div>
  );
}