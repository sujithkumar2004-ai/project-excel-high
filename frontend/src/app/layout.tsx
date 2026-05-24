import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Excel Records",
  description: "Hospital records upload, extraction, review, and Excel export"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <div className="app-shell">
            <header className="app-header">
              <Link href="/records/batches" className="brand">
                <FileSpreadsheet size={22} aria-hidden />
                <span>Project Excel</span>
              </Link>
              <nav>
                <Link href="/records/batches">Batches</Link>
                <Link href="/records/upload">
                  <Upload size={16} aria-hidden /> Upload
                </Link>
              </nav>
            </header>
            <main>{children}</main>
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}
