"""
Belge metin çıkarma modülleri.
"""
import os
import time
import threading
from queue import Queue
from PIL import Image
import numpy as np

# Önce Tesseract yapılandırması
import pytesseract
# Tesseract yolunu direkt olarak belirleyin
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = tesseract_path

from config.settings import OCR_CONFIG, TEMP_DIR

class UnstructuredTextExtractor:
    def __init__(self, timeout=None):
        """
        Belgelerden metin çıkarmak için sınıf.
        
        Args:
            timeout (int, optional): Metin çıkarma işlemi için maksimum süre (saniye). 
                                     Varsayılan OCR_CONFIG['timeout'].
        """
        print("Metin çıkarıcı başlatılıyor...")
        self.timeout = timeout or OCR_CONFIG['timeout']
        # Tesseract yolunu kontrol et
        if os.path.exists(tesseract_path):
            print(f"Tesseract OCR bulundu: {tesseract_path}")
        else:
            print(f"UYARI: Tesseract OCR bulunamadı: {tesseract_path}")

    def extract_text(self, document_path):
        """
        Belge dosyasından metin çıkarma işlemi.
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
                print(f"Metin çıkarma başlıyor: {document_path}")

                # Belgenin uzantısını kontrol et
                ext = os.path.splitext(document_path)[1].lower()

                # TIF dosyalarına özel işlem
                if ext in ['.tif', '.tiff']:
                    try:
                        # TIF dosyasını PIL ile açıp geçici bir JPEG olarak kaydet
                        print(f"TIF dosyası işleniyor: {document_path}")
                        img = Image.open(document_path)

                        # Geçici jpeg dosyası oluştur
                        temp_jpg = os.path.join(TEMP_DIR, os.path.basename(document_path) + "_temp.jpg")
                        img = img.convert('RGB')
                        img.save(temp_jpg)
                        print(f"Geçici JPEG oluşturuldu: {temp_jpg}")

                        # Pytesseract ile doğrudan OCR uygula
                        try:
                            text = pytesseract.image_to_string(img)
                            print(f"Pytesseract ile OCR yapıldı. Metin uzunluğu: {len(text)} karakter")
                            
                            # Geçici dosyayı temizle
                            try:
                                os.remove(temp_jpg)
                            except:
                                pass
                        except Exception as e:
                            print(f"Pytesseract OCR hatası: {e}")
                            # Unstructured ile dene
                            try:
                                from unstructured.partition.auto import partition
                                from unstructured.staging.base import elements_to_text

                                print("Unstructured ile ayrıştırma başlıyor...")
                                elements = partition(temp_jpg)
                                text = elements_to_text(elements)
                                print(f"Unstructured ile OCR yapıldı. Metin uzunluğu: {len(text)} karakter")

                                # Geçici dosyayı temizle
                                try:
                                    os.remove(temp_jpg)
                                except:
                                    pass
                            except ImportError:
                                print("Unstructured paketi kurulu değil, OCR atlanıyor")
                                text = "[OCR paketi bulunamadı]"
                                elements = []
                            except Exception as e:
                                print(f"Unstructured OCR hatası: {e}")
                                text = f"[OCR hatası: {str(e)}]"
                                elements = []
                            
                    except Exception as e:
                        print(f"TIF işleme hatası: {e}")
                        text = f"[TIF işleme hatası: {str(e)}]"
                        elements = []
                else:
                    # Diğer dosya türleri için doğrudan işle
                    try:
                        # Önce pytesseract ile dene
                        try:
                            img = Image.open(document_path).convert('RGB')
                            text = pytesseract.image_to_string(img)
                            print(f"Pytesseract ile OCR yapıldı. Metin uzunluğu: {len(text)} karakter")
                        except Exception as e:
                            print(f"Pytesseract OCR hatası: {e}")
                            # Unstructured ile dene
                            try:
                                from unstructured.partition.auto import partition
                                from unstructured.staging.base import elements_to_text

                                print("Unstructured ile ayrıştırma başlıyor...")
                                elements = partition(document_path)
                                text = elements_to_text(elements)
                                print(f"Unstructured ile OCR yapıldı. Metin uzunluğu: {len(text)} karakter")
                            except ImportError:
                                print("Unstructured paketi kurulu değil, OCR atlanıyor")
                                text = "[OCR paketi bulunamadı]"
                                elements = []
                            except Exception as e:
                                print(f"Unstructured OCR hatası: {e}")
                                text = f"[OCR hatası: {str(e)}]"
                                elements = []
                    except Exception as e:
                        print(f"Dosya işleme hatası: {e}")
                        text = f"[Dosya işleme hatası: {str(e)}]"
                        elements = []

                # İşlem süresini kontrol et
                elapsed_time = time.time() - start_time
                print(f"Metin çıkarma tamamlandı: {len(text)} karakter, {elapsed_time:.2f} saniye")

                # Sonuçları kuyruğa ekle
                result_queue.put({
                    'text': text,
                    'metadata': {
                        'num_elements': 0,  # Şu an için önemli değil
                        'processing_time': elapsed_time,
                        'file_path': document_path
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