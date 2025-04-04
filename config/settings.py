"""
Belge İşleme Sistemi için yapılandırma ayarları.
"""
import os

# Belge sınıfları
CLASSES = [
    'letter', 'form', 'email', 'handwritten', 'advertisement',
    'scientific_report', 'scientific_publication', 'specification',
    'file_folder', 'news_article', 'budget', 'invoice',
    'presentation', 'questionnaire', 'resume', 'memo'
]

# Model yolu - eğitilmiş modelin yolu
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         'models_saved', 'best_document_classifier.pth')

# Model ayarları
MODEL_CONFIG = {
    'pretrained_model': "microsoft/swin-base-patch4-window7-224-in22k",
    'image_size': 224,
    'num_classes': 16
}

# LLM analiz ayarları
LLM_CONFIG = {
    'model': "deepseek-ai/deepseek-llm-7b-chat",
    'timeout': 120,
    'max_tokens': 800,
    'temperature': 0.1,
    'max_chars': 500
}

# OCR ayarları
OCR_CONFIG = {
    'timeout': 60,
    'tesseract_path': r"C:\Program Files\Tesseract-OCR\tesseract.exe"
}

# MongoDB ayarları
MONGODB_CONFIG = {
    'uri': "mongodb://localhost:27017/",
    'db_name': "document_db",
    'collection_name': "processed_documents"
}

# Geçici dosyalar için dizin
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

# İşlenen belgeler için log dizini
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
