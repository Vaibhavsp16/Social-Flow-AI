const db = globalThis.__B44_DB__ || { auth:{ isAuthenticated: async()=>false, me: async()=>null }, entities:new Proxy({}, { get:()=>({ filter:async()=>[], get:async()=>null, create:async()=>({}), update:async()=>({}), delete:async()=>({}) }) }), integrations:{ Core:{ UploadFile:async()=>({ file_url:'' }) } } };

import React, { useState } from "react";
import { Sparkles, Wand2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { INDUSTRIES, DURATIONS, CONTENT_TYPES } from "@/lib/industries";
import IndustryCard from "@/components/IndustryCard";
import DurationCard from "@/components/DurationCard";
import FileUploader from "@/components/FileUploader";
import ResultsView from "@/components/ResultsView";
import { cn } from "@/lib/utils";

function StepLabel({ n, title, hint }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-xs font-semibold text-background">{n}</span>
      <div>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}

export default function Home() {
  const [industry, setIndustry] = useState(null);
  const [duration, setDuration] = useState(null);
  const [contentType, setContentType] = useState("Single Post");
  const [files, setFiles] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [posts, setPosts] = useState(null);

  const durationObj = DURATIONS.find((d) => d.id === duration);
  const canGenerate = industry && duration && !generating;

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await db.functions.invoke("generateContent", {
        industry,
        duration,
        numPosts: durationObj.posts,
        contentType,
        referenceFileUrls: files.map((f) => f.url)
      });
      const data = res?.data || res;
      if (data?.error) throw new Error(data.error);
      if (!data?.posts?.length) throw new Error("No posts were generated. Please try again.");
      setPosts(data.posts);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e.message || "Something went wrong while generating content.");
    } finally {
      setGenerating(false);
    }
  };

  const handleReset = () => {
    setPosts(null);
    setError(null);
  };

  if (posts) {
    return <ResultsView config={{ industry, duration, contentType }} posts={posts} onBack={handleReset} />;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Hero */}
      <header className="relative overflow-hidden border-b border-border">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-muted/60 to-background" />
        <div className="mx-auto max-w-5xl px-5 pb-10 pt-14 sm:px-8 sm:pt-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" /> AI Content Studio
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl md:text-5xl">
            Generate a social-media content plan,<br className="hidden sm:block" /> tailored to your industry.
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">
            Pick an industry, choose a plan, drop in reference material, and let AI craft a full calendar of captions, visual direction, and hashtags — written in the voice your audience expects.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-10 sm:px-8">
        <div className="space-y-12">
          {/* Step 1 */}
          <section>
            <StepLabel n={1} title="Select your industry" hint="Each industry uses a distinct tone, vocabulary, and content strategy." />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {INDUSTRIES.map((ind) => (
                <IndustryCard key={ind.id} industry={ind} selected={industry === ind.id} onSelect={setIndustry} />
              ))}
            </div>
          </section>

          {/* Step 2 */}
          <section>
            <StepLabel n={2} title="Choose your content plan" hint="Duration determines how many posts the AI will generate." />
            <div className="grid gap-4 sm:grid-cols-3">
              {DURATIONS.map((d) => (
                <DurationCard key={d.id} duration={d} selected={duration === d.id} onSelect={setDuration} />
              ))}
            </div>
          </section>

          {/* Step 3 */}
          <section>
            <StepLabel n={3} title="Content format" hint="How each post will be published." />
            <div className="flex flex-wrap gap-2.5">
              {CONTENT_TYPES.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setContentType(t)}
                  className={cn(
                    "rounded-full border px-4 py-2 text-sm font-medium transition-all",
                    contentType === t
                      ? "border-transparent bg-foreground text-background shadow-sm"
                      : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
          </section>

          {/* Step 4 */}
          <section>
            <StepLabel n={4} title="Upload reference material" hint="Optional — brand decks, product sheets, catalogs, or mood images the AI should use as context." />
            <FileUploader
              files={files}
              onAdd={(f) => setFiles((prev) => [...prev, f])}
              onRemove={(url) => setFiles((prev) => prev.filter((f) => f.url !== url))}
            />
          </section>
        </div>

        {/* Generate bar */}
        <div className="sticky bottom-4 mt-10">
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-card/80 p-4 shadow-lg backdrop-blur sm:flex-row sm:justify-between">
            <div className="text-sm text-muted-foreground">
              {industry && duration ? (
                <span>
                  <span className="font-medium text-foreground">{INDUSTRIES.find((i) => i.id === industry)?.name}</span> · {duration} · {durationObj?.posts} {contentType}s
                </span>
              ) : (
                "Select an industry and a plan to continue."
              )}
            </div>
            <Button
              size="lg"
              disabled={!canGenerate}
              onClick={handleGenerate}
              className="w-full gap-2 sm:w-auto"
            >
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {generating ? "Generating…" : "Generate Content"}
            </Button>
          </div>
          {error && (
            <p className="mt-2 text-center text-sm text-destructive">{error}</p>
          )}
        </div>
      </main>
    </div>
  );
}