"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, Eye, Upload } from "lucide-react";
import { BatchStatusCard } from "@/components/records/BatchStatusCard";
import { excelFileUrl, listRecordBatches, type RecordBatch } from "@/lib/records-api";
import { useToast } from "@/components/ui/Toast";

export default function RecordBatchesPage() {
  const { showToast } = useToast();
  const [batches, setBatches] = useState<RecordBatch[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    void listRecordBatches()
      .then((response) => {
        setBatches(response.items);
        setTotal(response.total);
      })
      .catch((error) => showToast({ tone: "error", title: "Could not load batches", message: error instanceof Error ? error.message : undefined }));
  }, [showToast]);

  return (
    <div className="page-container">
      <div className="section-heading">
        <div>
          <h2>Record Upload Batches</h2>
          <p className="muted">{total} batch{total === 1 ? "" : "es"} found</p>
        </div>
        <Link className="button" href="/records/upload">
          <Upload size={16} aria-hidden /> New Upload
        </Link>
      </div>
      <div className="records-batch-grid">
        {batches.map((batch) => (
          <div className="card" key={batch.id}>
            <BatchStatusCard batch={batch} />
            <div className="action-bar">
              <Link className="button secondary" href={`/records/review/${batch.id}`}>
                <Eye size={16} aria-hidden /> Review
              </Link>
              {batch.status === "completed" ? (
                <Link className="button secondary" href={excelFileUrl(batch.id)}>
                  <Download size={16} aria-hidden /> Excel
                </Link>
              ) : null}
            </div>
          </div>
        ))}
        {!batches.length ? <div className="card empty-state">No record batches yet.</div> : null}
      </div>
    </div>
  );
}
