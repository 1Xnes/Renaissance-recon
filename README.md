# Renaissance Recon

Bu proje, hedef bir domain üzerinde pasif ve aktif bilgi toplama işlemleri gerçekleştiren, terminal üzerinden çalışabilen ve çıktıları görsel olarak web arayüzde sunabilen bir OSINT & Recon aracıdır.

## Özellikler

*   **Subdomain Keşfi:** [Sublist3r](https://github.com/aboul3la/Sublist3r) entegrasyonu ile hedef domaine ait alt alan adlarını tespit eder.
*   **Dizin ve Dosya Fuzzing:** [FFUF](https://github.com/ffuf/ffuf) entegrasyonu ile web sunucularındaki gizli dizinleri ve dosyaları keşfeder.
*   **JavaScript Dosya Analizi:**
    *   FFUF ile bulunan `.js` dosyalarını listeler ve içeriklerini web arayüzünde görüntüleme imkanı sunar.
    *   [SubDomainizer](https://github.com/nsonaniya2010/SubDomainizer) entegrasyonu ile JavaScript dosyalarından ve web sayfalarından alt alan adları, cloudflare URL'leri ve potansiyel gizli bilgileri (API anahtarları, vb.) ayrıştırır.
*   **Thread Destekli Tarama:** Bilgi toplama araçları eş zamanlı çalışarak tarama süresini optimize eder.
*   **Web Arayüzü:** Flask tabanlı, modern ve kullanıcı dostu bir arayüz ile tarama sonuçlarını (subdomain listesi, fuzz edilen endpointler, toplanan .js dosyaları) görselleştirir.
*   **AI Destekli Analiz:** Gemini API entegrasyonu ile toplanan veriler üzerinden potansiyel zafiyetler hakkında fikir alışverişi yapma ve öneriler alma imkanı sunar. (`.env` dosyasında `GEMINI_API_KEY` tanımlanmalıdır.)
*   **Sonuç İndirme:** Elde edilen tüm çıktıların (Sublist3r, SubDomainizer, FFUF, JS dosya listesi) web arayüzünden ayrı ayrı veya toplu olarak `.zip` formatında indirilmesini sağlar.

## Kurulum

Python 3.9 veya üzeri bir sürüm gereklidir.

1.  **Repoyu Klonlayın:**
    ```bash
    git clone https://github.com/1Xnes/Renaissance-recon.git
    cd Renaissance-recon
    ```

2.  **Bağımlılıkları Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Araçların Kurulumu ve Ayarlanması:**
    *   **FFUF:** Sisteminizde [FFUF](https://github.com/ffuf/ffuf) aracının kurulu ve `PATH` üzerinde olduğundan emin olun. Kurulum talimatları için FFUF reposunu ziyaret edebilirsiniz.
    *   **Sublist3r ve SubDomainizer:** Bu araçlar proje içerisinde `tools/` dizini altında bulunmaktadır. `requirements.txt` dosyası bu araçların Python bağımlılıklarını da içermektedir.

4.  **(Opsiyonel) Gemini API Anahtarı:**
    Eğer AI Chat özelliğini kullanmak istiyorsanız, proje ana dizininde `.env` adında bir dosya oluşturun ve içerisine Gemini API anahtarınızı aşağıdaki formatta ekleyin:
    ```env
    GEMINI_API_KEY='YOUR_API_KEY_HERE'
    ```

## Docker ile Çalıştırma (Opsiyonel)

Projeyi Docker kullanarak da çalıştırabilirsiniz. Bu, bağımlılıkların ve araçların kurulumuyla uğraşmanızı engeller.

1.  **Docker Image'ını Oluşturun:**
    Proje ana dizinindeyken aşağıdaki komutu çalıştırın:
    ```bash
    docker build -t renaissance-recon .
    ```

2.  **Docker Container'ını Başlatın:**
    ```bash
    docker run -p 5000:5000 -v ${PWD}/output:/app/output renaissance-recon
    ```
    *   **Not (Windows PowerShell kullanıcıları için):** Eğer yukarıdaki komut `-v` parametresiyle ilgili "invalid reference format" hatası verirse, `$(pwd)` yerine `${PWD}` kullanmayı deneyin. Alternatif olarak, `"%cd%/output:/app/output"` şeklinde de kullanabilirsiniz veya `C:\path\to\your\Renaissance-recon\output` gibi tam yolu belirtebilirsiniz.
    *   `-p 5000:5000`: Container içerisindeki 5000 portunu host makinenizdeki 5000 portuna yönlendirir.
    *   Eğer Gemini API anahtarını kullanmak istiyorsanız, `.env` dosyanızı container'a dahil etmeniz veya environment variable olarak eklemeniz gerekir:
        ```bash
        docker run -p 5000:5000 -v ${PWD}/output:/app/output --env-file .env renaissance-recon
        ```
        Veya spesifik olarak:
        ```bash
        docker run -p 5000:5000 -v ${PWD}/output:/app/output -e GEMINI_API_KEY='YOUR_API_KEY_HERE' renaissance-recon
        ```

3.  **Web Arayüzüne Erişin:**
    Container başlatıldıktan sonra web tarayıcınızda `http://127.0.0.1:5000` adresine gidin.

## Kullanım

1.  **Uygulamayı Başlatın:**
    Proje ana dizinindeyken aşağıdaki komutu çalıştırın:
    ```bash
    python app.py
    ```

2.  **Web Arayüzüne Erişin:**
    Uygulama başlatıldıktan sonra web tarayıcınızda `http://127.0.0.1:5000` adresine gidin.

3.  **Tarama Başlatma:**
    *   "Hedef Domain/URL" alanına taramak istediğiniz domaini (örn: `example.com`) veya URL'yi (örn: `https://example.com`) girin.
    *   Çalıştırmak istediğiniz araçları (Sublist3r, SubDomainizer, FFUF) seçin.
    *   FFUF için opsiyonel olarak özel bir kelime listesi (`wordlist`) yolu belirtebilirsiniz. Boş bırakılırsa `wordlists/common_small.txt` kullanılır.
    *   "Taramayı Başlat" butonuna tıklayın.

4.  **Sonuçları Görüntüleme:**
    Tarama tamamlandıktan sonra veya devam ederken sonuçlar web arayüzünde ilgili sekmelerde (Sublist3r, SubDomainizer, FFUF, FFUF ile Bulunan JS Dosyaları) görüntülenecektir.
    *   Her bir aracın ham çıktısını ve ayrıştırılmış/önemli sonuçlarını görebilirsiniz.
    *   FFUF ile bulunan JS dosyalarının listesini ve üzerine tıklayarak içeriklerini inceleyebilirsiniz.
    *   Sonuçları ayrı ayrı veya tümünü bir `.zip` dosyası olarak indirebilirsiniz.
    *   Eğer Gemini API anahtarı tanımlıysa, "AI ile Tartış" butonu ile sonuçları AI'a gönderip analiz ve öneriler alabilirsiniz.

### Test Edilebilecek Örnek Hedefler:
* `testphp.vulnweb.com`
* `github.com`
* `google.com`
* `ffuf.io` (FFUF testleri için)


## Ekran Görüntüleri

*(Buraya web arayüzünün ana sayfasının, sonuçlar sayfasının ve AI chat sayfasının ekran görüntüleri eklenecek)*

*   **Ana Sayfa (Tarama Başlatma):**
    `[SCREENSHOT_MAIN_PAGE_HERE]`

*   **Sonuçlar Sayfası (Örnek Bir Tarama):**
    `[SCREENSHOT_RESULTS_PAGE_HERE]`

*   **FFUF ile Bulunan JS Dosyaları Bölümü:**
    `[SCREENSHOT_JS_FILES_SECTION_HERE]`

*   **JS İçerik Görüntüleme Modalı:**
    `[SCREENSHOT_JS_MODAL_HERE]`

*   **AI Chat Sayfası:**
    `[SCREENSHOT_AI_CHAT_PAGE_HERE]`

*   **Örnek Terminal Çıktısı (Uygulama Başlatma ve Tarama Akışı):**
    ```
    (venv) $ python app.py
     * Serving Flask app 'app'
     * Debug mode: on
    WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
     * Running on http://127.0.0.1:5000
    Press CTRL+C to quit
     * Restarting with stat
     * Debugger is active!
     * Debugger PIN: XXX-XXX-XXX
    [12:34:56] arama1_testphpvulnwebcom - sublist3r: Başlatılıyor...
    [12:34:56] arama1_testphpvulnwebcom - ffuf: Başlatılıyor...
    [12:34:56] arama1_testphpvulnwebcom - subdomainizer: Başlatılıyor...
    [12:34:57] arama1_testphpvulnwebcom - sublist3r: Çalışıyor...
    [12:34:57] arama1_testphpvulnwebcom - subdomainizer: Çalışıyor...
    [12:34:58] arama1_testphpvulnwebcom - ffuf: Çalışıyor...
    ... (tarama çıktıları) ...
    [12:35:10] arama1_testphpvulnwebcom - sublist3r: Tamamlandı
    [12:35:15] arama1_testphpvulnwebcom - subdomainizer: Tamamlandı
    [12:36:00] arama1_testphpvulnwebcom - ffuf: Tamamlandı
    ```

## Katkıda Bulunma

Katkılarınız ve önerileriniz her zaman açığız! Lütfen bir issue açın veya pull request gönderin.

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.

## Kaynakça ve Teşekkürler

Bu araç geliştirilirken aşağıdaki açık kaynaklı projelere ve kütüphanelere başvurulmuş ve/veya entegre edilmiştir:

*   **[Sublist3r](https://github.com/aboul3la/Sublist3r):** Alt alan adı keşfi için kullanılan mükemmel bir araç. Geliştiricilerine teşekkürler.
*   **[SubDomainizer](https://github.com/nsonaniya2010/SubDomainizer):** JavaScript dosyalarından ve web kaynaklarından bilgi çıkarmada etkili bir araç. Geliştiricilerine teşekkürler.
*   **[FFUF (Fuzz Faster U Fool)](https://github.com/ffuf/ffuf):** Web fuzzing için hızlı ve esnek bir araç. Geliştiricilerine teşekkürler.
*   **[Flask](https://flask.palletsprojects.com/):** Web arayüzünün geliştirilmesinde kullanılan Python web framework'ü.
*   **[Tailwind CSS](https://tailwindcss.com/):** Modern ve hızlı UI geliştirme için kullanılan CSS framework'ü.
*   **[Font Awesome](https://fontawesome.com/):** İkonlar için.
*   **[Requests](https://requests.readthedocs.io/):** HTTP istekleri için.
*   **[Python-dotenv](https://github.com/theskumar/python-dotenv):** Ortam değişkenlerini yönetmek için.
*   **[Google Gemini API](https://ai.google.dev/):** AI destekli analiz ve chat özelliği için.
*   **[JSZip](https://stuk.github.io/jszip/):** Sonuçları zipleyerek indirme özelliği için.
*   **[Marked](https://marked.js.org/):** AI Chat arayüzünde Markdown metinlerini HTML'e dönüştürmek için.


Bu araç, sızma testi ve güvenlik araştırmaları sırasında bilgi toplama süreçlerini otomatize etmek ve kolaylaştırmak amacıyla geliştirilmiştir. Lütfen aracı yasal ve etik kurallar çerçevesinde kullanın.
