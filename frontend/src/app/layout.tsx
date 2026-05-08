import type { Metadata } from "next";
import "./globals.css";
import { BuildStamp } from "@/components/layout/BuildStamp";

export const metadata: Metadata = {
  title: "Bürokratie-Helfer",
  description: "Form assistance for Jobcenter documents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="min-h-screen bg-gray-50 pb-6">
        {children}
        <BuildStamp />
      </body>
    </html>
  );
}
