"use client";

import { UploadCloud, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";

type ImageUploaderProps = {
  files: File[];
  onFilesChange: (files: File[]) => void;
  disabled?: boolean;
};

const allowedTypes = ["image/jpeg", "image/png", "image/webp"];

export function ImageUploader({ files, onFilesChange, disabled }: ImageUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const previews = useMemo(() => files.map((file) => ({ file, url: URL.createObjectURL(file) })), [files]);

  function addFiles(fileList: FileList | File[]) {
    const next = Array.from(fileList).filter((file) => allowedTypes.includes(file.type));
    onFilesChange([...files, ...next]);
  }

  return (
    <div className="records-uploader">
      <button
        type="button"
        className={`upload-dropzone ${isDragging ? "dragging" : ""}`}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          addFiles(event.dataTransfer.files);
        }}
      >
        <UploadCloud size={30} aria-hidden />
        <span>Drop hospital record images here</span>
        <small>JPG, PNG, or WEBP</small>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        disabled={disabled}
        onChange={(event) => {
          if (event.target.files) addFiles(event.target.files);
          event.target.value = "";
        }}
      />
      <div className="records-count">Total images selected: {files.length}</div>
      {previews.length ? (
        <div className="image-preview-grid">
          {previews.map(({ file, url }, index) => (
            <div className="image-preview-tile" key={`${file.name}-${file.lastModified}-${index}`}>
              <img src={url} alt={file.name} />
              <div>
                <strong>{file.name}</strong>
                <span>{Math.round(file.size / 1024)} KB</span>
              </div>
              <button type="button" aria-label={`Remove ${file.name}`} onClick={() => onFilesChange(files.filter((_, itemIndex) => itemIndex !== index))}>
                <X size={16} aria-hidden />
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
