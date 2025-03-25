# mongodb_keywords.py
from pymongo import MongoClient

class MongoDBKeywords:
    
    def __init__(self):
        self.client = None
        self.db = None
    
    def connect_to_mongodb(self, uri):
        """MongoDB'ye bağlanır"""
        self.client = MongoClient(uri)
        return self.client
    
    def use_database(self, db_name):
        """Veritabanı seçer"""
        if not self.client:
            raise Exception("Önce MongoDB'ye bağlanmalısınız")
        self.db = self.client[db_name]
        return self.db
    
    def insert_one(self, collection_name, document):
        """Belge ekler"""
        if not self.db:
            raise Exception("Önce veritabanı seçmelisiniz")
        result = self.db[collection_name].insert_one(document)
        return str(result.inserted_id)
    
    def count_documents(self, collection_name, query):
        """Belge sayısını sayar"""
        if not self.db:
            raise Exception("Önce veritabanı seçmelisiniz")
        return self.db[collection_name].count_documents(query)