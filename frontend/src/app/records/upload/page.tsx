"use client";

import { Download, Loader2, Plus, Save, Trash2, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import {
  cellCropUrl,
  debugImageUrl,
  emptyOTRow,
  exportOTRegisterUrl,
  otColumns,
  OTApiError,
  recordImageUrl,
  saveOTRegisterData,
  uploadOTRegisterImage,
  type OTCell,
  type OTColumn,
  type OTDebugPaths,
  type OTImageQuality,
  type OTRegisterRecord,
  type OTRegisterRow
} from "@/lib/ot-register-api";

export default function RecordsUploadPage() {
  const { showToast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [record, setRecord] = useState<OTRegisterRecord | null>(null);
  const [rows, setRows] = useState<OTRegisterRow[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [qualityError, setQualityError] = useState("");
  const [failedQuality, setFailedQuality] = useState<OTImageQuality | null>(null);
  const [failedDebugPaths, setFailedDebugPaths] = useState<OTDebugPaths | null>(null);

  const summary = useMemo(() => buildSummary(rows, record), [rows, record]);

  function handleFile(nextFile: File | null) {
    setFile(nextFile);
    setRecord(null);
    setRows([]);
    setSaved(false);
    setQualityError("");
    setFailedQuality(null);
    setFailedDebugPaths(null);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return nextFile ? URL.createObjectURL(nextFile) : "";
    });
  }

  async function uploadAndExtract() {
    if (!file) {
      showToast({ tone: "warning", title: "Choose an image first" });
      return;
    }

    setIsUploading(true);
    setSaved(false);
    try {
      const nextRecord = await uploadOTRegisterImage(file);
      setRecord(nextRecord);
      setRows(nextRecord.rows);
      setQualityError("");
      setFailedQuality(null);
      setFailedDebugPaths(null);
      showToast({ tone: "success", title: "Extraction ready", message: "Review yellow cells before exporting." });
    } catch (error) {
      const detail = error instanceof OTApiError && isQualityFailureDetail(error.detail) ? error.detail : null;
      setFailedQuality(detail?.image_quality ?? null);
      setFailedDebugPaths(detail?.debug_paths ?? null);
      setQualityError(error instanceof Error ? error.message : "Unable to extract register rows");
      showToast({ tone: "error", title: "Extraction failed", message: error instanceof Error ? error.message : "Unable to extract register rows" });
    } finally {
      setIsUploading(false);
    }
  }

  async function saveData() {
    if (!record) return;

    setIsSaving(true);
    try {
      const savedRecord = await saveOTRegisterData(record.id, rows);
      setRecord(savedRecord);
      setRows(savedRecord.rows);
      setSaved(true);
      showToast({ tone: "success", title: "Corrected data saved" });
    } catch (error) {
      showToast({ tone: "error", title: "Save failed", message: error instanceof Error ? error.message : "Unable to save corrected data" });
    } finally {
      setIsSaving(false);
    }
  }

  function updateCell(rowIndex: number, column: OTColumn, value: string) {
    setSaved(false);
    setRows((current) =>
      current.map((row, index) =>
        index === rowIndex
          ? {
              ...row,
              [column]: {
                ...row[column],
                value,
                edited: true
              }
            }
          : row
      )
    );
  }

  function toggleUncertain(rowIndex: number, column: OTColumn) {
    setSaved(false);
    setRows((current) =>
      current.map((row, index) =>
        index === rowIndex
          ? {
              ...row,
              [column]: {
                ...row[column],
                uncertain: !row[column].uncertain,
                edited: true
              }
            }
          : row
      )
    );
  }

  function addRow() {
    setSaved(false);
    setRows((current) => [...current, emptyOTRow()]);
  }

  function removeRow(rowIndex: number) {
    setSaved(false);
    setRows((current) => current.filter((_, index) => index !== rowIndex));
  }

  return (
    <div className="page-container ot-workspace">
      <div className="section-heading">
        <div>
          <h2>OT Register Image to Excel</h2>
          <p className="muted">Local OpenCV table detection, local OCR, human-reviewed Excel output.</p>
        </div>
      </div>

      <section className="ot-top-grid">
        <div className="card ot-upload-card">
          <label
            className={`upload-dropzone ot-dropzone${isDragging ? " dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              handleFile(event.dataTransfer.files[0] ?? null);
            }}
          >
            <Upload size={28} aria-hidden />
            <span>{file ? file.name : "Drop register image here"}</span>
            <small>JPG, PNG, or WebP</small>
            <input type="file" accept="image/jpeg,image/png,image/webp" disabled={isUploading || isSaving} onChange={(event) => handleFile(event.target.files?.[0] ?? null)} />
          </label>

          {previewUrl ? (
            <div className="ot-preview-shell">
              <img src={previewUrl} alt="Uploaded OT register preview" className="ot-preview-image" />
            </div>
          ) : null}
        </div>

        <aside className="card ot-status-card">
          <div>
            <h2>Extraction Status</h2>
            <p className="muted">{isUploading ? "Processing image and cells..." : record ? "Ready for review" : "Waiting for upload"}</p>
          </div>

          <dl className="ot-summary-grid">
            <div>
              <dt>Total rows</dt>
              <dd>{summary.totalRows}</dd>
            </div>
            <div>
              <dt>Uncertain cells</dt>
              <dd>{summary.uncertainCells}</dd>
            </div>
            <div>
              <dt>OCR engine</dt>
              <dd>{summary.engine}</dd>
            </div>
            <div>
              <dt>Average confidence</dt>
              <dd>{Math.round(summary.averageConfidence * 100)}%</dd>
            </div>
          </dl>

          <ImageQualityPanel record={record} error={qualityError} failedQuality={failedQuality} />

          <div className="action-bar">
            <button type="button" className="button" disabled={!file || isUploading || isSaving} onClick={uploadAndExtract}>
              {isUploading ? <Loader2 size={17} className="spin" aria-hidden /> : <Upload size={17} aria-hidden />}
              Upload & Extract
            </button>
            <button type="button" className="button secondary" disabled={!record || isUploading || isSaving} onClick={addRow}>
              <Plus size={16} aria-hidden />
              Add Row
            </button>
          </div>

          {record?.processed_image_url ? (
            <a className="ot-processed-link" href={recordImageUrl(record.processed_image_url)} target="_blank" rel="noreferrer">
              View processed table image
            </a>
          ) : null}
        </aside>
      </section>

      <DebugView debugPaths={failedDebugPaths ?? record?.debug_paths ?? null} failed={Boolean(failedDebugPaths)} />

      <section className="card ot-review-card">
        <div className="section-heading compact">
          <div>
            <h2>Extracted Rows</h2>
            <p className="muted">Rows appear below the image preview. Edit values, clear or mark uncertainty, then save.</p>
          </div>
          <div className="action-bar">
            <button type="button" className="button secondary" disabled={!record || isSaving || isUploading} onClick={saveData}>
              {isSaving ? <Loader2 size={17} className="spin" aria-hidden /> : <Save size={17} aria-hidden />}
              Save Corrected Data
            </button>
            <a className={`button${!record || !saved ? " disabled-link" : ""}`} href={record && saved ? exportOTRegisterUrl(record.id) : undefined} aria-disabled={!record || !saved}>
              <Download size={17} aria-hidden />
              Export Excel
            </a>
          </div>
        </div>

        <OTRegisterTable recordId={record?.id} rows={rows} disabled={!record || isUploading || isSaving} onUpdateCell={updateCell} onToggleUncertain={toggleUncertain} onRemoveRow={removeRow} />
      </section>
    </div>
  );
}

type OTRegisterTableProps = {
  recordId?: string;
  rows: OTRegisterRow[];
  disabled: boolean;
  onUpdateCell: (rowIndex: number, column: OTColumn, value: string) => void;
  onToggleUncertain: (rowIndex: number, column: OTColumn) => void;
  onRemoveRow: (rowIndex: number) => void;
};

function OTRegisterTable({ recordId, rows, disabled, onUpdateCell, onToggleUncertain, onRemoveRow }: OTRegisterTableProps) {
  if (!rows.length) {
    return <div className="empty-state ot-empty-state">Upload an OT register image to extract rows, or add a row after upload.</div>;
  }

  return (
    <div className="table-wrap ot-table-wrap">
      <table className="ot-edit-table">
        <thead>
          <tr>
            {otColumns.map((column) => (
              <th key={column}>{column}</th>
            ))}
            <th>Row confidence</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {otColumns.map((column) => {
                const cell = ensureCell(row[column]);
                const cropUrl = recordId ? cellCropUrl(recordId, cell.cell_crop_path) : "";
                return (
                  <td key={column} className={cell.uncertain ? "uncertain-cell" : undefined}>
                    <input aria-label={`${column} row ${rowIndex + 1}`} value={cell.value} disabled={disabled} onChange={(event) => onUpdateCell(rowIndex, column, event.target.value)} />
                    <div className="cell-review-row">
                      <label>
                        <input type="checkbox" checked={cell.uncertain} disabled={disabled} onChange={() => onToggleUncertain(rowIndex, column)} />
                        Uncertain
                      </label>
                      <span>{Math.round(cell.confidence * 100)}%</span>
                    </div>
                    {cropUrl ? (
                      <a className="cell-crop-link" href={cropUrl} target="_blank" rel="noreferrer">
                        Crop
                        <img src={cropUrl} alt={`${column} crop row ${rowIndex + 1}`} />
                      </a>
                    ) : null}
                  </td>
                );
              })}
              <td>{Math.round(rowConfidence(row) * 100)}%</td>
              <td>
                <button type="button" className="icon-button danger" disabled={disabled} aria-label={`Delete row ${rowIndex + 1}`} onClick={() => onRemoveRow(rowIndex)}>
                  <Trash2 size={15} aria-hidden />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ensureCell(cell: OTCell | undefined): OTCell {
  return cell ?? { value: "", confidence: 0, uncertain: true, edited: false, cell_crop_path: "", ocr_text: "", original_value: "" };
}

function rowConfidence(row: OTRegisterRow) {
  const values = otColumns.map((column) => ensureCell(row[column]).confidence);
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function buildSummary(rows: OTRegisterRow[], record: OTRegisterRecord | null) {
  const totalCells = rows.length * otColumns.length;
  const uncertainCells = rows.reduce((total, row) => total + otColumns.filter((column) => ensureCell(row[column]).uncertain).length, 0);
  const confidenceTotal = rows.reduce((total, row) => total + otColumns.reduce((rowTotal, column) => rowTotal + ensureCell(row[column]).confidence, 0), 0);
  return {
    totalRows: rows.length || record?.summary.total_rows || 0,
    uncertainCells: uncertainCells || record?.summary.uncertain_cells_count || 0,
    engine: record?.summary.ocr_engine_used || "-",
    averageConfidence: totalCells ? confidenceTotal / totalCells : record?.summary.average_confidence || 0
  };
}

function ImageQualityPanel({ record, error, failedQuality }: { record: OTRegisterRecord | null; error: string; failedQuality: OTImageQuality | null }) {
  const quality = failedQuality ?? record?.image_quality;
  if (error && !quality) {
    return <div className="quality-panel error">{error}</div>;
  }
  if (!quality) {
    return <div className="quality-panel neutral">Image quality will appear after extraction.</div>;
  }
  return (
    <div className={`quality-panel ${quality.valid ? "ok" : "error"}`}>
      <div className="quality-score">
        <span>Image quality</span>
        <strong>{quality.score}/100</strong>
      </div>
      <dl>
        <div><dt>Blur</dt><dd>{quality.metrics.blur_score}</dd></div>
        <div><dt>Contrast</dt><dd>{quality.metrics.contrast}</dd></div>
        <div><dt>Rotation</dt><dd>{quality.metrics.rotation_angle} deg</dd></div>
        <div><dt>Cells</dt><dd>{quality.metrics.cell_count}</dd></div>
        <div><dt>Lines</dt><dd>{quality.metrics.horizontal_line_count ?? 0}H / {quality.metrics.vertical_line_count ?? 0}V</dd></div>
      </dl>
      {error ? <p>{error}</p> : null}
      {[...quality.issues, ...quality.warnings].length ? <p>{[...quality.issues, ...quality.warnings].join(", ")}</p> : null}
    </div>
  );
}

function DebugView({ debugPaths, failed }: { debugPaths: OTDebugPaths | null; failed: boolean }) {
  if (!debugPaths || !Object.keys(debugPaths).length) return null;
  const items = [
    ["original", "Original"],
    ["deskewed", "Deskewed"],
    ["perspective_corrected", "Perspective"],
    ["threshold", "Threshold"],
    ["detected_lines", "Detected lines"],
    ["detected_cells", "Detected cells"]
  ] as const;

  return (
    <section className={`card debug-card${failed ? " failed" : ""}`}>
      <div className="section-heading compact">
        <div>
          <h2>Debug View</h2>
          <p className="muted">{failed ? "Extraction failed, but these images show where preprocessing and table detection stopped." : "Preprocessing and table detection checkpoints."}</p>
        </div>
      </div>
      <div className="debug-grid">
        {items.map(([key, label]) => {
          const url = debugImageUrl(debugPaths[key]);
          if (!url) return null;
          return (
            <a key={key} href={url} target="_blank" rel="noreferrer" className="debug-tile">
              <span>{label}</span>
              <img src={url} alt={`${label} debug output`} />
            </a>
          );
        })}
      </div>
    </section>
  );
}

function isQualityFailureDetail(detail: unknown): detail is { image_quality: OTImageQuality; debug_paths: OTDebugPaths } {
  return typeof detail === "object" && detail !== null && "image_quality" in detail;
}
