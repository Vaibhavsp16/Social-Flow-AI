const db = globalThis.__B44_DB__ || { auth:{ isAuthenticated: async()=>false, me: async()=>null }, entities:new Proxy({}, { get:()=>({ filter:async()=>[], get:async()=>null, create:async()=>({}), update:async()=>({}), delete:async()=>({}) }) }), integrations:{ Core:{ UploadFile:async()=>({ file_url:'' }) } } };

import React, { useRef, useState } from "react";
import { Upload, X, FileText, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.jpg,.jpeg,.png";

function fileIcon(name) {
  return <FileText className="h-4 w-4 text-muted-foreground" />;
}

export default function FileUploader({ files, onAdd, onRemove }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const handleFiles = async (fileList) => {
    const arr = Array.from(fileList);
    if (!arr.length) return;
    setUploading(true);
    try {
      for (const file of arr) {
        const { file_url } = await db.integrations.Core.UploadFile({ file });
        onAdd({ name: file.name, url: file_url });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          dragging ? "border-foreground/60 bg-muted/50" : "border-border hover:border-foreground/30 hover:bg-muted/30"
        )}
      >
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-muted">
          {uploading ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /> : <Upload className="h-5 w-5 text-muted-foreground" />}
        </div>
        <p className="mt-3 text-sm font-medium">
          {uploading ? "Uploading…" : "Drop reference files here or browse"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">PDF, DOC, PPT, XLS, TXT, JPG, PNG</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {files.map((f, i) => (
            <li key={f.url + i} className="flex items-center justify-between rounded-xl border border-border bg-card px-3 py-2.5">
              <div className="flex min-w-0 items-center gap-2.5">
                {fileIcon(f.name)}
                <span className="truncate text-sm">{f.name}</span>
              </div>
              <button
                type="button"
                onClick={() => onRemove(f.url)}
                className="ml-2 flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}