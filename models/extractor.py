"""
Belge metin çıkarma modülleri - EasyOCR Entegrasyonu.
"""
import os
import time
import threading
from queue import Queue
from PIL import Image
import numpy as np
import easyocr  # Yeni eklenen import

from config.settings import OCR_CONFIG, TEMP_DIR

class UnstructuredTextExtractor:
    def __init__(self, timeout=None):
        """
        Belgelerden metin çıkarmak için EasyOCR tabanlı sınıf.
        
        Args:
            timeout (int, optional): Metin çıkarma işlemi için maksimum süre (saniye). 
                                     Varsayılan OCR_CONFIG['timeout'].
        """
        print("EasyOCR tabanlı metin çıkarıcı başlatılıyor...")
        self.timeout = timeout or OCR_CONFIG['timeout']
        
        # EasyOCR okuyucusu oluştur - dil listesini ayarlamalar dosyasından al
        self.languages = OCR_CONFIG.get('languages', ['tr', 'en'])
        print(f"EasyOCR dilleri: {self.languages}")
        
        try:
            # EasyOCR reader'ı GPU kullanılabilirse GPU ile başlat
            self.reader = easyocr.Reader(
                self.languages, 
                gpu=OCR_CONFIG.get('use_gpu', True)
            )
            print(f"EasyOCR başarıyla başlatıldı: {self.languages} dilleri için.")
        except Exception as e:
            print(f"UYARI: EasyOCR başlatılamadı: {e}")
            self.reader = None

    def extract_text(self, document_path):
        """
        Belge dosyasından metin çıkarma işlemi - EasyOCR ile.
        Güvenlik için zaman aşımı ve hata yönetimi eklenmiştir.
        
        Args:
            document_path (str): İşlenecek belge dosyasının yolu
            
        Returns:
            dict: {'text': çıkarılan metin, 'metadata': meta bilgiler}
        """
        result_queue = Queue()
        exception_queue = Queue()

        def extraction_worker():
            try:
                # Hata ayıklama için başlangıç zamanı
                start_time = time.time()
                print(f"EasyOCR ile metin çıkarma başlıyor: {document_path}")

                # Belgenin uzantısını kontrol et
                ext = os.path.splitext(document_path)[1].lower()
                
                # EasyOCR reader kontrol
                if self.reader is None:
                    print("EasyOCR başlatılmamış, metin çıkarma atlanıyor")
                    result_queue.put({
                        'text': "[EasyOCR başlatılmamış]",
                        'metadata': {
                            'error': "reader_not_initialized",
                            'file_path': document_path
                        }
                    })
                    return

                # PDF veya TIF dosyalarını işle
                if ext in ['.pdf', '.tif', '.tiff']:
                    try:
                        # Görüntüyü PIL ile aç (PDF ise ilk sayfası alınır)
                        print(f"{ext.upper()} dosyası işleniyor: {document_path}")
                        
                        # PDF dosyası için
                        if ext == '.pdf':
                            import pdf2image
                            pages = pdf2image.convert_from_path(document_path, dpi=300)
                            
                            all_text = []
                            for i, img in enumerate(pages):
                                print(f"PDF sayfa {i+1}/{len(pages)} işleniyor...")
                                # EasyOCR ile OCR uygula
                                results = self.reader.readtext(np.array(img))
                                page_text = ' '.join([text for _, text, _ in results])
                                all_text.append(page_text)
                            
                            # Tüm sayfaları birleştir
                            text = '\n\n'.join(all_text)
                            print(f"PDF OCR tamamlandı. Metin uzunluğu: {len(text)} karakter")
                            
                        # TIF/TIFF dosyası için
                        else:
                            img = Image.open(document_path)
                            img_array = np.array(img)
                            
                            # Çok sayfalı TIF için
                            if hasattr(img, 'n_frames') and img.n_frames > 1:
                                all_text = []
                                for i in range(img.n_frames):
                                    print(f"TIF sayfa {i+1}/{img.n_frames} işleniyor...")
                                    img.seek(i)
                                    img_array = np.array(img)
                                    results = self.reader.readtext(img_array)
                                    page_text = ' '.join([text for _, text, _ in results])
                                    all_text.append(page_text)
                                
                                text = '\n\n'.join(all_text)
                            else:
                                # Tek sayfalı TIF
                                results = self.reader.readtext(img_array)
                                text = ' '.join([text for _, text, _ in results])
                            
                            print(f"TIF OCR tamamlandı. Metin uzunluğu: {len(text)} karakter")
                    
                    except Exception as e:
                        print(f"{ext.upper()} işleme hatası: {e}")
                        text = f"[OCR hatası: {str(e)}]"
                
                # Diğer görüntü formatları için doğrudan işle
                elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    try:
                        img = Image.open(document_path)
                        img_array = np.array(img)
                        
                        results = self.reader.readtext(img_array)
                        text = ' '.join([text for _, text, _ in results])
                        print(f"Görüntü OCR tamamlandı. Metin uzunluğu: {len(text)} karakter")
                    
                    except Exception as e:
                        print(f"Görüntü işleme hatası: {e}")
                        text = f"[Görüntü işleme hatası: {str(e)}]"
                
                # Desteklenmeyen dosya formatları
                else:
                    print(f"Desteklenmeyen dosya formatı: {ext}")
                    text = f"[Desteklenmeyen dosya formatı: {ext}]"

                # İşlem süresini kontrol et
                elapsed_time = time.time() - start_time
                print(f"Metin çıkarma tamamlandı: {len(text)} karakter, {elapsed_time:.2f} saniye")

                # Sonuçları kuyruğa ekle
                result_queue.put({
                    'text': text,
                    'metadata': {
                        'num_characters': len(text),
                        'processing_time': elapsed_time,
                        'file_path': document_path,
                        'ocr_engine': 'EasyOCR'
                    }
                })

            except Exception as e:
                print(f"Metin çıkarma thread hatası: {e}")
                import traceback
                print(traceback.format_exc())
                exception_queue.put(e)

        # İş parçacığını başlat
        thread = threading.Thread(target=extraction_worker)
        thread.daemon = True
        thread.start()

        # Zaman aşımı ile bekle
        thread.join(timeout=self.timeout)

        # Thread hala çalışıyorsa zaman aşımına uğradı
        if thread.is_alive():
            print(f"Metin çıkarma zaman aşımına uğradı ({self.timeout} saniye)")
            return {
                'text': f"[Metin çıkarma zaman aşımına uğradı ({self.timeout} saniye)]",
                'metadata': {'error': 'timeout', 'file_path': document_path}
            }

        # İstisna olup olmadığını kontrol et
        if not exception_queue.empty():
            e = exception_queue.get()
            return {
                'text': f"[Metin çıkarma hatası: {str(e)}]",
                'metadata': {'error': str(e), 'file_path': document_path}
            }

        # Sonuçları döndür
        if not result_queue.empty():
            return result_queue.get()
        else:
            return {
                'text': "[Metin çıkarma işlemi tamamlandı ancak sonuç bulunamadı]",
                'metadata': {'error': 'no_result', 'file_path': document_path}
            }