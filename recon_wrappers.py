import subprocess
import os
import re # Regex kütüphanesini import ediyoruz

# OUTPUT_DIR app.py'den veya global bir config'den alınabilir, şimdilik burada tanımlıyoruz.
# Veya app.py'de tanımlanıp buraya parametre olarak geçirilebilir.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Çıktı dizininin var olduğundan emin ol (recon_wrappers.py doğrudan çalıştırılırsa diye)
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def run_ffuf(target_url, wordlist_path, extensions=None, output_format="json"):
    """
    Belirtilen URL üzerinde ffuf ile dizin/dosya taraması yapar.

    Args:
        target_url (str): Tam hedef URL (örn: "http://example.com/FUZZ" veya "https://sub.example.com/FUZZ").
                          'FUZZ' keyword'ü wordlist'teki her kelimeyle değiştirilecektir.
        wordlist_path (str): Kullanılacak wordlist dosyasının yolu.
        extensions (list, optional): Denenecek dosya uzantıları (örn: [".php", ".html", ".js"]).
                                     ffuf'ta -e flag'i ile kullanılır.
        output_format (str, optional): ffuf çıktı formatı. "json" önerilir.

    Returns:
        list: Bulunan geçerli URL'lerin listesi. Hata durumunda boş liste döner.
    """
    if not target_url.endswith("/FUZZ"):
        print("[UYARI] ffuf için hedef URL'nin '/FUZZ' ile bitmesi önerilir. (örn: http://site.com/FUZZ)")
        # Otomatik olarak ekleyebiliriz ya da kullanıcıya bırakabiliriz. Şimdilik devam edelim.

    if not os.path.exists(wordlist_path):
        print(f"[HATA] Wordlist bulunamadı: {wordlist_path}")
        return {"error": "Wordlist bulunamadı.", "results": []}

    # ffuf için komut listesi oluştur
    # Örnek: ffuf -w /path/to/wordlist.txt -u http://example.com/FUZZ -o output.json -of json -e .php,.html
    command = [
        "ffuf",
        "-w", wordlist_path,
        "-u", target_url,
        "-mc", "200,204,301,302,307,401,403" # Sadece belirli HTTP status kodlarını göster
    ]

    if extensions:
        ext_string = ",".join(extensions)
        command.extend(["-e", ext_string])

    # Çıktı dosyasının adını hedef domainden ve araçtan türetelim
    # target_url'den domain adını çıkarmak için basit bir regex veya urlparse kullanılabilir.
    # Şimdilik basit bir adlandırma yapalım:
    domain_part = target_url.split("//")[-1].split("/")[0].replace(":", "_") # http://example.com:8080 -> example.com_8080
    output_file_base = os.path.join(OUTPUT_DIR, f"{domain_part}_ffuf")

    if output_format == "json":
        output_file_path = f"{output_file_base}.json"
        command.extend(["-o", output_file_path, "-of", "json"])
    elif output_format == "csv":
        output_file_path = f"{output_file_base}.csv"
        command.extend(["-o", output_file_path, "-of", "csv"])
    # Diğer formatlar eklenebilir (html, md, ecsv)
    else: # Varsayılan olarak text (eğer -o belirtilmezse stdout'a basar)
        output_file_path = f"{output_file_base}.txt" # Kendimiz bir text dosyasına yönlendirebiliriz
        # ffuf -o olmadan stdout'a yazar, biz bunu yakalayacağız.

    print(f"[INFO] ffuf komutu çalıştırılıyor: {' '.join(command)}")

    found_paths = []
    error_message = None

    try:
        # ffuf -silent flag'i progress bar'ı gizler, daha temiz çıktı için eklenebilir.
        # command.insert(1, "-silent") # Örneğin ffuf -silent -w ...
        process = subprocess.run(command, capture_output=True, text=True, timeout=300) # 5 dakika timeout

        if process.returncode == 0 or process.returncode == 1: # ffuf bazen sonuç bulamayınca 1 dönebilir
            print(f"[SUCCESS] ffuf taraması tamamlandı: {target_url}")
            if output_format == "json" and os.path.exists(output_file_path):
                import json
                with open(output_file_path, 'r') as f:
                    data = json.load(f)
                # ffuf json formatında 'results' altında bir liste tutar
                for result in data.get("results", []):
                    # result objesi: {"input": {"FUZZ":"admin"}, "position":0, "status":200, "length":1234, "words":50, "lines":100, "url":"http://example.com/admin", "redirectlocation":"", "host":"example.com"}
                    found_paths.append({
                        "url": result.get("url"),
                        "status": result.get("status"),
                        "length": result.get("length")
                    })
            elif output_format != "json": # Eğer json değilse ve dosya oluşturulduysa (veya stdout'tan okuma)
                # Bu kısmı text çıktı parse etmek için geliştirmek gerekebilir.
                # Şimdilik sadece stdout'u (eğer dosya belirtilmediyse) veya stderr'yi kontrol edelim.
                # ffuf genellikle sonuçları stdout'a basar.
                # Örnek bir ffuf text çıktısı:
                # admin [Status: 200, Size: 1234, Words: 50, Lines: 100]
                # .htaccess [Status: 403, Size: 200, Words: 10, Lines: 5]
                for line in process.stdout.splitlines():
                    # Sadece anlamlı satırları alalım (örn: progress bar satırlarını atlayalım)
                    # Bu regex çok basit, ffuf'un farklı versiyonlarına göre ayarlanması gerekebilir.
                    # Daha güvenilir olan JSON çıktısıdır.
                    match = re.search(r'^(.+?)\s+\[Status: (\d+), Size: (\d+),.+]', line)
                    if match:
                        path = match.group(1).strip()
                        status = int(match.group(2))
                        size = int(match.group(3))
                        # Base URL'i oluşturmak için biraz daha mantık gerekebilir.
                        # Şimdilik sadece path'i alalım.
                        # target_url'deki FUZZ'ı path ile değiştirerek tam url oluşturulabilir.
                        full_url = target_url.replace("FUZZ", path)
                        found_paths.append({"url": full_url, "status": status, "length": size})
                if not found_paths:
                     print("[INFO] ffuf stdout'tan parse edilecek bir sonuç bulunamadı veya format beklenenden farklı.")
                if process.stderr:
                    print(f"[INFO] ffuf stderr: {process.stderr.strip()}")


            if os.path.exists(output_file_path):
                 print(f"[INFO] ffuf çıktısı şuraya kaydedildi: {output_file_path}")

        else:
            error_message = f"ffuf hata ile sonlandı. Return code: {process.returncode}"
            print(f"[ERROR] {error_message}")
            if process.stderr:
                print(f"[ERROR] ffuf stderr: {process.stderr.strip()}")
                error_message += f" stderr: {process.stderr.strip()}"
            if process.stdout: # Bazen hata olsa da stdout'ta bilgi olabilir
                 print(f"[INFO] ffuf stdout (hata durumunda): {process.stdout.strip()}")


    except FileNotFoundError:
        error_message = "ffuf komutu bulunamadı. Sistemde kurulu ve PATH üzerinde olduğundan emin olun."
        print(f"[HATA] {error_message}")
    except subprocess.TimeoutExpired:
        error_message = "ffuf taraması zaman aşımına uğradı."
        print(f"[HATA] {error_message}")
    except Exception as e:
        error_message = f"ffuf çalıştırılırken bir hata oluştu: {e}"
        print(f"[HATA] {error_message}")

    return {"error": error_message, "results": found_paths}


