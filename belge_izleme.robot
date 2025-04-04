*** Settings ***
Documentation    Sürekli belge izleme ve otomatik işleme RPA süreci
Library    RPA.FileSystem
Library    Process
Library    OperatingSystem
Library    Collections
Library    DateTime
Library    String

*** Variables ***
${MONGO_CONNECTION_STRING}    mongodb://localhost:27017/
${DATABASE_NAME}              document_db
${COLLECTION_NAME}            processed_documents
${INPUT_FOLDER}               ${CURDIR}${/}input_documents
${ARCHIVE_FOLDER}             ${CURDIR}${/}input_documents${/}archive
${OUTPUT_FOLDER}              ${CURDIR}${/}processed_results
${PYTHON_SCRIPT}              ${CURDIR}${/}document_classifier.py
${CHECK_INTERVAL}             5
${MAX_RUNTIME}                28800
${PROCESSED_FILES_LOG}        ${CURDIR}${/}processed_files.txt
${BASE_PATH}                  ${CURDIR}
${PYTHONIOENCODING}    utf-8
*** Tasks ***
Belgeleri Sürekli İzle ve İşle
    [Documentation]    Belirtilen klasörü sürekli izler ve yeni belgeleri işler

    Log To Console    \n=== BELGE İZLEME BAŞLATILIYOR ===
    ${start_time}=    Get Current Date
    Log To Console    Başlangıç zamanı: ${start_time}

    Create Directory If Not Exists    ${INPUT_FOLDER}
    Create Directory If Not Exists    ${ARCHIVE_FOLDER}
    Create Directory If Not Exists    ${OUTPUT_FOLDER}
    Log To Console    Dizinler kontrol edildi

    @{processed_files}=    Load Processed Files
    Log To Console    İşlenmiş dosya sayısı: ${processed_files.__len__()}

    Log    Belge izleme başlatıldı: ${INPUT_FOLDER}
    Log To Console    Belge izleme başlatıldı: ${INPUT_FOLDER}
    Log To Console    İzleme aralığı: ${CHECK_INTERVAL} saniye

    ${running}=    Set Variable    ${TRUE}
    ${cycle_count}=    Set Variable    ${0}
    WHILE    ${running}
        ${cycle_count}=    Evaluate    ${cycle_count} + 1
        Log To Console    \n--- Döngü #${cycle_count} ---

        ${current_time}=    Get Current Date
        ${elapsed_seconds}=    Subtract Date From Date    ${current_time}    ${start_time}
        Log To Console    Geçen süre: ${elapsed_seconds} saniye (Maksimum: ${MAX_RUNTIME})

        IF    ${elapsed_seconds} > ${MAX_RUNTIME}
            Log To Console    UYARI: Maksimum çalışma süresi aşıldı (${MAX_RUNTIME} saniye). RPA süreci durdurulacak.
            ${running}=    Set Variable    ${FALSE}
        ELSE
            Log To Console    ${INPUT_FOLDER} klasöründeki dosyalar listeleniyor...
            @{all_files}=    RPA.FileSystem.List Files In Directory    ${INPUT_FOLDER}
            Log To Console    Bulunan dosya sayısı: ${all_files.__len__()}

            @{files}=    Create List

            # Dosya uzantılarını filtreleme
            FOR    ${file}    IN    @{all_files}
                ${extension}=    Get File Extension    ${file}
                ${extension}=    Convert To Lower Case    ${extension}
                IF    '${extension}' == '.pdf' or '${extension}' == '.tif' or '${extension}' == '.jpg' or '${extension}' == '.png'
                    Append To List    ${files}    ${file}
                    Log To Console    ✓ Desteklenen format (${extension}): ${file}
                ELSE
                    Log To Console    ✗ Desteklenmeyen format (${extension}): ${file}
                END
            END

            Log To Console    İşlenecek dosya sayısı: ${files.__len__()}
            ${new_files_found}=    Set Variable    ${FALSE}

            FOR    ${file}    IN    @{files}
                ${full_path}=    RPA.FileSystem.Join Path    ${INPUT_FOLDER}    ${file}
                ${is_processed}=    Is File Processed    ${full_path}    ${processed_files}

                IF    not ${is_processed}
                    Log To Console    \n=== YENİ BELGE BULUNDU: ${file} ===
                    ${new_files_found}=    Set Variable    ${TRUE}

                    TRY
                        ${result}=    Process Document    ${full_path}    ${MONGO_CONNECTION_STRING}    ${DATABASE_NAME}    ${COLLECTION_NAME}
                        ${json_str}=    Evaluate    json.dumps($result, ensure_ascii=False, indent=2)    json
                        
                        ${timestamp}=    Get Current Date    result_format=%Y%m%d_%H%M%S
                        ${filename_only}=    Get File Name    ${file}
                        ${safe_filename}=    Set Variable    ${timestamp}_${filename_only}
                        ${output_file}=    RPA.FileSystem.Join Path    ${OUTPUT_FOLDER}    ${safe_filename}.json
                        
                        RPA.FileSystem.Create File    ${output_file}    ${json_str}
                        Log To Console    JSON sonuç dosyası oluşturuldu: ${output_file}
                        
                        # İşlenen dosyalara ekle
                        Append To List    ${processed_files}    ${full_path}
                        Log To Console    İşlenen dosya listeye eklendi: ${full_path}

                        # Log dosyasına ekle
                        RPA.FileSystem.Append To File    ${PROCESSED_FILES_LOG}    ${full_path}\n
                        Log To Console    İşlenen dosya log dosyasına kaydedildi

                        ${has_class}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${result}    classification
                        IF    ${has_class}
                            ${has_class_info}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${result['classification']}    class
                            IF    ${has_class_info}
                                Log To Console    Belge sınıfı: ${result['classification']['class']}, Güven: ${result['classification']['confidence']}
                            ELSE
                                Log To Console    Belge sınıflandırıldı fakat sınıf bilgisi bulunamadı
                            END
                        ELSE
                            Log To Console    Belge işlenmiş fakat sınıflandırma bilgisi bulunamadı
                        END

                    EXCEPT    AS    ${error}
                        Log To Console    HATA: Belge işleme sırasında hata oluştu: ${error}
                    END
                END
            END

            # Yeni belgeler işlendiyse Python yönlendirme scriptini çalıştır
            IF    ${new_files_found}
                Log To Console    \n=== BELGE YÖNLENDİRME BAŞLATILIYOR ===
                ${routing_result}=    Run Process    python    ${CURDIR}${/}document_router.py    shell=True    stdout=${TEMPDIR}${/}routing_stdout.txt    stderr=${TEMPDIR}${/}routing_stderr.txt
                
                ${routing_stdout}=    Get File    ${TEMPDIR}${/}routing_stdout.txt    encoding=latin1
                ${routing_stderr}=    Get File    ${TEMPDIR}${/}routing_stderr.txt    encoding=latin1
                
                Log To Console    Yönlendirme çıktısı: ${routing_stdout}
                
                IF    ${routing_result.rc} == 0
                    Log To Console    Belgeler başarıyla yönlendirildi
                ELSE
                    Log To Console    HATA: Belge yönlendirme sırasında hata oluştu!
                    Log To Console    Hata kodu: ${routing_result.rc}
                    Log To Console    Hata: ${routing_stderr}
                END
            ELSE
                Log To Console    Yeni belge bulunamadı, ${CHECK_INTERVAL} saniye sonra tekrar kontrol edilecek.
            END

            Log To Console    ${CHECK_INTERVAL} saniye bekleniyor...
            Sleep    ${CHECK_INTERVAL}
        END
    END

    Log To Console    \n=== BELGE İZLEME SÜRECİ TAMAMLANDI ===

