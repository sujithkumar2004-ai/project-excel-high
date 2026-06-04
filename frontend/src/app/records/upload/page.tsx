"use client";

import { Download, FileImage, Loader2, LogOut, Upload } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { downloadExcel, extractImage, login, type ImageExtractionData, type ImageExtractionResponse } from "@/lib/image-extraction-api";

const SESSION_TOKEN_KEY = "project_excel_auth_token";
const SESSION_USER_KEY = "project_excel_auth_user";

export default function RecordsUploadPage() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [response, setResponse] = useState<ImageExtractionResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const result = response?.data ?? null;
  const columns = useMemo(() => getColumns(result), [result]);

  useEffect(() => {
    setToken(sessionStorage.getItem(SESSION_TOKEN_KEY) ?? "");
    setUsername(sessionStorage.getItem(SESSION_USER_KEY) ?? "");
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoggingIn(true);
    setLoginError("");
    try {
      const auth = await login(loginUsername.trim(), loginPassword);
      sessionStorage.setItem(SESSION_TOKEN_KEY, auth.token);
      sessionStorage.setItem(SESSION_USER_KEY, auth.username);
      setToken(auth.token);
      setUsername(auth.username);
      setLoginPassword("");
    } catch (authError) {
      setLoginError(authError instanceof Error ? authError.message : "Login failed");
    } finally {
      setIsLoggingIn(false);
    }
  }

  function logout() {
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
    sessionStorage.removeItem(SESSION_USER_KEY);
    setToken("");
    setUsername("");
    chooseFile(null);
  }

  function chooseFile(nextFile: File | null) {
    setFile(nextFile);
    setResponse(null);
    setError("");
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return nextFile ? URL.createObjectURL(nextFile) : "";
    });
  }

  async function uploadAndExtract() {
    if (!file || !token) return;
    setIsLoading(true);
    setError("");
    setResponse(null);

    try {
      const nextResponse = await extractImage(file, token);
      setResponse(nextResponse);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to extract image data");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDownload() {
    if (!response || !token) return;
    setIsDownloading(true);
    setError("");
    try {
      const blob = await downloadExcel(response.excel_download_url, token);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "Project_Excel_Extraction.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Unable to download Excel file");
    } finally {
      setIsDownloading(false);
    }
  }

  if (!token) {
    return (
      <div className="page-container simple-extraction-page">
        <section className="simple-hero">
          <span className="simple-eyebrow">Project Excel Secure</span>
          <h1>Login to extract Excel</h1>
          <p>Use the temporary credentials to access the image-to-Excel workflow.</p>
        </section>

        <form className="card login-card" onSubmit={handleLogin}>
          <label>
            <span>Login ID</span>
            <input value={loginUsername} autoComplete="username" placeholder="SK001" onChange={(event) => setLoginUsername(event.target.value)} />
          </label>
          <label>
            <span>Password</span>
            <input value={loginPassword} type="password" autoComplete="current-password" placeholder="Enter password" onChange={(event) => setLoginPassword(event.target.value)} />
          </label>
          <button type="submit" className="button" disabled={isLoggingIn || !loginUsername || !loginPassword}>
            {isLoggingIn ? <Loader2 size={18} className="spin" aria-hidden /> : null}
            Login
          </button>
          {loginError ? <p className="simple-error">{loginError}</p> : null}
        </form>
      </div>
    );
  }

  return (
    <div className="page-container simple-extraction-page">
      <section className="simple-hero">
        <div className="simple-session-row">
          <span className="simple-eyebrow">Logged in as {username}</span>
          <button type="button" className="button secondary compact-button" onClick={logout}>
            <LogOut size={15} aria-hidden />
            Logout
          </button>
        </div>
        <h1>Image to Excel</h1>
        <p>Upload one image. The Python backend sends it to OpenAI, extracts structured data, and creates a downloadable Excel workbook.</p>
      </section>

      <section className="card simple-upload-card">
        <label
          className={`upload-dropzone simple-dropzone${isDragging ? " dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            chooseFile(event.dataTransfer.files[0] ?? null);
          }}
        >
          <Upload size={30} aria-hidden />
          <span>{file ? file.name : "Drop an image here or click to browse"}</span>
          <small>JPG, PNG, WebP, or GIF. One image at a time.</small>
          <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={isLoading} onChange={(event) => chooseFile(event.target.files?.[0] ?? null)} />
        </label>

        {previewUrl ? (
          <div className="simple-preview">
            <img src={previewUrl} alt="Selected image preview" />
            <div>
              <strong>{file?.name}</strong>
              <span>{file ? formatBytes(file.size) : ""}</span>
            </div>
          </div>
        ) : null}

        <div className="action-bar">
          <button type="button" className="button simple-submit" disabled={!file || isLoading} onClick={uploadAndExtract}>
            {isLoading ? <Loader2 size={18} className="spin" aria-hidden /> : <FileImage size={18} aria-hidden />}
            {isLoading ? "Analyzing image..." : "Analyze & Create Excel"}
          </button>
          <button type="button" className="button secondary simple-submit" disabled={!response || isDownloading} onClick={handleDownload}>
            {isDownloading ? <Loader2 size={18} className="spin" aria-hidden /> : <Download size={18} aria-hidden />}
            Download Excel
          </button>
        </div>

        {error ? <p className="simple-error">{error}</p> : null}
      </section>

      {isLoading ? (
        <section className="card simple-loading">
          <Loader2 size={22} className="spin" aria-hidden />
          <span>OpenAI is reading the image. The backend will create the Excel file when extraction finishes.</span>
        </section>
      ) : null}

      {result ? (
        <section className="card simple-result-card">
          <div>
            <span className="simple-eyebrow">Extraction ready</span>
            <h2>Preview before Excel</h2>
            <p className="muted">The workbook includes Extracted Rows, Fields, and Raw Text sheets.</p>
          </div>

          {result.rows.length && columns.length ? (
            <div className="table-wrap simple-table-wrap">
              <table>
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, index) => (
                    <tr key={index}>
                      {columns.map((column) => (
                        <td key={column}>{row[column] ?? ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {Object.keys(result.fields).length ? (
            <div className="fields-grid">
              {Object.entries(result.fields).map(([key, value]) => (
                <div key={key}>
                  <span>{key}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          ) : null}

          <details>
            <summary>Raw extracted text</summary>
            <pre>{result.extracted_text || "No raw text returned."}</pre>
          </details>
        </section>
      ) : null}
    </div>
  );
}

function getColumns(result: ImageExtractionData | null) {
  if (!result) return [];
  const columns: string[] = [];
  const seen = new Set<string>();
  for (const row of result.rows) {
    for (const column of Object.keys(row)) {
      if (!seen.has(column)) {
        seen.add(column);
        columns.push(column);
      }
    }
  }
  return columns;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
