export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface OCRLine {
  line_id: number;
  text: string;
  bbox: BoundingBox;
}

export interface OCRPage {
  page: number;
  width: number;
  height: number;
  lines: OCRLine[];
}

export interface OCRResult {
  filename: string;
  total_pages?: number; // Có nếu là PDF
  lines?: OCRLine[];    // Có nếu là ảnh đơn lẻ
  pages?: OCRPage[];    // Có nếu là PDF
}