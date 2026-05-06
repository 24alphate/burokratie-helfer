"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { clsx } from "clsx";

interface FileDropzoneProps {
  /** Stateless mode: parent receives raw File and handles all API logic. */
  onFileSelected: (file: File) => void;
  onError: (message: string) => void;
  uploadLabel: string;
  supportedLabel: string;
  /** Let the parent signal that processing is underway (disables the dropzone). */
  isProcessing?: boolean;
}

export function FileDropzone({
  onFileSelected,
  onError,
  uploadLabel,
  supportedLabel,
  isProcessing = false,
}: FileDropzoneProps) {
  const [fileName, setFileName] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      setFileName(file.name);
      try {
        onFileSelected(file);
      } catch (e: unknown) {
        onError(e instanceof Error ? e.message : "Upload failed.");
      }
    },
    [onFileSelected, onError],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [] },
    maxFiles: 1,
    disabled: isProcessing,
  });

  return (
    <div
      {...getRootProps()}
      className={clsx(
        "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-colors",
        isDragActive ? "border-brand-600 bg-brand-50" : "border-gray-300 bg-white hover:border-brand-400",
        isProcessing && "opacity-60 cursor-not-allowed",
      )}
    >
      <input {...getInputProps()} />
      <div className="text-4xl mb-3">📄</div>
      {isProcessing ? (
        <p className="text-brand-600 font-medium">Processing {fileName}…</p>
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
