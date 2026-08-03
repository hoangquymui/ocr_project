import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { renderAsync } from 'docx-preview';

interface ProcessedFile {
  id: string;
  originalName: string;
  downloadName: string;
  docxBlob: Blob;
  originalBlob: Blob;
  originalFileType: string;
  originalUrl: string;
  timestamp: string;
  size: string;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [stageText, setStageText] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  
  const [processedFiles, setProcessedFiles] = useState<ProcessedFile[]>([]);
  const [activeFile, setActiveFile] = useState<ProcessedFile | null>(null);
  const [viewHeight, setViewHeight] = useState<number>(720);
  
  const viewerRef = useRef<HTMLDivElement>(null);
  const [renderingDocx, setRenderingDocx] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      const ext = droppedFile.name.split('.').pop()?.toLowerCase();
      if (['pdf', 'jpg', 'jpeg', 'png'].includes(ext || '')) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Hệ thống chỉ hỗ trợ tệp định dạng PDF hoặc Ảnh (JPG, PNG).');
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Vui lòng chọn một tệp tài liệu trước khi bắt đầu.');
      return;
    }

    const currentFile = file;
    const formData = new FormData();
    formData.append('file', currentFile);

    setLoading(true);
    setProgress(5);
    setStageText('📄 Đang khởi tạo và chuẩn bị tài liệu...');
    setError(null);

    // Giả lập tiến trình mịn từ 5% đến 95% theo nhịp thời gian chạy OCR AI
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 92) {
          setStageText('🎨 Đang dựng file Word Flow Native & Bảng Ẩn...');
          return 92;
        }
        if (prev >= 65) {
          setStageText('🧠 Đang nhận dạng Tiếng Việt qua VietOCR C++ Engine...');
          return prev + 3;
        }
        if (prev >= 30) {
          setStageText('⚡ Đang định vị ô chữ bằng RapidOCR ONNX Detector...');
          return prev + 5;
        }
        setStageText('📤 Đang tải tệp lên máy chủ OCR Pipeline...');
        return prev + 8;
      });
    }, 400);

    try {
      const response = await axios.post('http://localhost:3000/ocr/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 25) / progressEvent.total);
            setProgress(prev => Math.max(prev, percentCompleted));
          }
        }
      });

      clearInterval(timer);
      setProgress(100);
      setStageText('✅ Xử lý OCR thành công! Đang mở giao diện so sánh...');

      const docxBlob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });

      const baseName = currentFile.name.substring(0, currentFile.name.lastIndexOf('.')) || currentFile.name;
      const downloadFilename = `${baseName}_ocr.docx`;
      const originalUrl = window.URL.createObjectURL(currentFile);

      const newProcessedFile: ProcessedFile = {
        id: Math.random().toString(36).substr(2, 9),
        originalName: currentFile.name,
        downloadName: downloadFilename,
        docxBlob: docxBlob,
        originalBlob: currentFile,
        originalFileType: currentFile.type || (currentFile.name.endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'),
        originalUrl: originalUrl,
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
        size: (currentFile.size / 1024 / 1024).toFixed(2) + ' MB'
      };

      setTimeout(() => {
        setProcessedFiles(prev => [newProcessedFile, ...prev]);
        setActiveFile(newProcessedFile);
        setFile(null);
        setLoading(false);
      }, 500);

    } catch (err: any) {
      clearInterval(timer);
      setLoading(false);
      if (err.response?.data instanceof Blob) {
        const textError = await err.response.data.text();
        try {
          const jsonError = JSON.parse(textError);
          setError(jsonError.message || 'Có lỗi xảy ra trong quá trình xử lý OCR.');
        } catch {
          setError('Có lỗi xảy ra khi gửi dữ liệu đến máy chủ OCR.');
        }
      } else {
        setError(err.response?.data?.message || 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra NestJS Gateway và FastAPI Server.');
      }
    }
  };

  useEffect(() => {
    let isMounted = true;
    if (activeFile && viewerRef.current) {
      viewerRef.current.innerHTML = '';
      setRenderingDocx(true);

      activeFile.docxBlob.arrayBuffer().then((arrayBuffer) => {
        if (!isMounted || !viewerRef.current) return;
        renderAsync(arrayBuffer, viewerRef.current, undefined, {
          className: 'docx-render-page',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          debug: false,
        })
          .then(() => {
            if (isMounted) setRenderingDocx(false);
          })
          .catch((err) => {
            console.error('Lỗi hiển thị tệp Word:', err);
            if (isMounted) setRenderingDocx(false);
          });
      });
    }
    return () => {
      isMounted = false;
    };
  }, [activeFile]);

  const handleDownloadDocx = (item: ProcessedFile) => {
    const url = window.URL.createObjectURL(item.docxBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = item.downloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  return (
    <div style={{ minHeight: '100vh', padding: '24px 32px', maxWidth: '1600px', margin: '0 auto' }}>
      
      {/* 1. HEADER HERO BANNER */}
      <header style={{ textAlign: 'center', marginBottom: '28px' }} className="animate-fade-in">
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#eff6ff', border: '1px solid #bfdbfe', padding: '6px 16px', borderRadius: '30px', color: '#2563eb', fontSize: '13px', fontWeight: '600', marginBottom: '12px' }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }}></span>
          OCR Studio AI Engine v4.0 • Real-time Progress Bar
        </div>
        <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '8px' }}>
          Hệ Thống Trích Xuất & So Sánh Tài Liệu AI
        </h1>
        <p style={{ color: '#64748b', fontSize: '14px', maxWidth: '720px', margin: '0 auto', lineHeight: '1.6' }}>
          So sánh song song <strong>File Gốc (PDF / Ảnh)</strong> ⚡ <strong>Văn Bản Trích Xuất Word (.docx)</strong> trực tiếp trong giao diện Studio 2 khung.
        </p>
      </header>

      {/* 2. UPLOAD ZONE */}
      <section style={{ maxWidth: '800px', margin: '0 auto 32px' }} className="animate-fade-in">
        <div 
          className="glass-panel"
          style={{ 
            padding: '24px', 
            transition: 'all 0.25s ease',
            borderColor: isDragOver ? '#2563eb' : 'rgba(226, 232, 240, 0.9)',
            backgroundColor: isDragOver ? '#eff6ff' : 'rgba(255, 255, 255, 0.98)'
          }}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
        >
          <div style={{ border: '2px dashed #cbd5e1', borderRadius: '12px', padding: '28px 20px', textAlign: 'center', backgroundColor: '#f8fafc', position: 'relative', cursor: 'pointer' }}>
            <input 
              type="file" 
              accept="image/*,application/pdf" 
              onChange={handleFileChange} 
              disabled={loading}
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', opacity: 0, cursor: loading ? 'not-allowed' : 'pointer' }} 
            />
            
            <div style={{ width: '50px', height: '50px', borderRadius: '14px', backgroundColor: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 10px' }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>

            <p style={{ fontWeight: '700', color: '#0f172a', fontSize: '15px', marginBottom: '4px' }}>
              {file ? file.name : 'Kéo thả tài liệu vào đây hoặc nhấp để chọn tệp'}
            </p>
            <p style={{ color: '#94a3b8', fontSize: '13px' }}>
              Hỗ trợ định dạng PDF, JPG, PNG (Tự động gom dòng & phân tích căn lề)
            </p>
          </div>

          {file && !loading && (
            <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '18px' }}>{file.name.endsWith('.pdf') ? '📄' : '🖼️'}</span>
                <div>
                  <p style={{ fontWeight: '700', color: '#1e40af', fontSize: '13px', margin: 0 }}>{file.name}</p>
                  <p style={{ color: '#3b82f6', fontSize: '11px', margin: 0 }}>{(file.size / 1024 / 1024).toFixed(2)} MB • Sẵn sàng xử lý</p>
                </div>
              </div>
              <button 
                onClick={() => setFile(null)} 
                style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}
              >
                Gỡ chọn ✕
              </button>
            </div>
          )}

          {/* 🌟 THANH TIẾN TRÌNH PHẦN TRĂM (PROGRESS BAR) */}
          {loading && (
            <div style={{ marginTop: '18px', padding: '16px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#2563eb', animation: 'pulse 1.5s infinite' }}></span>
                  <span style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>{stageText}</span>
                </div>
                <span style={{ fontSize: '15px', fontWeight: '800', color: '#2563eb' }}>{progress}%</span>
              </div>

              {/* Progress track */}
              <div style={{ width: '100%', height: '10px', backgroundColor: '#e2e8f0', borderRadius: '20px', overflow: 'hidden' }}>
                <div 
                  style={{ 
                    height: '100%', 
                    width: `${progress}%`, 
                    background: 'linear-gradient(90deg, #2563eb 0%, #4f46e5 50%, #10b981 100%)', 
                    borderRadius: '20px', 
                    transition: 'width 0.3s ease-out' 
                  }} 
                />
              </div>
            </div>
          )}

          <button 
            onClick={handleUpload} 
            disabled={loading || !file}
            style={{ 
              marginTop: '16px', 
              width: '100%', 
              padding: '13px 20px', 
              borderRadius: '10px', 
              border: 'none', 
              background: loading || !file ? '#cbd5e1' : 'linear-gradient(135deg, #2563eb 0%, #4f46e5 100%)', 
              color: '#ffffff', 
              fontSize: '15px', 
              fontWeight: '700', 
              cursor: loading || !file ? 'not-allowed' : 'pointer',
              boxShadow: loading || !file ? 'none' : 'var(--shadow-xl)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.2s ease'
            }}
          >
            {loading ? (
              <>
                <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                <span>Đang Tiến Hành OCR ({progress}%)...</span>
              </>
            ) : (
              <>
                <span>🚀 Kích Hoạt OCR & So Sánh 2 Khung</span>
              </>
            )}
          </button>

          {error && (
            <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#991b1b', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>⚠️</span>
              <span><strong>Lỗi:</strong> {error}</span>
            </div>
          )}
        </div>
      </section>

      {/* 3. STUDIO DUAL-PANE COMPARISON DASHBOARD */}
      {activeFile && (
        <section style={{ marginBottom: '40px' }} className="animate-fade-in">
          
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', padding: '12px 20px', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ padding: '4px 10px', borderRadius: '6px', backgroundColor: '#eff6ff', color: '#2563eb', fontWeight: '700', fontSize: '13px' }}>
                🔍 STUDIO DUAL-PANE VIEW
              </span>
              <span style={{ fontSize: '14px', fontWeight: '700', color: '#0f172a' }}>
                {activeFile.originalName}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b' }}>
                <span>Chiều cao khung:</span>
                <button 
                  onClick={() => setViewHeight(720)} 
                  style={{ padding: '3px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', background: viewHeight === 720 ? '#2563eb' : '#ffffff', color: viewHeight === 720 ? '#ffffff' : '#334155', cursor: 'pointer', fontWeight: '600', fontSize: '11px' }}
                >
                  Standard (720px)
                </button>
                <button 
                  onClick={() => setViewHeight(900)} 
                  style={{ padding: '3px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', background: viewHeight === 900 ? '#2563eb' : '#ffffff', color: viewHeight === 900 ? '#ffffff' : '#334155', cursor: 'pointer', fontWeight: '600', fontSize: '11px' }}
                >
                  Expanded (900px)
                </button>
              </div>

              <button 
                onClick={() => handleDownloadDocx(activeFile)}
                style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #10b981', background: '#ecfdf5', color: '#047857', fontSize: '12px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <span>📥 Tải File Word (.docx)</span>
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', width: '100%' }}>
            
            {/* LEFT PANE */}
            <div className="studio-window">
              <div className="studio-window-header">
                <div className="window-dots">
                  <span className="window-dot red"></span>
                  <span className="window-dot yellow"></span>
                  <span className="window-dot green"></span>
                </div>

                <div style={{ fontWeight: '700', fontSize: '13px', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>📄 KHUNG TRÁI: FILE GỐC</span>
                </div>

                <span style={{ fontSize: '11px', fontWeight: '700', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#e2e8f0', color: '#334155' }}>
                  {activeFile.originalFileType.includes('pdf') ? 'PDF DOCUMENT' : 'IMAGE FILE'}
                </span>
              </div>

              <div style={{ height: `${viewHeight}px`, overflowY: 'auto', backgroundColor: '#cbd5e1', padding: '12px', display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
                {activeFile.originalFileType.includes('pdf') ? (
                  <iframe 
                    src={activeFile.originalUrl} 
                    style={{ width: '100%', height: '100%', border: 'none', borderRadius: '6px', backgroundColor: '#ffffff', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} 
                    title="Original Document View" 
                  />
                ) : (
                  <div style={{ width: '100%', display: 'flex', justifyContent: 'center', padding: '10px' }}>
                    <img 
                      src={activeFile.originalUrl} 
                      alt="Original Document" 
                      style={{ maxWidth: '100%', height: 'auto', borderRadius: '6px', boxShadow: '0 8px 24px rgba(0,0,0,0.15)', border: '1px solid #cbd5e1' }} 
                    />
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT PANE */}
            <div className="studio-window">
              <div className="studio-window-header">
                <div className="window-dots">
                  <span className="window-dot red"></span>
                  <span className="window-dot yellow"></span>
                  <span className="window-dot green"></span>
                </div>

                <div style={{ fontWeight: '700', fontSize: '13px', color: '#2563eb', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>✨ KHUNG PHẢI: KẾT QUẢ AI WORD (.DOCX)</span>
                </div>

                {renderingDocx ? (
                  <span style={{ fontSize: '11px', fontWeight: '600', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#fffbeb', color: '#b45309' }}>
                    ⏳ Rendering...
                  </span>
                ) : (
                  <span style={{ fontSize: '11px', fontWeight: '700', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#ecfdf5', color: '#047857' }}>
                    ✓ LIVE RENDERED
                  </span>
                )}
              </div>

              <div 
                ref={viewerRef} 
                style={{ 
                  height: `${viewHeight}px`, 
                  overflowY: 'auto', 
                  backgroundColor: '#eef2f6', 
                  boxSizing: 'border-box'
                }} 
              />
            </div>

          </div>
        </section>
      )}

      {/* 4. HISTORY LIST SECTION */}
      {processedFiles.length > 0 && (
        <section className="animate-fade-in" style={{ maxWidth: '1600px', margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', paddingBottom: '8px', borderBottom: '2px solid #e2e8f0' }}>
            <h3 style={{ fontSize: '17px', fontWeight: '700', color: '#0f172a', margin: 0 }}>
              📊 Lịch Sử Tài Liệu Đã OCR ({processedFiles.length})
            </h3>
            <span style={{ fontSize: '12px', color: '#64748b' }}>Bấm chọn tệp bất kỳ để mở 2 khung so sánh</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '14px' }}>
            {processedFiles.map((item) => {
              const isActive = activeFile?.id === item.id;
              return (
                <div 
                  key={item.id} 
                  className="glass-card"
                  style={{ 
                    padding: '14px 18px', 
                    borderColor: isActive ? '#2563eb' : 'var(--border)',
                    backgroundColor: isActive ? '#eff6ff' : '#ffffff',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '10px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '38px', height: '38px', borderRadius: '10px', backgroundColor: isActive ? '#2563eb' : '#f1f5f9', color: isActive ? '#ffffff' : '#475569', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px', fontWeight: 'bold' }}>
                        {item.originalFileType.includes('pdf') ? '📄' : '🖼️'}
                      </div>
                      <div>
                        <h4 style={{ fontSize: '13px', fontWeight: '700', color: isActive ? '#1e40af' : '#0f172a', margin: 0, wordBreak: 'break-all' }}>
                          {item.downloadName}
                        </h4>
                        <p style={{ fontSize: '11px', color: '#64748b', margin: '2px 0 0 0' }}>
                          File gốc: {item.originalName}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: '8px' }}>
                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                      {item.size} • {item.timestamp}
                    </span>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        onClick={() => handleDownloadDocx(item)}
                        title="Tải tệp Word .docx"
                        style={{ padding: '4px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', color: '#334155', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                      >
                        📥
                      </button>
                      <button 
                        onClick={() => setActiveFile(item)}
                        style={{ 
                          padding: '5px 12px', 
                          borderRadius: '6px', 
                          border: 'none',
                          backgroundColor: isActive ? '#2563eb' : '#f1f5f9', 
                          color: isActive ? '#ffffff' : '#334155', 
                          fontSize: '12px', 
                          fontWeight: '600', 
                          cursor: 'pointer',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        {isActive ? '🔍 Đang Xem' : '🔍 Mở So Sánh'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

    </div>
  );
}