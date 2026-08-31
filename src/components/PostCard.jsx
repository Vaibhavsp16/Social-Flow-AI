import React, { useState } from "react";
import { Calendar, Copy, Check, ImageIcon, Hash } from "lucide-react";
import { cn } from "@/lib/utils";

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch (e) {}
      }}
      className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {copied ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : label}
    </button>
  );
}

export default function PostCard({ post, accent }) {
  const hashtags = Array.isArray(post.hashtags) ? post.hashtags : [];
  const hashtagText = hashtags.map((h) => (h.startsWith("#") ? h : "#" + h)).join(" ");

  return (
    <article className="group relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
        <div className="flex items-center gap-3">
          <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl text-sm font-semibold text-white", accent)}>
            {post.postNumber}
          </span>
          <div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Calendar className="h-3 w-3" />
              {post.date || "—"}
            </div>
            {post.focusArea && (
              <div className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
                {post.focusArea}
              </div>
            )}
          </div>
        </div>
        <span className="text-xs font-medium text-muted-foreground">Post {post.postNumber}</span>
      </div>

      <div className="space-y-4 p-5">
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Caption</span>
            <CopyButton text={post.caption} label="Copy" />
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{post.caption}</p>
        </div>

        <div className="rounded-xl bg-muted/50 p-4">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <ImageIcon className="h-3.5 w-3.5" /> Visual Direction
          </div>
          <p className="text-sm leading-relaxed text-foreground/80">{post.imageDirection}</p>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Hash className="h-3.5 w-3.5" /> Hashtags
            </span>
            <CopyButton text={hashtagText} label="Copy all" />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {hashtags.map((h, i) => (
              <span key={i} className="rounded-full bg-primary/5 px-2.5 py-1 text-xs font-medium text-primary/80">
                {h.startsWith("#") ? h : "#" + h}
              </span>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}