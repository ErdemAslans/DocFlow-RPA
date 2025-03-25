"""
Yardımcı fonksiyonlar ve araçlar.
"""
import os
import json
import datetime
import logging
from config.settings import LOG_DIR

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'document_processor.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DocumentProcessor')

def process_single_document(document_path, classifier, extractor, analyzer=None, skip_analysis=False):
    """
    Tek bir belgeyi işle ve sonuçları döndür
    
    Args:
        document_path (str): İşlenecek belge dosyasının yolu
        classifier: DocumentClassifier nesnesi
        extractor: UnstructuredTextExtractor nesnesi
        analyzer (optional): DocumentAnalyzer nesnesi
        skip_analysis (bool): İçerik analizi atlanacak mı
        
    Returns:
        dict: İşleme sonuçları
    """
    results = {}
    start_time = datetime.datetime.now()
    
    logger.info(f"Belge işleniyor: {document_path}")

    # Adım 1: Görsel sınıflandırma
    logger.info("Adım 1: Görsel sınıflandırma...")
    try:
        classification_result = classifier.predict(document_path)
        results['classification'] = classification_result

        doc_class = classification_result['class']
        confidence = classification_result['confidence']
        logger.info(f"Belge sınıfı: {doc_class} (güven: {confidence:.4f})")
    except Exception as e:
        logger.error(f"Sınıflandırma hatası: {e}")
        results['classification'] = {
            'class': 'error',
            'confidence': 0.0,
            'error': str(e)
        }
        doc_class = 'error'
        confidence = 0.0

    # Adım 2: Metin çıkarma
    logger.info("Adım 2: Metin çıkarma...")
    try:
        extraction_result = extractor.extract_text(document_path)
        results['extraction'] = {
            'text': extraction_result['text'],
            'metadata': extraction_result['metadata']
        }

        text_length = len(extraction_result['text'])
        logger.info(f"Çıkarılan metin uzunluğu: {text_length} karakter")

    except Exception as e:
        logger.error(f"Metin çıkarma hatası: {e}")
        results['extraction'] = {
            'text': "[Metin çıkarma başarısız oldu]",
            'metadata': {'error': str(e)}
        }
        text_length = 0

    # Adım 3: İçerik analizi (opsiyonel)
    if analyzer and not skip_analysis and confidence > 0.5 and text_length > 50:
        logger.info("Adım 3: İçerik analizi...")
        try:
            analysis_result = analyzer.analyze_document(
                results['extraction']['text'],
                doc_class
            )
            results['analysis'] = analysis_result
            logger.info("İçerik analizi tamamlandı.")
        except Exception as e:
            logger.error(f"İçerik analizi hatası: {e}")
            results['analysis'] = {
                'analysis': "[Analiz hatası oluştu]",
                'error': str(e)
            }
    else:
        if skip_analysis:
            logger.info("İçerik analizi atlandı (kullanıcı tercihiyle).")
        else:
            logger.info("İçerik analizi atlandı (düşük güven veya yetersiz metin veya analizör yok).")
        results['analysis'] = None

    # İşleme süresini ekle
    end_time = datetime.datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    results['processing_info'] = {
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'processing_time': processing_time,
        'file_path': document_path,
        'file_name': os.path.basename(document_path)
    }
    
    logger.info(f"Belge işleme tamamlandı. Süre: {processing_time:.2f} saniye.")

    return results

def save_result_to_json(result, output_path=None):
    """
    İşleme sonucunu JSON dosyasına kaydet
    
    Args:
        result (dict): İşleme sonucu
        output_path (str, optional): Çıktı dosyasının yolu. Belirtilmezse otomatik oluşturulur.
        
    Returns:
        str: Kaydedilen dosyanın yolu
    """
    if output_path is None:
        # Sonuç dizini oluştur
        results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
        os.makedirs(results_dir, exist_ok=True)
        
        # Dosya adını belirle
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"doc_result_{timestamp}.json"
        output_path = os.path.join(results_dir, file_name)
    
    # JSON serileştirme işlemi
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
    
    logger.info(f"Sonuç kaydedildi: {output_path}")
    return output_path

def format_result_for_mongodb(result):
    """
    İşleme sonucunu MongoDB formatına dönüştür
    
    Args:
        result (dict): İşleme sonucu
        
    Returns:
        dict: MongoDB için formatlanmış veri
    """
    document = {
        'file_path': result['processing_info']['file_path'],
        'file_name': result['processing_info']['file_name'],
        'processing_time': result['processing_info']['processing_time'],
        'processed_date': datetime.datetime.fromisoformat(result['processing_info']['end_time']),
        'document_class': result['classification']['class'],
        'confidence': result['classification']['confidence'],
        'extracted_text': result['extraction']['text'],
        'text_length': len(result['extraction']['text']),
        'metadata': {
            'ocr_metadata': result['extraction']['metadata'],
            'classification_details': {
                'all_probs': result['classification']['all_probs'],
                'sorted_probs': result['classification']['sorted_probs']
            }
        }
    }
    
    # Eğer analiz yapıldıysa ekle
    if result['analysis']:
        document["analysis"] = result['analysis']['analysis']
        document["analysis_metadata"] = {
            "model": result['analysis'].get('model', "unknown"),
            "processing_time": result['analysis'].get('processing_time', 0)
        }
    
    return document