if __name__ == '__main__':
    # Bu kısmı doğrudan çalıştırma ve test için kullanabilirsiniz
    # test_url = "http://testphp.vulnweb.com/FUZZ" # Test için genel bir site, izin alarak kullanın!
    # test_wordlist = "/usr/share/wordlists/dirb/common.txt" # Kendi wordlist yolunuzu belirtin
    # Linux'ta yaygın bir yol, sizde farklı olabilir. Windows'ta da bir wordlist yolu belirtin.
    
    # Örnek wordlist (proje içinde de olabilir):
    example_wordlist_path = os.path.join(BASE_DIR, "wordlists", "common_small.txt")
    os.makedirs(os.path.join(BASE_DIR, "wordlists"), exist_ok=True)
    with open(example_wordlist_path, "w") as f:
        f.write("admin\nlogin\nindex.html\nREADME.md\nconfig\n.git\n")

    # Güvenli ve bilinen bir test hedefi (eğer varsa)
    # Veya kendi lokal web sunucunuzda bir test yapısı oluşturun.
    # İnternetteki rastgele sitelerde test yapmaktan kaçının.
    # Docker ile bir test ortamı kurabilirsiniz, örn: bkimminich/juice-shop
    
    # Şimdilik test için bu satırları yorumda bırakalım veya kontrollü bir hedefle kullanalım.
    # results = run_ffuf(test_url, example_wordlist_path, extensions=[".php", ".txt"], output_format="json")
    # if results["error"]:
    #     print(f"Hata: {results['error']}")
    # else:
    #     print("\nBulunan Yollar:")
    #     for item in results["results"]:
    #         print(f"  URL: {item['url']}, Status: {item['status']}, Length: {item['length']}")
    print("run_ffuf fonksiyonu tanımlandı. Test için if __name__ == '__main__' bloğunu düzenleyin.")