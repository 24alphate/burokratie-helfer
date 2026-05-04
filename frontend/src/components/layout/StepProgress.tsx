"use client";

import { clsx } from "clsx";

const STEPS = ["Upload", "Questions", "Review", "Download"];

interface StepProgressProps {
  currentStep: 0 | 1 | 2 | 3;
  labels?: string[];
}

export function StepProgress({ currentStep, labels = STEPS }: StepProgressProps) {
  return (
    <div className="w-full flex items-center justify-between mb-8">
      {labels.map((label, i) => (
        <div key={i} className="flex items-center flex-1">
          <div className="flex flex-col items-center">
            <div
              className={clsx(
                "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors",
                i < currentStep && "bg-brand-600 text-white",
                i === currentStep && "bg-brand-600 text-white ring-4 ring-brand-100",
                i > currentStep && "bg-gray-200 text-gray-500"
              )}
            >
              {i < currentStep ? "✓" : i + 1}
            </div>
            <span
              className={clsx(
                "text-xs mt-1 font-medium",
                i === currentStep ? "text-brand-700" : "text-gray-400"
              )}
            >
              {label}
            </span>
          </div>
          {i < labels.length - 1 && (
            <div
              className={clsx(
                "flex-1 h-0.5 mx-2 -mt-4",
                i < currentStep ? "bg-brand-600" : "bg-gray-200"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
