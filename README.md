# Renaissance-recon

Bu proje, hedef bir domain üzerinde pasif ve aktif bilgi toplama işlemleri gerçekleştiren, terminal üzerinden çalışabilen ve çıktıları görsel olarak web arayüzde sunabilen bir OSINT & Recon aracıdır.

## Özellikler

* Subdomain keşfi (Sublist3r entegrasyonu)
* Dizin fuzzing (ffuf entegrasyonu)
* JS dosyalarından ve sayfalardan secret/anahtar keşfi (SubDomainizer entegrasyonu)
* Thread destekli tarama işlemleri
* Flask tabanlı web arayüzü ile sonuçların görselleştirilmesi
* (İleride) Gemini API ile zafiyet analizi ve önerileri
* PYTHON 3.9 GEREKTİRİR.

## Kurulum

1.  Bu repoyu klonlayın veya indirin.
2.  Gerekli Python kütüphanelerini yükleyin:
    ```bash
    pip install -r requirements.txt
    ```
3.  `ffuf` aracının sisteminizde kurulu ve PATH üzerinde olduğundan emin olun.
4.  (İleride Gemini API için) `.env` dosyası oluşturup `GEMINI_API_KEY='YOUR_API_KEY'` şeklinde anahtarınızı ekleyin.

## Kullanım

Uygulamayı başlatmak için:
```bash
python app.py
Ardından web tarayıcınızda http://127.0.0.1:5000 adresine gidin.

## Test edilebilecek URL'ler
- https://nsonaniya2010.github.io/neeraj.github.io/
- google.com
- https://www.facebook.com

(CLI kullanımı detayları eklenecek.)

Katkıda Bulunma
(Katkıda bulunma yönergeleri eklenecek.)

Lisans
(Lisans bilgisi eklenecek.)
