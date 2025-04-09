"""
Belge vektör veritabanı işlemleri için yardımcı modül.
Belgelerin metin içeriklerini vektör olarak saklar ve benzerlik aramaları yapar.
"""
import logging
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import numpy as np
from sentence_transformers import SentenceTransformer
import hashlib
from datetime import datetime
from config.settings import VECTORDB_CONFIG

logger = logging.getLogger('DocumentProcessor.VectorDB')

class DocumentVectorDB:
    def __init__(self, collection_name=None, connect_uri=None):
        """
        Belge vektör veritabanını başlatır
        
        Args:
            collection_name (str, optional): Koleksiyon adı
            connect_uri (str, optional): Milvus bağlantı URI'si
        """
        self.collection_name = collection_name or VECTORDB_CONFIG['collection_name']
        self.connect_uri = connect_uri or VECTORDB_CONFIG['uri']
        self.model_name = VECTORDB_CONFIG['model_name']
        
        # Embedding modeli yükle
        self.model = SentenceTransformer(self.model_name)
        self.vector_dim = self.model.get_sentence_embedding_dimension()
        
        logger.info(f"Vektör modeli yüklendi: {self.model_name}, boyut: {self.vector_dim}")
        
        # Milvus'a bağlan
        try:
            connections.connect("default", host=self.connect_uri.split(':')[0], 
                               port=self.connect_uri.split(':')[1] if ':' in self.connect_uri else "19530")
            logger.info(f"Milvus bağlantısı kuruldu: {self.connect_uri}")
            
            # Koleksiyon var mı kontrol et, yoksa oluştur
            self._init_collection()
        except Exception as e:
            logger.error(f"Milvus bağlantı hatası: {e}")
            raise
        
    def _init_collection(self):
        """Milvus koleksiyonunu oluşturur veya mevcut koleksiyona bağlanır"""
        if utility.has_collection(self.collection_name):
            logger.info(f"Var olan koleksiyona bağlanılıyor: {self.collection_name}")
            self.collection = Collection(name=self.collection_name)
        else:
            logger.info(f"Yeni koleksiyon oluşturuluyor: {self.collection_name}")
            # Şema tanımlama
            fields = [
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="class", dtype=DataType.VARCHAR, max_length=32),  # Belge sınıfı
                FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="processed_date", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="text_hash", dtype=DataType.VARCHAR, max_length=64),  # Metin MD5 hash
                FieldSchema(name="content_preview", dtype=DataType.VARCHAR, max_length=2000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim)
            ]
            schema = CollectionSchema(fields)
            self.collection = Collection(name=self.collection_name, schema=schema)
            
            # İndeks oluştur
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": VECTORDB_CONFIG['nlist']}
            }
            self.collection.create_index("embedding", index_params)
            logger.info(f"Koleksiyon ve indeks oluşturuldu: {self.collection_name}")
            
    def add_document(self, doc_id, doc_class, file_path, text_content, processed_date=None):
        """
        Belgeyi Milvus'a ekler
        
        Args:
            doc_id (str): Belge ID'si
            doc_class (str): Belge sınıfı
            file_path (str): Dosya yolu
            text_content (str): Metin içeriği
            processed_date (str, optional): İşleme tarihi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info(f"Vektör ekleme başlıyor: doc_id={doc_id}, class={doc_class}")
            
            # Boş içerik kontrolü
            if not text_content or len(text_content.strip()) < 20:
                logger.warning(f"Belge içeriği çok kısa veya boş, vektör oluşturulamadı: {doc_id}")
                return False
                
            # Metin hash'i hesapla (duplikasyon kontrolü için)
            text_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()
            logger.debug(f"Metin hash değeri: {text_hash[:8]}...")
                
            # Metin içeriğini vektöre dönüştür
            preview = text_content[:1500] if text_content else ""
            logger.debug(f"Metin vektörize ediliyor ({len(text_content)} karakter)")
            embedding = self.model.encode(text_content).tolist()
            logger.debug(f"Vektörize edildi: {len(embedding)} boyutlu vektör")
            
            # Tarih kontrolü
            if not processed_date:
                processed_date = datetime.now().isoformat()
                
            # Veri eklemeden önce koleksiyonu yükle (bazı Milvus sürümleri için gerekli olabilir)
            try:
                self.collection.load()
                logger.debug("Koleksiyon RAM'e yüklendi")
            except Exception as e:
                logger.debug(f"Koleksiyon yükleme atlandı: {e}")
                
            # Veriyi ekle
            entities = [
                [doc_id],
                [doc_class],
                [file_path],
                [processed_date],
                [text_hash],
                [preview],
                [embedding]
            ]
            
            logger.debug(f"Milvus insert çağrılıyor...")
            insert_result = self.collection.insert(entities)
            logger.debug(f"Insert sonucu: {insert_result}")
            
            self.collection.flush()  # Veriyi diske yazmayı garantile
            logger.info(f"Belge vektör veritabanına eklendi: {doc_id}")
            
            # İşlem sonunda koleksiyonu serbest bırak
            try:
                self.collection.release()
                logger.debug("Koleksiyon serbest bırakıldı")
            except Exception as e:
                logger.debug(f"Koleksiyon serbest bırakma atlandı: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"Vektör veritabanı ekleme hatası: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    def find_similar_documents(self, text_query, limit=5, min_score=0.85):
        """
        Metne en benzer belgeleri bulur
        
        Args:
            text_query (str): Sorgu metni
            limit (int): Maksimum sonuç sayısı
            min_score (float): Minimum benzerlik skoru (0.0-1.0)
            
        Returns:
            list: Benzer belgelerin listesi
        """
        try:
            # Koleksiyonu yükle
            self.collection.load()
            
            # Sorgu metnini vektöre dönüştür
            query_embedding = self.model.encode(text_query).tolist()
            
            # Milvus'ta arama yap
            search_params = {
                "metric_type": "COSINE", 
                "params": {"nprobe": VECTORDB_CONFIG['nprobe']}
            }
            
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                output_fields=["doc_id", "class", "file_path", "content_preview", "text_hash"]
            )
            
            # Sonuçları işle
            similar_docs = []
            for hit in results[0]:
                if hit.score < min_score:
                    continue
                    
                similar_docs.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "class": hit.entity.get("class"),
                    "file_path": hit.entity.get("file_path"),
                    "text_hash": hit.entity.get("text_hash"),
                    "similarity": hit.score,
                    "preview": hit.entity.get("content_preview")
                })
                
            logger.info(f"Benzer belge araması: {len(similar_docs)} sonuç bulundu (min_score={min_score})")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Vektör veritabanı arama hatası: {e}")
            return []
        finally:
            # Koleksiyonu RAM'den boşalt
            self.collection.release()
    
    def check_duplicate_document(self, text_content, min_similarity=0.95):
        """
        Metnin halihazırda sistemde var olup olmadığını kontrol eder
        
        Args:
            text_content (str): Kontrol edilecek metin
            min_similarity (float): Minimum benzerlik eşiği (0.0-1.0)
            
        Returns:
            dict: Bulunan benzer belge veya None
        """
        # Boş içerik kontrolü
        if not text_content or len(text_content.strip()) < 20:
            return {"is_duplicate": False, "error": "Metin içeriği çok kısa veya boş"}
        
        # Hash-tabanlı tam metin kontrolü
        text_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()
        
        # Koleksiyonu yükle
        self.collection.load()
        
        try:
            # Önce hash ile tam eşleşme ara
            direct_hit_query = f'text_hash == "{text_hash}"'
            direct_hits = self.collection.query(direct_hit_query, output_fields=["doc_id", "file_path"])
            
            if direct_hits:
                return {
                    "is_duplicate": True,
                    "duplicate_doc_id": direct_hits[0]["doc_id"],
                    "similarity": 1.0,  # Tam eşleşme
                    "file_path": direct_hits[0]["file_path"],
                    "match_type": "hash"
                }
            
            # Benzerlik temelli kontrol
            similar_docs = self.find_similar_documents(
                text_content, 
                limit=1,
                min_score=min_similarity
            )
            
            if similar_docs:
                return {
                    "is_duplicate": True,
                    "duplicate_doc_id": similar_docs[0]["doc_id"],
                    "similarity": similar_docs[0]["similarity"],
                    "file_path": similar_docs[0]["file_path"],
                    "match_type": "semantic"
                }
            
            return {"is_duplicate": False}
            
        except Exception as e:
            logger.error(f"Duplikasyon kontrolü hatası: {e}")
            return {"is_duplicate": False, "error": str(e)}
        finally:
            # Koleksiyonu RAM'den boşalt
            self.collection.release()