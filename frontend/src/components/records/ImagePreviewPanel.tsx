"use client";

import { ImageIcon } from "lucide-react";
import { imageFileUrl, type UploadedRecordImage } from "@/lib/records-api";

type ImagePreviewPanelProps = {
  images: UploadedRecordImage[];
  selectedImageId?: number | null;
  onSelectImage: (imageId: number) => void;
};

export function ImagePreviewPanel({ images, selectedImageId, onSelectImage }: ImagePreviewPanelProps) {
  const selectedImage = images.find((image) => image.id === selectedImageId) ?? images[0];

  return (
    <aside className="record-image-panel">
      <div className="section-heading compact">
        <div>
          <h2>
            <ImageIcon size={18} aria-hidden /> Source Image
          </h2>
          <p className="muted">{images.length} uploaded image{images.length === 1 ? "" : "s"}</p>
        </div>
      </div>
      {selectedImage ? <img className="record-source-image" src={imageFileUrl(selectedImage.id)} alt={selectedImage.original_name} /> : <div className="empty-state">No image available</div>}
      <div className="record-image-list">
        {images.map((image) => (
          <button key={image.id} type="button" className={image.id === selectedImage?.id ? "active" : ""} onClick={() => onSelectImage(image.id)}>
            <span>{image.original_name}</span>
            <small>{image.status.replace("_", " ")}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}
