package com.mercedes.documentprocessing;

public class Document {
    private String id;
    private String filePath;
    private String fileName;
    private String documentClass;
    private double confidence;
    private String extractedText;
    private int textLength;
    private String targetFolder; // Hedef klasör
    private boolean needsReview = false; // İnceleme gerektiriyor mu?
    private boolean ocrFailed = false; // OCR başarısız mı?
    private boolean requiresFinanceApproval = false; // Finans onayı gerektiriyor mu?
    private boolean needsDataExtraction = false; // Veri çıkarımı gerekiyor mu?

    // Getter ve setter metodları
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getFilePath() { return filePath; }
    public void setFilePath(String filePath) { this.filePath = filePath; }

    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }

    public String getDocumentClass() { return documentClass; }
    public void setDocumentClass(String documentClass) { this.documentClass = documentClass; }

    public double getConfidence() { return confidence; }
    public void setConfidence(double confidence) { this.confidence = confidence; }

    public String getExtractedText() { return extractedText; }
    public void setExtractedText(String extractedText) { this.extractedText = extractedText; }

    public int getTextLength() { return textLength; }
    public void setTextLength(int textLength) { this.textLength = textLength; }

    public String getTargetFolder() { return targetFolder; }
    public void setTargetFolder(String targetFolder) { this.targetFolder = targetFolder; }

    public boolean isNeedsReview() { return needsReview; }
    public void setNeedsReview(boolean needsReview) { this.needsReview = needsReview; }

    public boolean isOcrFailed() { return ocrFailed; }
    public void setOcrFailed(boolean ocrFailed) { this.ocrFailed = ocrFailed; }

    public boolean isRequiresFinanceApproval() { return requiresFinanceApproval; }
    public void setRequiresFinanceApproval(boolean requiresFinanceApproval) { this.requiresFinanceApproval = requiresFinanceApproval; }

    public boolean isNeedsDataExtraction() { return needsDataExtraction; }
    public void setNeedsDataExtraction(boolean needsDataExtraction) { this.needsDataExtraction = needsDataExtraction; }
}