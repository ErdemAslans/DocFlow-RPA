package com.mercedes.documentprocessing;

import org.kie.api.KieServices;
import org.kie.api.runtime.KieContainer;
import org.kie.api.runtime.KieSession;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import org.bson.Document;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;

public class DocumentProcessor {

    // Varsayılan MongoDB bağlantı ayarları
    private static String MONGO_URI = "mongodb://localhost:27017/";
    private static String DB_NAME = "document_db";
    private static String COLLECTION_NAME = "processed_documents";
    
    // Klasör yolları
    private static String BASE_ARCHIVE_PATH = "C:/Users/Erdem/OneDrive/Masaüstü/Mercedes/";
    
    public static void main(String[] args) {
        // Komut satırı parametrelerini işle
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--mongo-uri") && i + 1 < args.length) {
                MONGO_URI = args[i + 1];
            } else if (args[i].equals("--db-name") && i + 1 < args.length) {
                DB_NAME = args[i + 1];
            } else if (args[i].equals("--collection-name") && i + 1 < args.length) {
                COLLECTION_NAME = args[i + 1];
            } else if (args[i].equals("--base-path") && i + 1 < args.length) {
                BASE_ARCHIVE_PATH = args[i + 1];
            }
        }
        
        System.out.println("Belge yönlendirici başlatılıyor...");
        System.out.println("MongoDB URI: " + MONGO_URI);
        System.out.println("Database: " + DB_NAME);
        System.out.println("Collection: " + COLLECTION_NAME);
        System.out.println("Temel Klasör Yolu: " + BASE_ARCHIVE_PATH);

        // Drools KieSession oluştur
        KieServices ks = KieServices.Factory.get();
        KieContainer kContainer = ks.getKieClasspathContainer();
        KieSession kSession = kContainer.newKieSession("documentRulesSession");
        
        // MongoDB'ye bağlan
        try (MongoClient mongoClient = MongoClients.create(MONGO_URI)) {
            MongoDatabase database = mongoClient.getDatabase(DB_NAME);
            MongoCollection<Document> collection = database.getCollection(COLLECTION_NAME);
            
            // Hedef klasörleri oluştur
            createTargetFolders();
            
            // İşlenmemiş belgeleri al
            MongoCursor<Document> cursor = collection.find(
                new Document("processed_for_routing", new Document("$ne", true))
            ).iterator();
            
            List<com.mercedes.documentprocessing.Document> processedDocuments = new ArrayList<>();
            int documentCount = 0;
            
            // Her belge için kuralları uygula
            while (cursor.hasNext()) {
                Document mongoDoc = cursor.next();
                documentCount++;
                
                String id = mongoDoc.getObjectId("_id").toString();
                String filePath = mongoDoc.getString("file_path");
                String fileName = mongoDoc.getString("file_name");
                String documentClass = mongoDoc.getString("document_class");
                double confidence = mongoDoc.getDouble("confidence");
                String text = mongoDoc.getString("extracted_text");
                int textLength = text != null ? text.length() : 0;
                
                System.out.println("Belge işleniyor: " + fileName + " (Sınıf: " + documentClass + ")");
                
                // Drools için belge nesnesini oluştur
                com.mercedes.documentprocessing.Document doc = new com.mercedes.documentprocessing.Document();
                doc.setId(id);
                doc.setFilePath(filePath);
                doc.setFileName(fileName);
                doc.setDocumentClass(documentClass);
                doc.setConfidence(confidence);
                doc.setExtractedText(text);
                doc.setTextLength(textLength);
                
                // Kuralları uygula
                kSession.insert(doc);
                kSession.fireAllRules();
                
                // Belgeyi taşı
                boolean moved = moveDocumentToTargetFolder(doc);
                
                // MongoDB'yi güncelle
                collection.updateOne(
                    new Document("_id", mongoDoc.getObjectId("_id")),
                    new Document("$set", new Document("processed_for_routing", true)
                        .append("target_folder", doc.getTargetFolder())
                        .append("needs_review", doc.isNeedsReview())
                        .append("ocr_failed", doc.isOcrFailed()))
                );
                
                processedDocuments.add(doc);
                System.out.println("Belge işlendi ve MongoDB güncellendi: " + fileName);
            }
            
            System.out.println("İşlenen toplam belge sayısı: " + documentCount);
            if (documentCount == 0) {
                System.out.println("İşlenecek yeni belge bulunamadı.");
            }
            
        } catch (Exception e) {
            System.err.println("Hata oluştu: " + e.getMessage());
            e.printStackTrace();
        } finally {
            kSession.dispose();
            System.out.println("Belge yönlendirme tamamlandı.");
        }
    }
    
    private static void createTargetFolders() {
        // Tüm belge sınıfları için klasörler oluştur
        String[] classes = {
            "letter", "form", "email", "handwritten", "advertisement",
            "scientific_report", "scientific_publication", "specification",
            "file_folder", "news_article", "budget", "invoice",
            "presentation", "questionnaire", "resume", "memo",
            "review", "ocr_failed" // Özel durum klasörleri
        };
        
        for (String cls : classes) {
            File folder = new File(BASE_ARCHIVE_PATH + cls);
            if (!folder.exists()) {
                folder.mkdirs();
                System.out.println("Klasör oluşturuldu: " + folder.getPath());
            }
        }
    }
    
    private static boolean moveDocumentToTargetFolder(com.mercedes.documentprocessing.Document doc) {
        try {
            File sourceFile = new File(doc.getFilePath());
            if (!sourceFile.exists()) {
                System.out.println("UYARI: Kaynak dosya bulunamadı: " + doc.getFilePath());
                return false;
            }
            
            String targetFolder = BASE_ARCHIVE_PATH + doc.getTargetFolder() + "/";
            File targetFolderDir = new File(targetFolder);
            if (!targetFolderDir.exists()) {
                targetFolderDir.mkdirs();
            }
            
            Path targetPath = Paths.get(targetFolder + doc.getFileName());
            Files.move(sourceFile.toPath(), targetPath, StandardCopyOption.REPLACE_EXISTING);
            
            System.out.println("Dosya taşındı: " + doc.getFileName() + " -> " + targetPath);
            return true;
            
        } catch (Exception e) {
            System.out.println("Dosya taşıma hatası: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }
}