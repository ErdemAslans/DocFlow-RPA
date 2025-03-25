"""
Belge içerik analizi için LLM entegrasyonu.
"""
import time
import threading
from queue import Queue
import torch

from config.settings import LLM_CONFIG

class DocumentAnalyzer:
    def __init__(self, model=None, timeout=None):
        """
        DeepSeek LLM kullanarak belge analizi sınıfı.
        
        Args:
            model (str, optional): Kullanılacak LLM modeli. Varsayılan LLM_CONFIG['model'].
            timeout (int, optional): Analiz işlemi için zaman aşımı (saniye). Varsayılan LLM_CONFIG['timeout'].
        """
        self.model = model or LLM_CONFIG['model']
        self.timeout = timeout or LLM_CONFIG['timeout']
        self.max_chars = LLM_CONFIG['max_chars']
        self.pipe = None
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"LLM için kullanılan cihaz: {device}")

        try:
            # Transformers pipeline'ı başlat
            from transformers import pipeline
            
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            print(f"LLM modeli başarıyla yüklendi: {self.model}")
        except Exception as e:
            print(f"LLM modeli yüklenirken hata oluştu: {e}")
            print("Analiz işlevi kullanılamayacak.")

    def analyze_document(self, text, document_class, prompt_template=None):
        """
        Belge metnini analiz et ve önemli bilgileri çıkar.
        Gelişmiş hata yakalama ve zaman aşımı kontrolü içerir.
        
        Args:
            text (str): Analiz edilecek belge metni
            document_class (str): Belgenin sınıfı
            prompt_template (str, optional): Özel bir prompt şablonu
            
        Returns:
            dict: Analiz sonuçları
        """
        # LLM modeli yoksa analiz atla
        if self.pipe is None:
            return {
                'analysis': "LLM modeli yüklenemediği için analiz yapılamadı.",
                'model': "None",
                'error': "Model yüklenemedi"
            }
            
        # Sonuç ve hata kuyrukları
        result_queue = Queue()
        exception_queue = Queue()

        # Prompt şablonunu belirle
        if prompt_template is None:
            # Sınıf-spesifik özel şablonlar
            class_specific_templates = {
                'letter': """
                Bu belge "letter" (mektup) olarak sınıflandırılmıştır.
                Lütfen aşağıdaki mektubu analiz et ve şu bilgileri çıkar:

                1. Mektubun kimden geldiği ve kime hitap ettiği
                2. Mektubun yazılış tarihi
                3. Mektubun ana konusu ve amacı
                4. Mektupta belirtilen önemli bilgiler
                5. Mektupta bahsedilen kişiler, kurumlar veya yerler
                6. Mektubun tonu ve üslubu (resmi, gayri resmi, iş mektubu vb.)
                7. Mektubun içeriğinin kısa bir özeti

                Mektup İçeriği:
                {text}
                """,

                'form': """
                Bu belge "form" (form) olarak sınıflandırılmıştır.
                Lütfen aşağıdaki formu analiz et ve şu bilgileri çıkar:

                1. Formun türü ve amacı
                2. Formda bulunan ana bölümler
                3. Formdaki önemli alanlar ve bilgiler (varsa)
                4. Form ile ilgili kurumsal bilgiler
                5. Formun doldurulması için gereken bilgiler
                6. Formun genel yapısı ve organizasyonu
                7. Formun içeriğinin kısa bir özeti

                Form İçeriği:
                {text}
                """,

                'invoice': """
                Bu belge "invoice" (fatura) olarak sınıflandırılmıştır.
                Lütfen aşağıdaki faturayı analiz et ve şu bilgileri çıkar:

                1. Fatura tarihi ve numarası
                2. Satıcı/sağlayıcı bilgileri
                3. Alıcı bilgileri
                4. Fatura kalemleri (ürünler/hizmetler ve fiyatları)
                5. Toplam tutar, vergi tutarı ve varsa indirimler
                6. Ödeme koşulları ve son ödeme tarihi
                7. Faturanın içeriğinin kısa bir özeti

                Fatura İçeriği:
                {text}
                """,

                'email': """
                Bu belge "email" (e-posta) olarak sınıflandırılmıştır.
                Lütfen aşağıdaki e-postayı analiz et ve şu bilgileri çıkar:

                1. E-postanın kimden geldiği ve kime gönderildiği
                2. E-postanın tarihi ve saati
                3. E-postanın konusu
                4. E-postada belirtilen önemli bilgiler veya talepler
                5. E-postada bahsedilen kişiler, kurumlar veya projeler
                6. E-postanın tonu ve amacı
                7. E-postanın içeriğinin kısa bir özeti

                E-posta İçeriği:
                {text}
                """
            }

            # Sınıfa özel şablon varsa kullan, yoksa genel şablonu kullan
            prompt_template = class_specific_templates.get(document_class, """
            Bu belge "{document_class}" olarak sınıflandırılmıştır.
            Lütfen aşağıdaki belgeyi analiz et ve şu bilgileri çıkar:

            1. Belge tipi ve amacı nedir?
            2. Ana konusu veya içeriği nedir?
            3. Önemli anahtar-değer çiftleri (varsa)
            4. Belgedeki önemli varlıklar (kişiler, şirketler, tarihler vb.)
            5. Belgenin yapısı ve formatı nasıldır?
            6. Belgenin hedef kitlesi kimdir?
            7. Belgenin içeriğinin özeti

            Belge İçeriği:
            {text}
            """)

        # Analiz çalışanı
        def analyze_worker():
            try:
                # Analiz başlangıç zamanı
                start_time = time.time()
                print(f"LLM analizi başlıyor, metin uzunluğu: {len(text)} karakter")

                # Metni kısalt (çok uzunsa)
                truncated_text = text[:self.max_chars] if len(text) > self.max_chars else text

                # Prompt oluştur
                prompt = prompt_template.format(document_class=document_class, text=truncated_text)

                # LLM yanıtı al
                response = self.pipe(
                    prompt,
                    max_new_tokens=LLM_CONFIG['max_tokens'],
                    temperature=LLM_CONFIG['temperature'],
                    top_p=0.9,
                    do_sample=True
                )

                generated_text = response[0]['generated_text']

                # Prompt'u çıkar ve sadece yanıtı al
                response_text = generated_text[len(prompt):].strip()

                # İşlem süresini hesapla
                elapsed_time = time.time() - start_time
                print(f"LLM analizi tamamlandı: {len(response_text)} karakter, {elapsed_time:.2f} saniye")

                # Sonucu kuyruğa ekle
                result_queue.put({
                    'analysis': response_text,
                    'model': self.model,
                    'processing_time': elapsed_time
                })

            except Exception as e:
                print(f"LLM analiz hatası: {e}")
                import traceback
                print(traceback.format_exc())
                exception_queue.put(e)

        # İş parçacığını başlat
        thread = threading.Thread(target=analyze_worker)
        thread.daemon = True
        thread.start()

        # Zaman aşımı ile bekle
        thread.join(timeout=self.timeout)

        # Thread hala çalışıyorsa zaman aşımına uğradı
        if thread.is_alive():
            print(f"LLM analizi zaman aşımına uğradı ({self.timeout} saniye)")
            return {
                'analysis': f"[LLM analizi zaman aşımına uğradı ({self.timeout} saniye). Belge çok karmaşık veya LLM işlem kapasitesini aşıyor olabilir.]",
                'model': self.model,
                'error': 'timeout'
            }

        # İstisna olup olmadığını kontrol et
        if not exception_queue.empty():
            e = exception_queue.get()
            return {
                'analysis': f"[LLM analiz hatası: {str(e)}]",
                'model': self.model,
                'error': str(e)
            }

        # Sonuçları döndür
        if not result_queue.empty():
            return result_queue.get()
        else:
            return {
                'analysis': "[LLM analizi tamamlandı ancak sonuç bulunamadı]",
                'model': self.model,
                'error': 'no_result'
            }
