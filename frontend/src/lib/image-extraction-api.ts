import { apiFetch } from "@/lib/api";

export type ImageExtractionData = {
  extracted_text: string;
  rows: Array<Record<string, string>>;
  fields: Record<string, string>;
};

export type ImageExtractionResponse = {
  success: boolean;
  data: ImageExtractionData;
  excel_filename: string;
  excel_download_url: string;
};

export type LoginResponse = {
  success: boolean;
  token: string;
  username: string;
};

const API_BASE_URL = "/api";

export async function login(username: string, password: string) {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export async function extractImage(file: File, token: string) {
  const formData = new FormData();
  formData.append("image", file);
  return apiFetch<ImageExtractionResponse>("/extract-image", {
    method: "POST",
    body: formData,
    headers: authHeaders(token)
  });
}

export async function downloadExcel(path: string, token: string) {
  const response = await fetch(`${API_BASE_URL}${path.replace(/^\/api/, "")}`, {
    headers: authHeaders(token)
  });
  if (!response.ok) {
    let message = `Download failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
    } catch {
      // Keep status fallback.
    }
    throw new Error(message);
  }
  return response.blob();
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}
