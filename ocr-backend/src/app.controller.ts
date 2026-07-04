import { Controller, Post, UseInterceptors, UploadedFile, Res } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { AppService } from './app.service';
import { Response } from 'express';
import { Multer } from 'multer';

@Controller('ocr')
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Post('upload')
  @UseInterceptors(FileInterceptor('file'))
  async uploadFile(@UploadedFile() file: Express.Multer.File, @Res() res: Response) {
    const fileBuffer = await this.appService.forwardToOcrEngine(file);
    
    // Thiết lập các header tải file chuẩn quốc tế
    res.set({
      'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'Content-Disposition': 'attachment; filename="ocr_result.docx"',
      // 🔥 QUAN TRỌNG: Cho phép Frontend đọc được các header cấu hình file này
      'Access-Control-Expose-Headers': 'Content-Disposition', 
    });
    
    // Gửi trực tiếp buffer nhị phân về cho Frontend
    res.send(fileBuffer);
  }
}