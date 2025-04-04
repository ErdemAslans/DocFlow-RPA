#!/usr/bin/env python
"""
Belge yönlendirme sistemi.

MongoDB'den işlenen belgeleri alıp, sınıflarına göre uygun klasörlere taşır.
RPA sürecinden çağrılır.

Kullanım:
    python document_router.py
"""
import os
import sys
import logging
import shutil
from datetime import datetime
from pymongo import MongoClient

# Logları yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/document_router.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DocumentRouter')

# MongoDB bağlantı bilgileri
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "document_db"
COLLECTION_NAME = "processed_documents"

# Klasör yolu
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# Tüm belge sınıfları
DOCUMENT_CLASSES = [
    'letter', 'form', 'email', 'handwritten', 'advertisement',
    'scientific_report', 'scientific_publication', 'specification',
    'file_folder', 'news_article', 'budget', 'invoice',
    'presentation', 'questionnaire', 'resume', 'memo',
    'review', 'ocr_failed'
]

def create_directories():
    """Gerekli tüm klasörleri oluştur"""
    for doc_class in DOCUMENT_CLASSES:
        class_dir = os.path.join(BASE_PATH, doc_class)
        os.makedirs(class_dir, exist_ok=True)
        logger.info(f"Klasör kontrol edildi: {class_dir}")

def route_documents():
    """Belgeleri sınıflarına göre uygun klasörlere yönlendir"""
    try:
        
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        logger.info(f"MongoDB bağlantısı kuruldu: {MONGO_URI}, DB: {DB_NAME}, Collection: {COLLECTION_NAME}")
        
        
        total_docs = collection.count_documents({})
        logger.info(f"MongoDB'de toplam {total_docs} belge var")
        
        # İşlenmemiş belgeleri bul - genişletilmiş sorgu
        query = {
            "$or": [
                {"processed_for_routing": {"$ne": True}},
                {"processed_for_routing": {"$exists": False}}
            ]
        }
        matching_docs = collection.count_documents(query)
        logger.info(f"İşlenmemiş {matching_docs} belge bulundu")
        
        # Belgeleri getir
        cursor = collection.find(query)
        
        count = 0
        
        # Her belge için kuralları uygula
        for doc in cursor:
            count += 1
            
            # Belge ID'sini log'la
            doc_id = str(doc.get("_id", "Bilinmeyen ID"))
            logger.info(f"Belge işleniyor: {doc_id}")
            
            
            logger.info(f"Belge alanları: {list(doc.keys())}")
            
            
            file_path = doc.get("file_path") or doc.get("filepath") or doc.get("path")
            file_name = doc.get("file_name") or doc.get("filename") or os.path.basename(str(file_path)) if file_path else "bilinmeyen.dosya"
            document_class = doc.get("document_class") or doc.get("class") or "review"
            confidence = float(doc.get("confidence", 0.0))
            text_length = int(doc.get("text_length", 0))
            
            logger.info(f"Belge bilgileri: file_path={file_path}, file_name={file_name}, class={document_class}")
            
            # Hedef klasörü belirle
            target_folder = document_class
            needs_review = False
            ocr_failed = False
            
            # Kural 1: Düşük güven skoru -> inceleme klasörü
            if confidence < 0.75:
                target_folder = "review"
                needs_review = True
                logger.info(f"Düşük güven skoru tespit edildi: {confidence}")
            
            # Kural 2: Kısa/eksik metin -> OCR hatası klasörü
            if text_length < 50:
                target_folder = "ocr_failed"
                ocr_failed = True
                logger.info(f"Az/eksik metin tespit edildi: {text_length} karakter")
            
            # Dosyayı hedef klasöre taşı
            if file_path and isinstance(file_path, str):
                if os.path.exists(file_path):
                    target_dir = os.path.join(BASE_PATH, target_folder)
                    target_path = os.path.join(target_dir, file_name)
                    
                    try:
                        shutil.copy2(file_path, target_path)
                        logger.info(f"Dosya kopyalandı: {file_name} -> {target_folder}")
                        
                        # MongoDB'de işlendiği işaretle
                        collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {
                                "processed_for_routing": True,
                                "target_folder": target_folder,
                                "needs_review": needs_review,
                                "ocr_failed": ocr_failed,
                                "routing_time": datetime.now()
                            }}
                        )
                        logger.info(f"Belge MongoDB'de güncellendi: {doc_id}")
                    except Exception as e:
                        logger.error(f"Dosya kopyalama hatası: {e}")
                else:
                    logger.warning(f"Dosya bulunamadı: {file_path}")
                    # Belge işlenmiş olarak işaretle ama hata durumunu belirt
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {
                            "processed_for_routing": True,
                            "routing_error": f"Dosya bulunamadı: {file_path}",
                            "routing_time": datetime.now()
                        }}
                    )
            else:
                error_msg = "Dosya yolu bilgisi bulunamadı veya geçersiz"
                logger.warning(f"{error_msg}: {file_path}")
                # Belge işlenmiş olarak işaretle ama hata durumunu belirt
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "processed_for_routing": True,
                        "routing_error": error_msg,
                        "routing_time": datetime.now()
                    }}
                )
        
        logger.info(f"Toplam {count} belge işlendi")
        
        if count == 0:
            logger.info("İşlenecek yeni belge bulunamadı")
        
        # MongoDB bağlantısını kapat
        client.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Yönlendirme hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

if __name__ == "__main__":
    print("Belge yönlendirme sistemi başlatılıyor...")
    
    # logs klasörünü kontrol et
    os.makedirs("logs", exist_ok=True)
    
    # Klasörleri kontrol et
    create_directories()
    
    # Belgeleri yönlendir
    num_routed = route_documents()
    
    print(f"Yönlendirme tamamlandı: {num_routed} belge işlendi.")