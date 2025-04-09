#!/usr/bin/env python
"""
Robot Framework (RPA) ile entegrasyon için belge işleme köprü scripti.

Bu script, RPA sürecinden çağrılarak belgeleri sınıflandırır
ve metin çıkartır. Sonuçları JSON formatında döndürür.

Kullanım:
    python document_classifier.py --file /yol/belge.pdf --mode full
    python document_classifier.py --file /yol/belge.pdf --mode classify --output sonuc.json
    python document_classifier.py --file /yol/belge.pdf --mode full --save_to_mongo
"""
import os
import sys
import json
import argparse
import traceback
import logging
from datetime import datetime
from utils.vector_db import DocumentVectorDB

# Proje dizinini Python modül yoluna ekle
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Belge işleme modüllerini import et
from models.classifier import DocumentClassifier
from models.extractor import UnstructuredTextExtractor
# from models.analyzer import DocumentAnalyzer  # <-- LLM analiz kodu kapalı
from utils.helpers import process_single_document, save_result_to_json, format_result_for_mongodb
from utils.mongodb_client import MongoDBClient
from config.settings import MODEL_PATH


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(script_dir, 'logs', 'document_classifier.log')),
        logging.StreamHandler(sys.stderr)  # <--- Logları stderr'e yönlendir
    ]
)
logger = logging.getLogger('DocumentClassifier')


def process_document(file_path, mode="full", mongo_uri=None,use_vector_db=True):
    """
    Belgeyi işle ve sonuçları döndür
    
    Args:
        file_path (str): İşlenecek belge dosyasının yolu
        mode (str): İşleme modu:
                   "classify" - sadece sınıflandırma
                   "extract"  - sınıflandırma ve metin çıkarma
                   "full"     - (LLM analizi kapalı, ancak metin çıkarma + sınıflandırma)
        mongo_uri (str, optional): MongoDB URI (belirtilirse sonuçlar MongoDB'ye kaydedilir)
        use_vector_db (bool): Vektör veritabanı kullanılacak mı
    
    Returns:
        dict: İşleme sonuçları (JSON serileştirilebilir biçimde)
    """
    try:
        start_time = datetime.now()
        logger.info(f"Belge işleme başlatılıyor: {file_path}, Mod: {mode}")
        
        
        if not os.path.exists(file_path):
            error_msg = f"Dosya bulunamadı: {file_path}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "file_path": file_path
            }
        
        
        classifier = DocumentClassifier(model_path=MODEL_PATH)
        extractor = UnstructuredTextExtractor()
        
        
        vector_db = None
        if use_vector_db:
            try:
                vector_db = DocumentVectorDB()
                logger.info("Vektör veritabanı başlatıldı")
            except Exception as e:
                logger.error(f"Vektör veritabanı başlatma hatası: {e}")
        
        # Belgeyi işle
        result = process_single_document(
            file_path,
            classifier=classifier,
            extractor=extractor,
            analyzer=None,
            vector_db=vector_db,
            skip_analysis=True,
            check_duplicates=use_vector_db
        )
        
        
        if mongo_uri:
            try:
                mongo_doc = format_result_for_mongodb(result)
                mongo_client = MongoDBClient(uri=mongo_uri)
                doc_id = mongo_client.save_document(mongo_doc)
                mongo_client.close()
                
                if doc_id:
                    result['mongodb_id'] = doc_id
                    logger.info(f"Belge MongoDB'ye kaydedildi, ID: {doc_id}")
                else:
                    logger.warning("Belge MongoDB'ye kaydedilemedi")
            except Exception as e:
                logger.error(f"MongoDB kayıt hatası: {e}")
                result['mongodb_error'] = str(e)
        
        # İşleme süresi
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        result['status'] = "success"
        result['processing_summary'] = {
            'mode': mode,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'total_time': processing_time,
            'class': result['classification']['class'],
            'confidence': result['classification']['confidence'],
            'text_length': len(result['extraction']['text']) if 'extraction' in result else 0,
            'has_analysis': False  # LLM analizi kapalı
        }
        
        logger.info(f"Belge işleme tamamlandı: {file_path}, Süre: {processing_time:.2f} sn")
        return result
        
    except Exception as e:
        error_info = traceback.format_exc()
        logger.error(f"Belge işleme hatası: {e}\n{error_info}")
        
        return {
            "status": "error",
            "file_path": file_path,
            "error": str(e),
            "error_details": error_info
        }


def main():
    parser = argparse.ArgumentParser(description="Belge Sınıflandırma ve Metin Çıkarma Scripti")
    parser.add_argument("--file", required=True, help="İşlenecek belge dosyasının yolu")
    parser.add_argument("--mode", choices=["classify", "extract", "full"], default="full",
                        help="İşleme modu: classify, extract veya full")
    parser.add_argument("--output", help="Sonuçları JSON dosyasına yazılacak dosya yolu (stdout yerine)")
    parser.add_argument("--save_to_mongo", help="MongoDB bağlantı URI'si (belirtilirse sonuçlar MongoDB'ye de kaydedilir)")
    parser.add_argument("--use_vector_db", action="store_true", help="Vektör veritabanını kullan")
    parser.add_argument("--verbose", action="store_true", help="Detaylı log çıktısı (stderr'e)")

    args = parser.parse_args()
    
    # Detaylı log modunu ayarla
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Belgeyi işle
    result = process_document(args.file, args.mode, args.save_to_mongo, args.use_vector_db) 
    
    # Sonucu JSON olarak çıktıla
    if args.output:
        # JSON dosyasına kaydet
        save_result_to_json(result, args.output)
        # Not: Bu print de stderr'e gider (log), stdout’ta karışıklık olmaz.
        logger.info(f"Sonuçlar kaydedildi: {args.output}")
    else:
        # stdout'a (tek satırlık JSON) yazdır
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return json.JSONEncoder.default(self, obj)
        
        # Sadece JSON'u stdout'a basarız
        print(json.dumps(result, ensure_ascii=False, cls=DateTimeEncoder))


if __name__ == "__main__":
    # Gerekli dizinleri oluştur
    os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'models_saved'), exist_ok=True)
    
    main()
