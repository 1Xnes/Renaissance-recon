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


def run_command(command_list, output_file_for_stdout, print_output=False):
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
        
        if print_output and stderr: # stderr'i her zaman konsola yazdır (hata ayıklama için)
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
    # https:// veya http:// ile başlamamalı, sadece domain adı olmalı, ve baştaki www. da dahil edilmemeli kırpılmalı.
    if target_domain.startswith(('http://', 'https://')):
        target_domain = target_domain.split('//')[-1]
    if target_domain.startswith('www.'):
        target_domain = target_domain[4:]
    command = [PYTHON_CMD, '-u', SUBLIST3R_PATH, '-d', target_domain]
    return run_command(command, output_file, False)

def run_subdomainizer(target_url, output_file):
    command = [PYTHON_CMD, '-u', SUBDOMAINIZER_PATH, '-u', target_url] # SubDomainizer için de -u ekleyebiliriz.
    return run_command(command, output_file, False)

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
    stdout_console, stderr = run_command(command, None, False) 
    return stdout_console, stderr

# === Utility: Safe folder/file name ===

def sanitize_filename(name):
    """Sanitize a string so it can be safely used as a file or folder name."""
    name = name.replace("http://", "").replace("https://", "")
    name = name.replace("/", "_").replace(":", "_").replace("#", "_").replace("?", "_").replace("&", "_")
    # Keep only alnum, underscore and dash
    name = "".join(c for c in name if c.isalnum() or c in ("_", "-"))
    return name.strip()


# === CLI Helper ===

def _run_tool_cli(tool_name, target_url, scan_folder_path, wordlist_path, verbose=False):
    """Internal helper used by the CLI interface to call the correct wrapper."""
    if tool_name == "sublist3r":
        output_file = os.path.join(scan_folder_path, "sublist3r_stdout.txt")
        stdout, stderr = run_sublist3r(target_url, output_file)
        if verbose:
            print("--- Sublist3r stdout ---")
            print(stdout.strip() or "<boş>")
            if stderr:
                print("--- Sublist3r stderr ---")
                print(stderr.strip())
    elif tool_name == "subdomainizer":
        output_file = os.path.join(scan_folder_path, "subdomainizer_stdout.txt")
        stdout, stderr = run_subdomainizer(target_url, output_file)
        if verbose:
            print("--- SubDomainizer stdout ---")
            print(stdout.strip() or "<boş>")
            if stderr:
                print("--- SubDomainizer stderr ---")
                print(stderr.strip())
    elif tool_name == "ffuf":
        # Ensure the FFUF URL ends with FUZZ
        ffuf_target = target_url.rstrip("/") + "/FUZZ"
        output_json = os.path.join(scan_folder_path, "ffuf_results.json")
        stdout, stderr = run_ffuf(ffuf_target, wordlist_path, output_json)
        if verbose:
            print("--- FFUF console stdout ---")
            print(stdout.strip() or "<boş>")
            if stderr:
                print("--- FFUF console stderr ---")
                print(stderr.strip())
    else:
        print(f"[!] Bilinmeyen araç: {tool_name}. Atlanıyor.")

    if verbose:
        print(f"[+] {tool_name} tamamlandı!")


def main_cli():
    """Entry point for command-line usage."""
    import argparse, threading, time

    parser = argparse.ArgumentParser(
        prog="Renaissance-Recon CLI",
        description="Web enum araçlarını komut satırından çalıştırır."
    )
    parser.add_argument("-u", "--target", required=True, help="Hedef domain veya tam URL")
    parser.add_argument(
        "-t", "--tools", default="sublist3r,subdomainizer,ffuf",
        help="Virgül ile ayrılmış çalıştırılacak araç listesi (sublist3r, subdomainizer, ffuf)"
    )
    parser.add_argument(
        "-w", "--wordlist",
        default=os.path.join("wordlists", "common_small.txt"),
        help="FFUF için kelime listesi yolu (sadece ffuf seçildiyse kullanılır)"
    )
    parser.add_argument(
        "--sequential", action="store_true", help="Araçları ardışık sıra ile çalıştır (varsayılan eşzamanlı)"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Araçların çıktılarını konsola yazdır"
    )
    args = parser.parse_args()

    selected_tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    print(f"[+] Çalıştırılacak araçlar: {', '.join(selected_tools)}")

    # Klasör hazırlığı
    timestamp = int(time.time())
    safe_target = sanitize_filename(args.target)
    scan_folder_name = f"cli_{timestamp}_{safe_target}"
    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    scan_folder_path = os.path.join(output_base, scan_folder_name)
    os.makedirs(scan_folder_path, exist_ok=True)
    print(f"[+] Sonuçlar '{scan_folder_path}' dizinine kaydedilecek.")

    # Araçları çalıştır
    if args.sequential:
        for tool in selected_tools:
            _run_tool_cli(tool, args.target, scan_folder_path, args.wordlist, args.verbose)
    else:
        threads = []
        for tool in selected_tools:
            th = threading.Thread(target=_run_tool_cli, args=(tool, args.target, scan_folder_path, args.wordlist, args.verbose))
            th.start()
            threads.append(th)
        for th in threads:
            th.join()

    print("[+] Tarama tamamlandı!")
    print(f"[i] Rapor ve log dosyaları: {scan_folder_path}")


if __name__ == "__main__":
    main_cli()
