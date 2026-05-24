"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { excelFileUrl } from "@/lib/records-api";

export default function RecordExportPage() {
  const params = useParams<{ batchId: string }>();
  return (
    <div className="page-container">
      <section className="card">
        <div className="section-heading">
          <div>
            <h2>Excel Export</h2>
            <p className="muted">Download finalized records for batch {params.batchId}.</p>
          </div>
        </div>
        <Link className="button" href={excelFileUrl(Number(params.batchId))}>
          <Download size={16} aria-hidden /> Download Excel
        </Link>
      </section>
    </div>
  );
}
