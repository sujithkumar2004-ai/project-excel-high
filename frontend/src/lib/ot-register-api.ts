const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8011/api";
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
  ocr_text?: string;
  original_value?: string;
  confidence: number;
  uncertain: boolean;
  edited?: boolean;
  cell_crop_path?: string;
};

export type OTRegisterRow = Record<OTColumn, OTCell>;

export type OTRegisterSummary = {
  total_rows: number;
  total_cells?: number;
  uncertain_cells?: number;
  uncertain_cells_count: number;
  edited_cells_count: number;
  average_confidence: number;
  ocr_engine_used: string;
};

export type OTImageQuality = {
  valid: boolean;
  score: number;
  issues: string[];
  warnings: string[];
  metrics: {
    blur_score: number;
    brightness: number;
    contrast: number;
    rotation_angle: number;
    table_detected: boolean;
    table_detected_raw?: boolean;
    table_detected_processed?: boolean;
    low_quality?: boolean;
    horizontal_line_count?: number;
    vertical_line_count?: number;
    row_count: number;
    column_count: number;
    cell_count: number;
  };
};

export type OTDebugPaths = Partial<Record<"original" | "deskewed" | "perspective_corrected" | "threshold" | "detected_lines" | "detected_cells", string>>;

export type OTRegisterRecord = {
  id: string;
  record_id?: string;
  ocr_engine?: string;
  image_quality?: OTImageQuality;
  columns: OTColumn[];
  rows: OTRegisterRow[];
  summary: OTRegisterSummary;
  image_url: string;
  processed_image_url: string;
  debug_paths?: OTDebugPaths;
  low_quality?: boolean;
  warnings?: string[];
  created_at?: string;
  saved_at?: string;
};

export class OTApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "OTApiError";
    this.status = status;
    this.detail = detail;
  }
}

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
    let detail: unknown;
    try {
      const payload = await response.json();
      detail = payload.detail;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail?.message) {
        const issues = payload.detail.image_quality?.issues?.join(", ");
        message = issues ? `${payload.detail.message}: ${issues}` : payload.detail.message;
      } else {
        message = payload.message || message;
      }
    } catch {
      // Keep HTTP status fallback for file/error responses.
    }
    throw new OTApiError(message, response.status, detail);
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

export function debugImageUrl(path?: string) {
  return path ? `${API_ROOT_URL}${path}` : "";
}

export function cellCropUrl(recordId: string, cropPath?: string) {
  if (!cropPath) return "";
  const cropName = cropPath.split("/").pop();
  return cropName ? `${API_ROOT_URL}/records/${recordId}/cells/${cropName}` : "";
}

export function emptyOTRow(): OTRegisterRow {
  return Object.fromEntries(
    otColumns.map((column) => [
      column,
      {
        value: "",
        confidence: 0,
        uncertain: true,
        edited: true,
        ocr_text: "",
        original_value: "",
        cell_crop_path: ""
      }
    ])
  ) as OTRegisterRow;
}
