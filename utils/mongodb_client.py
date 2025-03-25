"""
MongoDB yardımcı fonksiyonları ve bağlantı yönetimi.
"""
import logging
from datetime import datetime
from config.settings import MONGODB_CONFIG

logger = logging.getLogger('DocumentProcessor.MongoDB')

class MongoDBClient:
    def __init__(self, uri=None, db_name=None, collection_name=None):
        """
        MongoDB istemcisi başlat
        
        Args:
            uri (str): MongoDB bağlantı URI'si
            db_name (str): Veritabanı adı
            collection_name (str): Koleksiyon adı
        """
        self.uri = uri or MONGODB_CONFIG['uri']
        self.db_name = db_name or MONGODB_CONFIG['db_name']
        self.collection_name = collection_name or MONGODB_CONFIG['collection_name']
        self.client = None
        self.db = None
        self.collection = None
        
    def connect(self):
        """MongoDB bağlantısını başlat"""
        try:
            from pymongo import MongoClient
            self.client = MongoClient(self.uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"MongoDB bağlantısı kuruldu: {self.uri}, DB: {self.db_name}, Collection: {self.collection_name}")
            return True
        except ImportError:
            logger.error("PyMongo paketi kurulu değil. 'pip install pymongo' komutu ile kurulabilir.")
            return False
        except Exception as e:
            logger.error(f"MongoDB bağlantı hatası: {e}")
            return False
    
    def close(self):
        """MongoDB bağlantısını kapat"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.collection = None
            logger.info("MongoDB bağlantısı kapatıldı")
    
    def save_document(self, document_data):
        """
        Belge verilerini MongoDB'ye kaydet
        
        Args:
            document_data (dict): Belge verileri
            
        Returns:
            str: Eklenen belgenin ID'si veya None
        """
        if not self.collection:
            if not self.connect():
                return None
                
        try:
            result = self.collection.insert_one(document_data)
            document_id = str(result.inserted_id)
            logger.info(f"Belge MongoDB'ye kaydedildi: {document_id}")
            return document_id
        except Exception as e:
            logger.error(f"MongoDB kaydetme hatası: {e}")
            return None
    
    def get_document(self, document_id):
        """
        ID'ye göre belge getir
        
        Args:
            document_id (str): Belge ID'si
            
        Returns:
            dict: Belge verileri veya None
        """
        if not self.collection:
            if not self.connect():
                return None
                
        try:
            from bson import ObjectId
            result = self.collection.find_one({"_id": ObjectId(document_id)})
            if result:
                # ObjectId'yi string'e dönüştür
                result["_id"] = str(result["_id"])
                return result
            return None
        except Exception as e:
            logger.error(f"MongoDB belge getirme hatası: {e}")
            return None
    
    def get_documents_by_class(self, document_class, limit=100):
        """
        Sınıfa göre belgeleri getir
        
        Args:
            document_class (str): Belge sınıfı
            limit (int): Maksimum belge sayısı
            
        Returns:
            list: Belge listesi
        """
        if not self.collection:
            if not self.connect():
                return []
                
        try:
            cursor = self.collection.find({"document_class": document_class}).limit(limit)
            documents = list(cursor)
            
            # ObjectId'leri string'e dönüştür
            for doc in documents:
                doc["_id"] = str(doc["_id"])
                
            return documents
        except Exception as e:
            logger.error(f"MongoDB belge sorgulama hatası: {e}")
            return []
    
    def get_class_statistics(self):
        """
        Sınıf bazında istatistikleri getir
        
        Returns:
            dict: Sınıf istatistikleri
        """
        if not self.collection:
            if not self.connect():
                return {}
                
        try:
            pipeline = [
                {"$group": {
                    "_id": "$document_class",
                    "count": {"$sum": 1},
                    "avg_confidence": {"$avg": "$confidence"},
                    "avg_text_length": {"$avg": "$text_length"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            results = list(self.collection.aggregate(pipeline))
            
            # İstatistikleri daha okunabilir formata dönüştür
            statistics = {}
            for item in results:
                class_name = item["_id"]
                statistics[class_name] = {
                    "count": item["count"],
                    "avg_confidence": round(item["avg_confidence"], 4),
                    "avg_text_length": round(item["avg_text_length"], 2)
                }
                
            return statistics
        except Exception as e:
            logger.error(f"MongoDB istatistik hatası: {e}")
            return {}
    
    def get_recent_documents(self, limit=10):
        """
        Son işlenen belgeleri getir
        
        Args:
            limit (int): Maksimum belge sayısı
            
        Returns:
            list: Belge listesi
        """
        if not self.collection:
            if not self.connect():
                return []
                
        try:
            cursor = self.collection.find({}, {
                "file_name": 1,
                "document_class": 1,
                "confidence": 1,
                "processed_date": 1,
                "text_length": 1
            }).sort("processed_date", -1).limit(limit)
            
            documents = list(cursor)
            
            # ObjectId'leri string'e dönüştür
            for doc in documents:
                doc["_id"] = str(doc["_id"])
                
            return documents
        except Exception as e:
            logger.error(f"MongoDB sorgu hatası: {e}")
            return []
