from flask import Flask, render_template, request, redirect, url_for
import os
# recon_wrappers.py dosyasından run_ffuf fonksiyonunu import et
from recon_wrappers import run_ffuf

# Uygulama ve çıktı dizini yapılandırması
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"Output directory created at: {OUTPUT_DIR}")

# Basit bir wordlist yolu (kendi sisteminize veya projenize göre ayarlayın)
# Örnek: Proje içinde bir wordlist klasörü oluşturup oradan çekebilirsiniz.
# WORDLIST_PATH = "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt" 
# Geçici olarak recon_wrappers.py'deki örnek wordlist'i kullanalım:
WORDLIST_PATH = os.path.join(BASE_DIR, "wordlists", "common_small.txt")
# Bu wordlist'in recon_wrappers.py'deki test bloğu tarafından oluşturulduğundan emin olun
# veya manuel olarak oluşturun.
if not os.path.exists(WORDLIST_PATH):
    os.makedirs(os.path.join(BASE_DIR, "wordlists"), exist_ok=True)
    try:
        with open(WORDLIST_PATH, "w") as f:
            f.write("admin\nlogin\nindex.html\nREADME.md\nconfig\n.git\napi\nuploads\nstatic\njs\ncss\n")
        print(f"Örnek wordlist oluşturuldu: {WORDLIST_PATH}")
    except Exception as e:
        print(f"Örnek wordlist oluşturulamadı: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    scan_results = {
        "ffuf": None,
        "sublist3r": None, # Diğer araçlar için yer tutucular
        "subdomainizer": None
    }
    message = None
    error = None
    target_domain_input = request.form.get('target_domain', '') if request.method == 'POST' else ''

    if request.method == 'POST':
        if not target_domain_input:
            error = "Lütfen bir hedef domain girin."
        else:
            print(f"Hedef domain alındı: {target_domain_input}")
            
            # ffuf için hedef URL'yi oluştur
            # Kullanıcı http/https girmezse varsayılan olarak http ekleyelim
            if not target_domain_input.startswith(('http://', 'https://')):
                ffuf_target_url = f"http://{target_domain_input}/FUZZ"
            else:
                # Eğer kullanıcı URL'nin sonuna /FUZZ eklemediyse biz ekleyelim
                if not target_domain_input.endswith("/FUZZ"):
                     # Önce varsa en sondaki / işaretini kaldıralım, sonra /FUZZ ekleyelim
                    ffuf_target_url = target_domain_input.rstrip('/') + "/FUZZ"
                else:
                    ffuf_target_url = target_domain_input

            print(f"ffuf için hedef URL: {ffuf_target_url}")
            print(f"Kullanılacak wordlist: {WORDLIST_PATH}")

            if not os.path.exists(WORDLIST_PATH):
                error = f"Wordlist bulunamadı: {WORDLIST_PATH}. Lütfen geçerli bir yol belirtin."
            else:
                # ffuf taramasını başlat
                # UYARI: Bu senkron bir çağrıdır ve uzun sürebilir, web isteğini bloklar.
                # Bir sonraki adımda bunu thread ile asenkron yapacağız.
                ffuf_result_data = run_ffuf(ffuf_target_url, WORDLIST_PATH, output_format="json", extensions=[".html", ".php", ".txt"])
                
                if ffuf_result_data["error"]:
                    error = f"ffuf Taramasında Hata: {ffuf_result_data['error']}"
                elif not ffuf_result_data["results"]:
                     message = f"ffuf taraması tamamlandı. {target_domain_input} için belirtilen wordlist ile eşleşen yol bulunamadı."
                else:
                    message = f"ffuf taraması {target_domain_input} için tamamlandı."
                
                scan_results["ffuf"] = ffuf_result_data["results"]
                
            # TODO: Diğer tarama araçları (Sublist3r, SubDomainizer) burada çağrılacak
            
    return render_template('index.html', 
                           scan_initiated=(request.method == 'POST' and target_domain_input), 
                           target_domain=target_domain_input,
                           message=message,
                           error=error,
                           scan_results=scan_results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)