"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { clsx } from "clsx";
import { UploadResponse } from "@/types/api";
import { api } from "@/lib/api";

interface FileDropzoneProps {
  token: string;
  caseId: string;
  onUploadComplete: (response: UploadResponse) => void;
  onError: (message: string) => void;
  uploadLabel: string;
  supportedLabel: string;
}

export function FileDropzone({
  token,
  caseId,
  onUploadComplete,
  onError,
  uploadLabel,
  supportedLabel,
}: FileDropzoneProps) {
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      setFileName(file.name);
      setUploading(true);
      try {
        const result = await api.documents.upload(token, caseId, file);
        onUploadComplete(result);
      } catch (e: unknown) {
        onError(e instanceof Error ? e.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [token, caseId, onUploadComplete, onError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [], "image/jpeg": [], "image/png": [], "image/tiff": [] },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps()}
      className={clsx(
        "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-colors",
        isDragActive ? "border-brand-600 bg-brand-50" : "border-gray-300 bg-white hover:border-brand-400",
        uploading && "opacity-60 cursor-not-allowed"
      )}
    >
      <input {...getInputProps()} />
      <div className="text-4xl mb-3">📄</div>
      {uploading ? (
        <p className="text-brand-600 font-medium">Uploading {fileName}...</p>
      ) : fileName ? (
        <p className="text-green-600 font-medium">✓ {fileName}</p>
      ) : (
        <>
          <p className="text-gray-700 font-medium mb-1">{uploadLabel}</p>
          <p className="text-gray-400 text-sm">{supportedLabel}</p>
        </>
      )}
    </div>
  );
}
