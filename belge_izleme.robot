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
            @{all_files}=    List Files In Directory    ${INPUT_FOLDER}
            Log To Console    Bulunan dosya sayısı: ${all_files.__len__()}
            Log To Console    Tüm dosyalar: ${all_files}

            @{files}=    Create List

            # Dosya uzantılarını filtreleme
            FOR    ${file}    IN    @{all_files}
                ${extension}=    Get File Extension    ${file}
                ${extension}=    Convert To Lower Case    ${extension}
                Log To Console    Dosya: "${file}" - Uzantı: "${extension}"

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
                ${full_path}=    Join Path    ${INPUT_FOLDER}    ${file}
                Log To Console    Tam dosya yolu: ${full_path}

                ${is_processed}=    Is File Processed    ${full_path}    ${processed_files}
                Log To Console    Daha önce işlenmiş mi: ${is_processed}

                IF    not ${is_processed}
                    Log To Console    \n=== YENİ BELGE BULUNDU: ${file} ===
                    ${new_files_found}=    Set Variable    ${TRUE}

                    Try Run Python Script    ${full_path}    ${MONGO_CONNECTION_STRING}    ${DATABASE_NAME}    ${COLLECTION_NAME}

                    ${timestamp}=    Get Current Date    result_format=%Y%m%d_%H%M%S
                    ${filename_only}=    Get File Name    ${file}
                    ${safe_filename}=    Set Variable    ${timestamp}_${filename_only}
                    ${output_file}=    Join Path    ${OUTPUT_FOLDER}    ${safe_filename}.json
                    Log To Console    Sonuç dosyası oluşturuluyor: ${output_file}

                    TRY
                        ${result}=    Process Document    ${full_path}    ${MONGO_CONNECTION_STRING}    ${DATABASE_NAME}    ${COLLECTION_NAME}

                        ${json_str}=    Evaluate    json.dumps($result, ensure_ascii=False, indent=2)    json
                        Create File    ${output_file}    ${json_str}
                        Log To Console    JSON sonuç dosyası oluşturuldu: ${output_file}

                        # Dosyayı arşive taşırken sadece dosya adını kullanın
                        ${filename_only_for_archive}=    Get File Name    ${file}
                        ${archive_path}=    Join Path    ${ARCHIVE_FOLDER}    ${filename_only_for_archive}
                        Log To Console    Belge arşive taşınıyor: ${archive_path}
                        Move File    ${full_path}    ${archive_path}
                        Log To Console    Belge arşive taşındı: ${archive_path}

                        # İşlenen dosyalara ekle
                        Append To List    ${processed_files}    ${full_path}
                        Log To Console    İşlenen dosya listeye eklendi: ${full_path}

                        # Log dosyasına ekle
                        Append To File    ${PROCESSED_FILES_LOG}    ${full_path}\n
                        Log To Console    İşlenen dosya log dosyasına kaydedildi

                        Log To Console    Belge başarıyla işlendi: ${file}

                        # DÜZELTİLMİŞ - JSON dictionary erişimi
                        # [classification][class] yerine, Robot 7.2'de dictionary index:
                        Log To Console    Belge sınıfı: ${result['classification']['class']}, Güven: ${result['classification']['confidence']}

                    EXCEPT    AS    ${error}
                        Log To Console    HATA: Belge işleme sırasında hata oluştu: ${error}
                    END
                END
            END

            IF    not ${new_files_found}
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
    Log To Console    Komut: python ${PYTHON_SCRIPT} --file ${document_path} --mode full --save_to_mongo ${mongo_uri}

    ${result}=    Run Process    python    ${PYTHON_SCRIPT}    --file    ${document_path}    --mode    full    --save_to_mongo    ${mongo_uri}    shell=True    stdout=${TEMPDIR}${/}stdout.txt    stderr=${TEMPDIR}${/}stderr.txt

    ${stdout}=    Get File    ${TEMPDIR}${/}stdout.txt    encoding=latin1
    ${stderr}=    Get File    ${TEMPDIR}${/}stderr.txt    encoding=latin1

    Log To Console    Çıktı kodu: ${result.rc}
    Log To Console    Standart çıktı: ${stdout}

    IF    ${result.rc} != 0
        Log To Console    HATA: Python script çalıştırma hatası! Hata kodu: ${result.rc}
        Log To Console    Hata çıktısı: ${stderr}
        RETURN    {"error": "${stderr}"}
    END

    TRY
        ${json_result}=    Evaluate    json.loads('''${stdout}''')    json
        Log To Console    JSON başarıyla ayrıştırıldı
        RETURN    ${json_result}
    EXCEPT    AS    ${error}
        Log To Console    HATA: JSON ayrıştırma hatası: ${error}
        Log To Console    Ayrıştırılamayan çıktı: ${stdout}
        RETURN    {"error": "JSON ayrıştırma hatası: ${error}"}
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
