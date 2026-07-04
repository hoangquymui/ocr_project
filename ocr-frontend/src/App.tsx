import React, { useState } from 'react';
import axios from 'axios';

// Định nghĩa cấu trúc dữ liệu cho một file đã được xử lý xong
interface ProcessedFile {
  id: string;
  originalName: string;
  downloadName: string;
  blobUrl: string; // Đường dẫn ảo lưu trong RAM để bấm tải lại nhanh
  timestamp: string;
  size: string;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  // State lưu danh sách các file đã OCR thành công
  const [processedFiles, setProcessedFiles] = useState<ProcessedFile[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Vui lòng chọn một file trước.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    setError(null);

    try {
      // 1. Gọi đến NestJS nhận dữ liệu nhị phân (Blob)
      const response = await axios.post('http://localhost:3000/ocr/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob', 
      });

      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });

      // 2. Tạo URL ảo cố định trong RAM cho file này
      const url = window.URL.createObjectURL(blob);

      // 3. Tính toán tên file Word kết quả
      const baseName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      const downloadFilename = `${baseName}_ocr.docx`;

      // 4. Kích hoạt tải xuống tự động lần đầu cho người dùng tiện lợi
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', downloadFilename);
      document.body.appendChild(link);
      link.click();
      if (link.parentNode) link.parentNode.removeChild(link);

      // 5. Đẩy thông tin file vừa làm xong vào danh sách hiển thị trên giao diện
      const newProcessedFile: ProcessedFile = {
        id: Math.random().toString(36).substr(2, 9),
        originalName: file.name,
        downloadName: downloadFilename,
        blobUrl: url, // Giữ lại URL này để nút "Tải xuống" trên giao diện hoạt động tức thì không cần gọi lại API
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
        size: (file.size / 1024 / 1024).toFixed(2) + ' MB'
      };

      setProcessedFiles(prev => [newProcessedFile, ...prev]); // Thêm file mới lên đầu danh sách
      setFile(null); // Reset khung chọn file để sẵn sàng cho file tiếp theo

    } catch (err: any) {
      if (err.response?.data instanceof Blob) {
        const textError = await err.response.data.text();
        try {
          const jsonError = JSON.parse(textError);
          setError(jsonError.message || 'Có lỗi xảy ra trong quá trình xử lý OCR.');
        } catch {
          setError('Có lỗi xảy ra khi tải file lên.');
        }
      } else {
        setError(err.response?.data?.message || 'Không thể kết nối đến máy chủ.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '700px', margin: '5px auto', padding: '40px 20px', fontFamily: 'system-ui, sans-serif', color: '#333' }}>
      <h2 style={{ textAlign: 'center', color: '#111', marginBottom: '8px' }}>Hệ Thống Chuyển Đổi Tài Liệu (OCR Pipeline)</h2>
      <p style={{ textAlign: 'center', color: '#666', fontSize: '14px', marginTop: '0', marginBottom: '30px' }}>
        Hỗ trợ file PDF đa trang hoặc file Ảnh (JPG, PNG) ➡️ Trích xuất trực tiếp ra file Word (.docx)
      </p>
      
      {/* Khung tải file đầu vào */}
      <div style={{ border: '2px dashed #0070f3', padding: '30px 20px', textAlign: 'center', borderRadius: '12px', backgroundColor: '#fcfcfc' }}>
        <input type="file" accept="image/*,application/pdf" onChange={handleFileChange} style={{ cursor: 'pointer' }} />
        {file && (
          <p style={{ marginTop: '15px', color: '#333', fontSize: '14px' }}>
            📄 File sẵn sàng: <strong style={{ color: '#0070f3' }}>{file.name}</strong> ({ (file.size / 1024 / 1024).toFixed(2) } MB)
          </p>
        )}
      </div>

      <button 
        onClick={handleUpload} 
        disabled={loading}
        style={{ 
          marginTop: '20px', padding: '12px 20px', 
          backgroundColor: loading ? '#ccc' : '#0070f3', color: '#fff', 
          border: 'none', borderRadius: '6px', 
          cursor: loading ? 'not-allowed' : 'pointer', fontSize: '16px',
          fontWeight: 'bold', width: '100%'
        }}
      >
        {loading ? '🤖 Đang trích xuất & cấu trúc lại văn bản...' : '🚀 Bắt đầu OCR & Kết xuất Word'}
      </button>

      {error && (
        <div style={{ color: '#d32f2f', backgroundColor: '#ffebee', padding: '12px', borderRadius: '6px', marginTop: '20px', fontSize: '14px', border: '1px solid #ffcdd2' }}>
          ⚠️ <strong>Lỗi:</strong> {error}
        </div>
      )}

      {/* KHU VỰC HIỂN THỊ FILE ĐÃ SỬA VÀ NÚT TẢI XUỐNG */}
      {processedFiles.length > 0 && (
        <div style={{ marginTop: '40px' }}>
          <h3 style={{ borderBottom: '2px solid #eee', paddingBottom: '8px', color: '#222' }}>📊 Danh sách kết quả đã trích xuất</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '15px' }}>
            {processedFiles.map((item) => (
              <div 
                key={item.id} 
                style={{ 
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                  padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', 
                  border: '1px solid #e9ecef', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' 
                }}
              >
                {/* Cột thông tin file */}
                <div style={{ flex: 1, paddingRight: '15px' }}>
                  <div style={{ fontWeight: 'bold', color: '#2b2d42', fontSize: '15px', marginBottom: '4px', wordBreak: 'break-all' }}>
                    📝 {item.downloadName}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6c757d' }}>
                    File gốc: {item.originalName} • Dung lượng gốc: {item.size} • Lúc: {item.timestamp}
                  </div>
                </div>

                {/* Cột nút bấm tải file thủ công kèm hiệu ứng đẹp */}
                <div>
                  <a 
                    href={item.blobUrl} 
                    download={item.downloadName}
                    style={{ 
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '8px 16px', backgroundColor: '#2ec4b6', color: '#fff', 
                      textDecoration: 'none', borderRadius: '4px', fontSize: '14px', 
                      fontWeight: '500', boxShadow: '0 2px 4px rgba(46,196,182,0.2)',
                      transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#259b90')}
                    onMouseOut={(e) => (e.currentTarget.style.backgroundColor = '#2ec4b6')}
                  >
                    📥 Tải xuống (.docx)
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}