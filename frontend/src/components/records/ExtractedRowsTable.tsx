"use client";

import { Plus, Trash2 } from "lucide-react";
import { emptyRecordRow, type ExtractedRecordRow } from "@/lib/records-api";

type ExtractedRowsTableProps = {
  rows: ExtractedRecordRow[];
  onRowsChange: (rows: ExtractedRecordRow[]) => void;
  onFocusImage?: (imageId: number | null | undefined) => void;
  disabled?: boolean;
};

const columns: Array<{ key: keyof ExtractedRecordRow; label: string; className?: string }> = [
  { key: "hospital_registration_no", label: "Hospital Reg. No" },
  { key: "patient_name", label: "Patient" },
  { key: "age", label: "Age/Sex" },
  { key: "provisional_diagnosis", label: "Provisional Diagnosis", className: "wide" },
  { key: "procedure_name", label: "Procedure", className: "wide" },
  { key: "final_diagnosis", label: "Final Diagnosis", className: "wide" },
  { key: "surgeon_name", label: "Surgeon / Anesthetist / Staff", className: "wide" },
  { key: "ot_number", label: "OT No" },
  { key: "procedure_date", label: "Date" },
  { key: "start_time", label: "Start" },
  { key: "end_time", label: "End" },
  { key: "anesthesia_type", label: "Anesthesia" }
];

export function ExtractedRowsTable({ rows, onRowsChange, onFocusImage, disabled }: ExtractedRowsTableProps) {
  function updateCell(index: number, key: keyof ExtractedRecordRow, value: string) {
    onRowsChange(rows.map((row, rowIndex) => (rowIndex === index ? { ...row, [key]: value } : row)));
  }

  function removeRow(index: number) {
    onRowsChange(rows.filter((_, rowIndex) => rowIndex !== index).map((row, rowIndex) => ({ ...row, row_number: rowIndex + 1 })));
  }

  return (
    <div className="records-table-shell">
      <div className="action-bar table-actions">
        <button type="button" className="button secondary" disabled={disabled} onClick={() => onRowsChange([...rows, emptyRecordRow(rows.length + 1)])}>
          <Plus size={16} aria-hidden /> Add row
        </button>
      </div>
      <div className="table-wrap records-edit-table-wrap">
        <table className="records-edit-table">
          <thead>
            <tr>
              <th>S.No</th>
              {columns.map((column) => (
                <th key={column.key as string} className={column.className}>{column.label}</th>
              ))}
              <th>Confidence</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id ?? `new-${index}`} onFocus={() => onFocusImage?.(row.image_id)}>
                <td>{index + 1}</td>
                {columns.map((column) => (
                  <td key={column.key as string} className={column.className}>
                    <input
                      aria-label={`${column.label} row ${index + 1}`}
                      value={String(row[column.key] ?? "")}
                      disabled={disabled}
                      onChange={(event) => updateCell(index, column.key, event.target.value)}
                    />
                  </td>
                ))}
                <td>{Math.round((row.extraction_confidence || 0) * 100)}%</td>
                <td>
                  <button type="button" className="icon-button danger" disabled={disabled} aria-label={`Remove row ${index + 1}`} onClick={() => removeRow(index)}>
                    <Trash2 size={15} aria-hidden />
                  </button>
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={14}>No rows extracted yet. Add rows manually before final save.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
