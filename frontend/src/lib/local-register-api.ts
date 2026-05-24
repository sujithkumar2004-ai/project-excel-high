import { apiFetch } from "@/lib/api";

export type LocalRegisterDraft = {
  success: boolean;
  imagePath: string;
  processedImagePath: string;
  imageUrl: string;
  processedImageUrl: string;
  ocrEngine: string;
  skewAngle: number;
  columns: string[];
  rows: Array<Record<string, string>>;
  rawText: string;
};

export type LocalRegisterExport = {
  success: boolean;
  excelPath: string;
  downloadUrl: string;
  driveFileId: string;
  driveLink: string;
};

export async function createLocalRegisterDraft(file: File) {
  const formData = new FormData();
  formData.append("image", file);
  return apiFetch<LocalRegisterDraft>("/local-register/draft", {
    method: "POST",
    body: formData
  });
}

export async function exportReviewedRegister(columns: string[], rows: Array<Record<string, string>>) {
  return apiFetch<LocalRegisterExport>("/local-register/export", {
    method: "POST",
    body: JSON.stringify({ columns, rows })
  });
}

export function apiAssetUrl(path: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010/api";
  const apiRoot = baseUrl.replace(/\/api\/?$/, "");
  return path.startsWith("/") ? `${apiRoot}${path}` : `${baseUrl.replace(/\/$/, "")}/${path}`;
}
