import { CalendarClock, FileSpreadsheet, Image as ImageIcon, Rows3 } from "lucide-react";
import type { RecordBatch } from "@/lib/records-api";

export function BatchStatusCard({ batch }: { batch: RecordBatch }) {
  return (
    <div className="record-status-card">
      <div>
        <span className={`badge ${statusTone(batch.status)}`}>{batch.status.replace("_", " ")}</span>
        <h2>{batch.batch_code}</h2>
      </div>
      <dl>
        <div>
          <ImageIcon size={18} aria-hidden />
          <dt>Images</dt>
          <dd>{batch.total_images}</dd>
        </div>
        <div>
          <Rows3 size={18} aria-hidden />
          <dt>Rows</dt>
          <dd>{batch.total_rows}</dd>
        </div>
        <div>
          <CalendarClock size={18} aria-hidden />
          <dt>Created</dt>
          <dd>{new Date(batch.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <FileSpreadsheet size={18} aria-hidden />
          <dt>Excel</dt>
          <dd>{batch.excel_file_path ? "Ready" : "Pending"}</dd>
        </div>
      </dl>
    </div>
  );
}

function statusTone(status: string) {
  if (status === "completed") return "ok";
  if (status === "failed") return "danger";
  if (status === "processing" || status === "review_pending") return "warn";
  return "neutral";
}