*** Keywords ***
Get File Extension
    [Arguments]    ${file_obj}
    ${filename}=    Convert To String    ${file_obj}
    ${has_extension}=    Run Keyword And Return Status    Should Contain    ${filename}    .
    IF    ${has_extension}
        ${extension}=    Fetch From Right    ${filename}    .
        RETURN    .${extension}
    ELSE
        RETURN    ${EMPTY}
    END

Process Document
    [Arguments]    ${document_path}    ${mongo_uri}    ${db_name}    ${collection_name}
    [Documentation]    Python belge işleme scriptini çağırır ve sınıflandırma sonucunu döndürür
    Log To Console    Belge işleniyor: ${document_path}
    
    # Dosya adını ve timestamp'i al
    ${filename_only}=    Get File Name    ${document_path}
    ${timestamp}=    Get Current Date    result_format=%Y%m%d_%H%M%S
    ${result}=    Run Process    python    ${PYTHON_SCRIPT}    --file    ${document_path}    --mode    full    --save_to_mongo    ${mongo_uri}    env:PYTHONIOENCODING=utf-8    shell=True    stdout=${TEMPDIR}${/}stdout.txt    stderr=${TEMPDIR}${/}stderr.txt
    
    # Latin-1 kodlaması kullan
    ${stdout}=    Get File    ${TEMPDIR}${/}stdout.txt    encoding=latin-1
    ${stderr}=    Get File    ${TEMPDIR}${/}stderr.txt    encoding=latin-1
    
    Log To Console    Çıktı kodu: ${result.rc}
    Log To Console    Standart çıktı: ${stdout}
    
    IF    ${result.rc} != 0
        Log To Console    HATA: Python script çalıştırma hatası! Hata kodu: ${result.rc}
        Log To Console    Hata çıktısı: ${stderr}
        RETURN    {"error": "${stderr}"}
    END
    
    # JSON dosyasını doğrudan oku
    ${json_path}=    Set Variable    ${OUTPUT_FOLDER}${/}${timestamp}_${filename_only}.json
    ${exists}=    Run Keyword And Return Status    File Should Exist    ${json_path}
    
    IF    ${exists}
        ${json_content}=    Get File    ${json_path}    encoding=utf-8
        TRY
            ${json_result}=    Evaluate    json.loads('''${json_content}''')    modules=json
            Log To Console    JSON dosyasından başarıyla okundu
            RETURN    ${json_result}
        EXCEPT    AS    ${error}
            Log To Console    HATA: JSON dosyasından okuma hatası: ${error}
        END
    END
    
    # JSON dosyasını okuyamadıysak, çıktıdan almayı dene
    TRY
        # JSON satırını ara (yalnızca JSON olan satırı bul)
        ${lines}=    Split To Lines    ${stdout}
        ${json_text}=    Set Variable    ${EMPTY}
        
        FOR    ${line}    IN    @{lines}
            ${starts_with_json}=    Run Keyword And Return Status    Should Start With    ${line}    {
            IF    ${starts_with_json}
                ${json_text}=    Set Variable    ${line}
                Exit For Loop
            END
        END
        
        # JSON satırı bulunamadıysa, basit bir sonuç döndür
        IF    $json_text == "${EMPTY}"
            Log To Console    UYARI: JSON satırı bulunamadı, basit bir sonuç oluşturuluyor
            RETURN    {"status": "unknown", "file_path": "${document_path}", "file_name": "${filename_only}"}
        END
        
        # Regex ile dosya yollarını temizle
        ${json_text}=    Replace String Using Regexp    ${json_text}    C:\\\\    C:/    
        ${json_text}=    Replace String Using Regexp    ${json_text}    \\\\    /    
        
        ${json_result}=    Evaluate    json.loads('''${json_text}''')    modules=json
        Log To Console    Çıktıdan JSON başarıyla ayrıştırıldı
        RETURN    ${json_result}
    EXCEPT    AS    ${error}
        Log To Console    HATA: JSON ayrıştırma hatası: ${error}
        Log To Console    Ayrıştırılamayan çıktı: ${stdout}
        RETURN    {"status": "error", "error": "JSON ayrıştırma hatası", "file_path": "${document_path}", "file_name": "${filename_only}"}
    END
    
Try Run Python Script
    [Arguments]    ${document_path}    ${mongo_uri}    ${db_name}    ${collection_name}
    [Documentation]    Python scriptini direkt çalıştırmayı dener
    Log To Console    Manuel Python script testi: ${document_path}
    ${cmd}=    Set Variable    python "${PYTHON_SCRIPT}" --file "${document_path}" --mode classify --verbose
    Log To Console    Komut: ${cmd}
    ${result}=    Run    ${cmd}
    Log To Console    Komut çıktısı:\n${result}

Create Directory If Not Exists
    [Arguments]    ${directory_path}
    Log To Console    Dizin kontrol ediliyor: ${directory_path}
    ${exists}=    Does Directory Exist    ${directory_path}
    Log To Console    Dizin var mı: ${exists}
    IF    not ${exists}
        Log To Console    Dizin oluşturuluyor: ${directory_path}
        Create Directory    ${directory_path}
        Log To Console    Dizin oluşturuldu: ${directory_path}
    END

Load Processed Files
    [Documentation]    İşlenen dosyaların listesini yükler
    Log To Console    İşlenen dosyalar yükleniyor: ${PROCESSED_FILES_LOG}
    ${exists}=    Does File Exist    ${PROCESSED_FILES_LOG}
    Log To Console    İşlenen dosyalar listesi var mı: ${exists}
    ${processed_files}=    Create List
    IF    ${exists}
        ${content}=    Get File    ${PROCESSED_FILES_LOG}
        Log To Console    İşlenen dosyalar dosya içeriği: ${content}
        @{lines}=    Split To Lines    ${content}
        Log To Console    Bulunan satır sayısı: ${lines.__len__()}
        FOR    ${line}    IN    @{lines}
            ${trimmed_line}=    Strip String    ${line}
            Log To Console    İşlenen satır: "${trimmed_line}"
            IF    $trimmed_line != ""
                Append To List    ${processed_files}    ${trimmed_line}
                Log To Console    Listeye eklendi: ${trimmed_line}
            ELSE
                Log To Console    Boş satır, atlanıyor
            END
        END
    ELSE
        Log To Console    İşlenen dosyalar dosyası bulunamadı, yeni oluşturuluyor
        Create File    ${PROCESSED_FILES_LOG}
        Log To Console    Yeni dosya oluşturuldu: ${PROCESSED_FILES_LOG}
    END
    Log To Console    Toplam işlenen dosya sayısı: ${processed_files.__len__()}
    RETURN    ${processed_files}

Is File Processed
    [Arguments]    ${file_path}    ${processed_files}
    Log To Console    Dosya işlenmiş mi kontrol ediliyor: ${file_path}
    FOR    ${processed_file}    IN    @{processed_files}
        Log To Console    Karşılaştırılıyor: "${processed_file}" - "${file_path}"
        ${is_equal}=    Run Keyword And Return Status    Should Be Equal As Strings    ${processed_file}    ${file_path}
        IF    ${is_equal}
            Log To Console    Eşleşme bulundu! Dosya daha önce işlenmiş
            RETURN    ${TRUE}
        END
    END
    Log To Console    Eşleşme bulunamadı. Dosya daha önce işlenmemiş
    RETURN    ${FALSE}
