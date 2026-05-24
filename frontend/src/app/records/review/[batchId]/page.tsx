"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Download, Loader2, Save } from "lucide-react";
import { BatchStatusCard } from "@/components/records/BatchStatusCard";
import { ExtractedRowsTable } from "@/components/records/ExtractedRowsTable";
import { ImagePreviewPanel } from "@/components/records/ImagePreviewPanel";
import { useToast } from "@/components/ui/Toast";
import { excelFileUrl, finalizeRecordBatch, getRecordBatch, updateRecordRows, type ExtractedRecordRow, type RecordBatchDetail } from "@/lib/records-api";

export default function RecordsReviewPage() {
  const params = useParams<{ batchId: string }>();
  const batchId = Number(params.batchId);
  const { showToast } = useToast();
  const [batch, setBatch] = useState<RecordBatchDetail | null>(null);
  const [rows, setRows] = useState<ExtractedRecordRow[]>([]);
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);

  useEffect(() => {
    void getRecordBatch(batchId)
      .then((detail) => {
        setBatch(detail);
        setRows(detail.rows);
        setSelectedImageId(detail.images[0]?.id ?? null);
      })
      .catch((error) => showToast({ tone: "error", title: "Could not load batch", message: error instanceof Error ? error.message : undefined }));
  }, [batchId, showToast]);

  const currentBatch = useMemo(() => (batch ? { ...batch, total_rows: rows.length } : null), [batch, rows.length]);
  const hasLowConfidenceRows = rows.some((row) => (row.extraction_confidence || 0) < 0.55);

  async function saveRows() {
    setIsSaving(true);
    try {
      const savedRows = await updateRecordRows(batchId, rows);
      setRows(savedRows);
      showToast({ tone: "success", title: "Draft rows saved" });
    } catch (error) {
      showToast({ tone: "error", title: "Save failed", message: error instanceof Error ? error.message : undefined });
    } finally {
      setIsSaving(false);
    }
  }

  async function finalizeRows() {
    setIsFinalizing(true);
    try {
      await updateRecordRows(batchId, rows);
      const result = await finalizeRecordBatch(batchId);
      setBatch((previous) => (previous ? { ...previous, ...result.batch } : previous));
      showToast({ tone: "success", title: "Final records saved", message: "Excel export is ready." });
    } catch (error) {
      showToast({ tone: "error", title: "Finalize failed", message: error instanceof Error ? error.message : undefined });
    } finally {
      setIsFinalizing(false);
    }
  }

  if (!batch || !currentBatch) {
    return <div className="page-container"><div className="card">Loading batch...</div></div>;
  }

  return (
    <div className="page-container records-review-page">
      <BatchStatusCard batch={currentBatch} />
      <div className="records-review-layout">
        <section className="card records-review-table-card">
          <div className="section-heading">
            <div>
              <h2>Review Extracted Rows</h2>
              <p className="muted">Edit OCR mistakes, add missing rows, then save final records.</p>
            </div>
            <div className="action-bar">
              <button type="button" className="button secondary" disabled={isSaving || isFinalizing} onClick={saveRows}>
                {isSaving ? <Loader2 size={16} className="spin" aria-hidden /> : <Save size={16} aria-hidden />}
                Save Draft
              </button>
              <button type="button" className="button" disabled={isSaving || isFinalizing || !rows.length} onClick={finalizeRows}>
                {isFinalizing ? <Loader2 size={16} className="spin" aria-hidden /> : <Save size={16} aria-hidden />}
                Save Final Records
              </button>
              {batch.status === "completed" || batch.excel_file_path ? (
                <Link className="button secondary" href={excelFileUrl(batchId)}>
                  <Download size={16} aria-hidden /> Download Excel
                </Link>
              ) : null}
            </div>
          </div>
          {!rows.length ? (
            <div className="ocr-warning" role="status">
              <AlertTriangle size={18} aria-hidden />
              <p>OCR could not reliably read this image. Add the rows manually from the source image before saving final records.</p>
            </div>
          ) : hasLowConfidenceRows ? (
            <div className="ocr-warning" role="status">
              <AlertTriangle size={18} aria-hidden />
              <p>Some extracted values are low confidence. Check every cell against the source image before saving final records.</p>
            </div>
          ) : null}
          <ExtractedRowsTable rows={rows} onRowsChange={setRows} onFocusImage={(imageId) => setSelectedImageId(imageId ?? null)} disabled={isSaving || isFinalizing} />
        </section>
        <ImagePreviewPanel images={batch.images} selectedImageId={selectedImageId} onSelectImage={setSelectedImageId} />
      </div>
    </div>
  );
}
