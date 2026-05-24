import { apiFetch } from "@/lib/api";

export type BatchStatus = "uploaded" | "processing" | "review_pending" | "completed" | "failed";

export type UploadedRecordImage = {
  id: number;
  batch_id: number;
  file_name: string;
  file_path: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  status: string;
  created_at: string;
};

export type ExtractedRecordRow = {
  id?: number | null;
  batch_id?: number;
  image_id?: number | null;
  row_number: number;
  hospital_registration_no: string;
  patient_name: string;
  age: string;
  provisional_diagnosis: string;
  procedure_name: string;
  final_diagnosis: string;
  surgeon_name: string;
  ot_number: string;
  procedure_date: string;
  start_time: string;
  end_time: string;
  anesthesia_type: string;
  extraction_confidence: number;
  is_reviewed?: boolean;
  is_final?: boolean;
};

export type RecordBatch = {
  id: number;
  batch_code: string;
  total_images: number;
  total_rows: number;
  status: BatchStatus;
  excel_file_path?: string | null;
  created_at: string;
  updated_at: string;
};

export type RecordBatchDetail = RecordBatch & {
  images: UploadedRecordImage[];
  rows: ExtractedRecordRow[];
};

export async function uploadRecordBatch(files: File[]) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiFetch<{ batch_id: number; batch_code: string; total_images: number; status: BatchStatus }>("/record-batches/upload", {
    method: "POST",
    body: formData
  });
}

export async function analyzeRecordBatch(batchId: number) {
  return apiFetch<{ batch: RecordBatch; rows: ExtractedRecordRow[] }>(`/record-batches/${batchId}/analyze`, { method: "POST" });
}

export async function getRecordBatch(batchId: number) {
  return apiFetch<RecordBatchDetail>(`/record-batches/${batchId}`);
}

export async function updateRecordRows(batchId: number, rows: ExtractedRecordRow[]) {
  return apiFetch<ExtractedRecordRow[]>(`/record-batches/${batchId}/rows`, {
    method: "PUT",
    body: JSON.stringify({ rows })
  });
}

export async function finalizeRecordBatch(batchId: number) {
  return apiFetch<{ batch: RecordBatch; excel_url: string }>(`/record-batches/${batchId}/finalize`, { method: "POST" });
}

export async function listRecordBatches(page = 1, pageSize = 20) {
  return apiFetch<{ items: RecordBatch[]; total: number; page: number; page_size: number }>(`/record-batches?page=${page}&page_size=${pageSize}`);
}

export function imageFileUrl(imageId: number) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010/api";
  return `${baseUrl}/record-batches/images/${imageId}/file`;
}

export function excelFileUrl(batchId: number) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010/api";
  return `${baseUrl}/record-batches/${batchId}/excel`;
}

export function emptyRecordRow(rowNumber: number): ExtractedRecordRow {
  return {
    row_number: rowNumber,
    image_id: null,
    hospital_registration_no: "",
    patient_name: "",
    age: "",
    provisional_diagnosis: "",
    procedure_name: "",
    final_diagnosis: "",
    surgeon_name: "",
    ot_number: "",
    procedure_date: "",
    start_time: "",
    end_time: "",
    anesthesia_type: "",
    extraction_confidence: 0
  };
}
