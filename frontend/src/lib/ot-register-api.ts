const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010/api";
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/?$/, "");

export const otColumns = [
  "S.No",
  "UHID",
  "Patient Name",
  "Age/Sex",
  "Provisional Diagnosis",
  "Procedure",
  "Final Diagnosis",
  "Anaesthetist",
  "OT No",
  "Date",
  "Start Time",
  "End Time"
] as const;

export type OTColumn = (typeof otColumns)[number];

export type OTCell = {
  value: string;
  confidence: number;
  uncertain: boolean;
  edited?: boolean;
};

export type OTRegisterRow = Record<OTColumn, OTCell>;

export type OTRegisterSummary = {
  total_rows: number;
  uncertain_cells_count: number;
  edited_cells_count: number;
  average_confidence: number;
  ocr_engine_used: string;
};

export type OTRegisterRecord = {
  id: string;
  columns: OTColumn[];
  rows: OTRegisterRow[];
  summary: OTRegisterSummary;
  image_url: string;
  processed_image_url: string;
  created_at?: string;
  saved_at?: string;
};

async function fetchRoot<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_ROOT_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `API request failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
    } catch {
      // Keep HTTP status fallback for file/error responses.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function uploadOTRegisterImage(file: File) {
  const formData = new FormData();
  formData.append("image", file);
  return fetchRoot<OTRegisterRecord>("/records/upload", {
    method: "POST",
    body: formData
  });
}

export async function saveOTRegisterData(id: string, rows: OTRegisterRow[]) {
  return fetchRoot<OTRegisterRecord>(`/records/${id}/save-corrections`, {
    method: "POST",
    body: JSON.stringify({ columns: otColumns, rows })
  });
}

export function exportOTRegisterUrl(id: string) {
  return `${API_ROOT_URL}/records/${id}/export-excel`;
}

export function recordImageUrl(path: string) {
  return `${API_ROOT_URL}${path}`;
}

export function emptyOTRow(): OTRegisterRow {
  return Object.fromEntries(
    otColumns.map((column) => [
      column,
      {
        value: "",
        confidence: 0,
        uncertain: true,
        edited: true
      }
    ])
  ) as OTRegisterRow;
}
