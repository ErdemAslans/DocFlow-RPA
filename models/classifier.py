"""
Belge sınıflandırma modeli.
RPA için optimize edilmiş versiyon - sadece tahmin işlevselliği içerir.
"""
import os
import torch
import numpy as np
from PIL import Image
from torchvision import transforms

from config.settings import CLASSES, MODEL_CONFIG, MODEL_PATH

class SwinImageProcessor:
    def __init__(self, image_size=224, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]):
        self.image_size = image_size
        self.mean = mean
        self.std = std

        # Temel dönüşüm
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std)
        ])

    def __call__(self, images, return_tensors="pt"):
        """
        Görüntüleri işleyip model için hazırlar
        """
        if not isinstance(images, list):
            images = [images]

        pixel_values = []
        for image in images:
            try:
                pixel_value = self.transform(image)
                pixel_values.append(pixel_value)
            except Exception as e:
                print(f"Görüntü dönüşüm hatası: {e}")
                # Hata durumunda varsayılan bir tensör oluştur
                pixel_values.append(torch.zeros((3, self.image_size, self.image_size)))

        # Tensörleri yığınla
        if return_tensors == "pt":
            pixel_values = torch.stack(pixel_values)

        return {"pixel_values": pixel_values}


class DocumentClassifier:
    def __init__(self, model_path=None, num_classes=16, pretrained_model=None):
        """
        Belge sınıflandırıcı modelini başlatır
        
        Args:
            model_path (str, optional): Eğitilmiş model dosyasının yolu. Belirtilmezse varsayılan yol kullanılır.
            num_classes (int, optional): Sınıf sayısı. Varsayılan: 16
            pretrained_model (str, optional): Pretrained model adı. Belirtilmezse yapılandırmadaki değer kullanılır.
        """
        from transformers import SwinForImageClassification
        
        # Yapılandırma değerlerini kullan
        num_classes = num_classes or MODEL_CONFIG['num_classes']
        pretrained_model = pretrained_model or MODEL_CONFIG['pretrained_model']
        model_path = model_path or MODEL_PATH
        
        self.processor = SwinImageProcessor(image_size=MODEL_CONFIG['image_size'])
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"Cihaz: {self.device}")

        # Model yolunu kontrol et
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model dosyası bulunamadı: {model_path}")

        print(f"Model yükleniyor: {model_path}")
        
        try:
            # Model state_dict'ini yükle
            checkpoint = torch.load(model_path, map_location=self.device)

            # Geçici bir model oluştur
            temp_model = SwinForImageClassification.from_pretrained(
                pretrained_model,
                num_labels=num_classes,
                ignore_mismatched_sizes=True
            )

            # Asıl modeli yapılandırmayla oluştur
            self.model = SwinForImageClassification(temp_model.config)

            # Eğitilmiş model ağırlıklarını yükle
            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                self.model.load_state_dict(checkpoint['model_state_dict'])
                print(f"Model yüklendi: {model_path} (Epoch: {checkpoint.get('epoch', 'Bilinmiyor')})")
            else:
                self.model.load_state_dict(checkpoint)
                print(f"Model yüklendi: {model_path}")

            # Geçici modeli temizle
            import gc
            del temp_model
            gc.collect()
            torch.cuda.empty_cache()
            
        except Exception as e:
            raise RuntimeError(f"Model yüklenirken hata oluştu: {e}")
            
        # Modeli değerlendirme moduna al ve cihaza taşı
        self.model.eval()
        self.model.to(self.device)
        
        # Sınıf index eşleştirmesi
        self.idx_to_class = {i: cls for i, cls in enumerate(CLASSES)}
        
        print("Sınıflandırıcı hazır!")

    def predict(self, image_path):
        """
        Bir belge görüntüsünü sınıflandırır
        
        Args:
            image_path (str): Belge görüntüsünün dosya yolu
            
        Returns:
            dict: Sınıflandırma sonuçları
        """
        try:
            # Görüntüyü yükle
            image = self._load_image(image_path)
            if image is None:
                return {
                    'class': 'error',
                    'confidence': 0.0,
                    'error': "Görüntü yüklenemedi",
                    'all_probs': {},
                    'sorted_probs': []
                }
                
            # İşle
            inputs = self.processor(images=image, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(self.device)

            # Tahmin yap
            with torch.no_grad():
                outputs = self.model(pixel_values=pixel_values)
                probs = torch.nn.functional.softmax(outputs.logits, dim=1)

                # En yüksek olasılığa sahip sınıfı ve güveni al
                confidence, predicted_class_idx = torch.max(probs, 1)
                predicted_class = self.idx_to_class[predicted_class_idx.item()]
                confidence = confidence.item()

                # Tüm sınıf olasılıklarını al
                class_probs = {self.idx_to_class[i]: prob.item() for i, prob in enumerate(probs[0])}

                # Olasılıkları sırala
                sorted_probs = sorted(class_probs.items(), key=lambda x: x[1], reverse=True)

                return {
                    'class': predicted_class,
                    'confidence': confidence,
                    'all_probs': class_probs,
                    'sorted_probs': sorted_probs
                }
        except Exception as e:
            import traceback
            print(f"Tahmin hatası: {e}")
            print(traceback.format_exc())
            return {
                'class': 'error',
                'confidence': 0.0,
                'error': str(e),
                'all_probs': {},
                'sorted_probs': []
            }
            
    def _load_image(self, image_path):
        """
        Görüntü dosyasını yükler, çeşitli formatlara destek verir
        
        Args:
            image_path (str): Görüntü dosyasının yolu
            
        Returns:
            PIL.Image: Yüklenen görüntü veya None (hata durumunda)
        """
        try:
            # PIL ile görüntüyü açma
            with Image.open(image_path) as img:
                return img.convert('RGB')
        except Exception as e:
            print(f"PIL ile yükleme hatası ({image_path}): {e}")

            # TIF dosyaları için alternatif yöntem
            try:
                import imageio.v2 as imageio 
                img_array = imageio.imread(image_path)

                # 2D (gri tonlamalı) bir görüntüyse 3 kanala dönüştür
                if len(img_array.shape) == 2:
                    img_array = np.stack([img_array, img_array, img_array], axis=2)
                elif len(img_array.shape) == 3 and img_array.shape[2] > 3:
                    # RGBA veya başka çok kanallı formatta ise, ilk 3 kanalı al
                    img_array = img_array[:, :, :3]

                # NumPy dizisini PIL görüntüsüne dönüştür
                return Image.fromarray(np.uint8(img_array))
            except Exception as e2:
                print(f"Alternatif yükleme hatası ({image_path}): {e2}")
                return None
