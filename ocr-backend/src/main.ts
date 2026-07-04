import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import * as express from 'express';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Cấu hình tăng giới hạn kích thước file nhận vào hệ thống
  app.use(express.json({ limit: '50mb' }));
  app.use(express.urlencoded({ limit: '50mb', extended: true }));

  // Bật CORS để cho phép Frontend từ Vite (thường chạy cổng 5173) gọi API sang
  app.enableCors();

  await app.listen(3000);
  console.log('--- BACKEND ĐỒ ÁN OCR ĐANG CHẠY TẠI CỔNG: http://localhost:3000 ---');
}
bootstrap();