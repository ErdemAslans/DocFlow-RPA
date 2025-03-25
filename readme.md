# Belge İşleme Sistemi - RPA Entegrasyonu

Bu sistem, belgeleri görüntü tabanlı sınıflandırma, metin çıkarma (OCR) ve içerik analizi (LLM) yetenekleriyle işler. RPA (Robot Process Automation) sistemleriyle entegrasyon için optimize edilmiştir.

## Özellikler

- 🔍 **Belge Sınıflandırma**: 16 farklı belge türü tanıma (mektup, fatura, form, e-posta vb.)
- 📝 **Metin Çıkarma (OCR)**: TIF, PDF, JPG, PNG formatındaki belgelerden metin çıkarma
- 🤖 **İçerik Analizi**: DeepSeek LLM ile belge içeriğinden önemli bilgileri çıkarma
- 💾 **MongoDB Entegrasyonu**: İşlenen belgeleri MongoDB'ye kaydetme
- 🔄 **RPA Entegrasyonu**: Robot Framework ile kolay entegrasyon

## Kurulum

### Gereksinimler

```bash
pip install -r requirements.txt
```

### Model Dosyası

Eğitilmiş model dosyasını `models_saved` klasörüne yerleştirin:

```
models_saved/best_document_classifier.pth
```

## Kullanım

### Komut Satırından Kullanım

```bash
# Tam analiz (sınıflandırma, OCR ve içerik analizi)
python document_classifier.py --file /yol/belge.pdf --mode full

# Sadece sınıflandırma
python document_classifier.py --file /yol/belge.pdf --mode classify

# Sonucu JSON dosyasına kaydetme
python document_classifier.py --file /yol/belge.pdf --output sonuc.json

# MongoDB'ye kaydetme
python document_classifier.py --file /yol/belge.pdf --save_to_mongo mongodb://localhost:27017/

# Detaylı log için
python document_classifier.py --file /yol/belge.pdf --verbose
```

### RPA ile Entegrasyon

Robot Framework ile entegrasyon örneği:

```robot
*** Settings ***
Library    Process
Library    OperatingSystem
Library    Collections
Library    JSON

*** Tasks ***
Belge İşle
    ${result}=    Run Process    python    ${CURDIR}/document_classifier.py    --file    ${BELGE_YOLU}    --mode    full
    ${json_result}=    Evaluate    json.loads('''${result.stdout}''')    json
    Log    Belge sınıfı: ${json_result["classification"]["class"]}
    
    # MongoDB'ye kaydet
    Run Process    python    ${CURDIR}/document_classifier.py    --file    ${BELGE_YOLU}    --save_to_mongo    ${MONGO_URI}
```

## RPA Arayüzü

`document_classifier.py` scripti, RPA sistemleriyle entegrasyon için aşağıdaki parametreleri alır:

- `--file`: İşlenecek belge dosyasının yolu (zorunlu)
- `--mode`: İşleme modu (classify, extract, full)
- `--output`: Sonuçların kaydedileceği JSON dosyasının yolu
- `--save_to_mongo`: MongoDB bağlantı URI'si
- `--verbose`: Detaylı log çıktısı için

## Klasör Yapısı

```
document_processing/
│
├── config/               # Yapılandırma ayarları
├── models/               # Model sınıfları
├── utils/                # Yardımcı fonksiyonlar ve MongoDB işlemleri
├── logs/                 # Log dosyaları
├── models_saved/         # Eğitilmiş model dosyaları
├── temp/                 # Geçici dosyalar
│
├── document_classifier.py   # RPA entegrasyonu için ana script
└── requirements.txt         # Gerekli kütüphaneler
```

## Notlar

- LLM analizi için tercihen GPU gereklidir, ancak CPU üzerinde de çalışabilir.
- OCR işlemi için `unstructured` kütüphanesi gereklidir.
- MongoDB'ye kaydetmek için `pymongo` kütüphanesi gereklidir.
