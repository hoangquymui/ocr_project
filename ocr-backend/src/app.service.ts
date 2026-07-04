import { Injectable, InternalServerErrorException } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import FormData = require('form-data');

@Injectable()
export class AppService {
  // 💡 MẸO DOCKER: Nếu chạy NestJS ngoài máy thật -> dùng 'http://localhost:8000'
  // Nếu NestJS chạy trong Docker chung với FastAPI -> hãy đổi 'localhost' thành tên container của FastAPI (ví dụ: 'http://ocr-core-running:8000')
  private readonly OCR_ENGINE_URL = 'http://localhost:8000';

  constructor(private readonly httpService: HttpService) {}

  async forwardToOcrEngine(file: Express.Multer.File):Promise<Buffer> {
    const formData = new FormData();
    
    // Tái cấu trúc file buffer để truyền tải qua API Gateway sang AI Core
    formData.append('file', file.buffer, {
      filename: file.originalname,
      contentType: file.mimetype,
    });

    // 🔥 ĐỒNG BỘ ENDPOINT: Trỏ thẳng vào endpoint duy nhất mà FastAPI đang sở hữu
    const endpoint = '/api/v1/pipeline/ocr';

    try {
      const response = await firstValueFrom(
        this.httpService.post(`${this.OCR_ENGINE_URL}${endpoint}`, formData, {
          headers: {
            ...formData.getHeaders(),
          },
          // Trả file Word dạng Stream/Buffer về, cấu hình nhận dạng dữ liệu lớn
          responseType: 'arraybuffer', 
          maxContentLength: Infinity,
          maxBodyLength: Infinity,
        }),
      );
      
      return Buffer.from(response.data);
    } catch (error: any) {
      // Bóc tách lỗi chi tiết từ FastAPI trả về để dễ debug
      console.error('Lỗi kết nối đến OCR Engine:', error.response?.data || error.message);
      throw new InternalServerErrorException(
        `Lỗi kết nối đến OCR Engine: ${error.response?.statusText || error.message}`
      );
    }
  }
}