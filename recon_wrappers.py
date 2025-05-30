import subprocess
import os

# Araçların yolları (Bu dosyanın bulunduğu dizine göre)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')

SUBLIST3R_PATH = os.path.join(TOOLS_DIR, 'Sublist3r', 'sublist3r.py')
SUBDOMAINIZER_PATH = os.path.join(TOOLS_DIR, 'SubDomainizer', 'SubDomainizer.py')
FFUF_PATH = 'ffuf' # Sistemde kurulu olduğunu varsayıyoruz. Değilse tam yolunu yazın.

# Python yorumlayıcısı için komut
PYTHON_CMD = 'python' # 'python3' yerine 'python' kullanıyoruz.


def run_command(command_list, output_file_for_stdout):
    """
    Verilen komutu (liste olarak) çalıştırır ve stdout'unu belirtilen dosyaya yazar.
    stdout ve stderr stringlerini döndürür.
    """
    try:
        print(f"Komut çalıştırılıyor: {' '.join(command_list)}")
        process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            # stderr'de zaten hata mesajı olacağı için burada stdout'u da eklemek bilgi tekrarı olabilir.
            # Ancak bazen stdout'ta da ek bilgi olabilir.
            error_message = f"Komut hatası (return code {process.returncode}). Stderr aşağıda ayrıca gösterilecektir."
            print(error_message) # Sadece konsola kısa bir bilgi
        
        if output_file_for_stdout: 
            with open(output_file_for_stdout, 'w', encoding='utf-8') as f:
                f.write(stdout if stdout else "")
        
        if stderr: # stderr'i her zaman konsola yazdır (hata ayıklama için)
            print(f"STDERR RAW:\n{stderr}")

        return stdout, stderr

    except FileNotFoundError:
        error_msg = f"HATA: Komut bulunamadı - {command_list[0]}. Lütfen aracın kurulu ve PATH'de olduğundan emin olun veya '{PYTHON_CMD}' komutunun geçerli olduğundan emin olun."
        print(error_msg)
        if output_file_for_stdout:
            with open(output_file_for_stdout, 'w', encoding='utf-8') as f:
                f.write(f"Hata: Araç bulunamadı - {command_list[0]}\n{error_msg}")
        return "", error_msg # stdout boş, stderr dolu (hata mesajı ile)
    except Exception as e:
        error_msg = f"Komut çalıştırılırken genel bir hata oluştu ({' '.join(command_list)}): {e}"
        print(error_msg)
        if output_file_for_stdout:
             with open(output_file_for_stdout, 'w', encoding='utf-8') as f:
                f.write(f"Hata: Komut çalıştırılamadı.\n{error_msg}")
        return "", error_msg # stdout boş, stderr dolu (hata mesajı ile)

def run_sublist3r(target_domain, output_file):
    # Sublist3r -d domain_adı şeklinde çalışır. URL değil.
    # Python'ı tamponsuz modda çalıştırmak için '-u' parametresini ekliyoruz.
    # Bu, stdout'un boru üzerinden daha güvenilir bir şekilde yakalanmasına yardımcı olabilir.
    command = [PYTHON_CMD, '-u', SUBLIST3R_PATH, '-d', target_domain]
    return run_command(command, output_file)

def run_subdomainizer(target_url, output_file):
    command = [PYTHON_CMD, '-u', SUBDOMAINIZER_PATH, '-u', target_url] # SubDomainizer için de -u ekleyebiliriz.
    return run_command(command, output_file)

def run_ffuf(target_url_with_fuzz, wordlist_path, output_json_file):
    command = [
        FFUF_PATH,
        '-u', target_url_with_fuzz,
        '-w', wordlist_path,
        '-o', output_json_file, 
        '-of', 'json',
        '-c', 
        '-mc', '200,204,301,302,307,401,403,405,500'
    ]
    # FFUF kendi çıktısını yönettiği için run_command'in stdout yazma özelliğine ihtiyacımız yok.
    # Bu yüzden output_file_for_stdout=None gönderiyoruz.
    stdout_console, stderr = run_command(command, None) 
    return stdout_console, stderr
