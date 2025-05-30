from flask import Flask, render_template, request, redirect, url_for
import os
import subprocess
import re 
from recon_wrappers import run_sublist3r, run_subdomainizer, run_ffuf

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'output'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

BASE_DIR_APP = os.path.dirname(os.path.abspath(__file__))
WORDLISTS_DIR = os.path.join(BASE_DIR_APP, 'wordlists')


def sanitize_domain_for_filename(domain_url):
    name = re.sub(r'^https?://', '', domain_url)
    name = re.sub(r'[/:*?"<>|]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name

def parse_subdomainizer_output(output_content):
    subdomains = []
    cloud_urls = []
    secrets = []
    try:
        subdomain_match = re.search(r"Got some subdomains\.\.\.\s*Total Subdomains: \d+\s*(.*?)\s*____", output_content, re.DOTALL)
        if subdomain_match:
            subdomains = [line.strip() for line in subdomain_match.group(1).strip().split('\n') if line.strip()]

        cloud_url_match = re.search(r"Some cloud services urls are found\.\.\.\s*Total Cloud URLs: \d+\s*(.*?)\s*____", output_content, re.DOTALL)
        if cloud_url_match:
            cloud_urls = [line.strip() for line in cloud_url_match.group(1).strip().split('\n') if line.strip()]

        secret_match = re.search(r"Found some secrets\(might be false positive\)\.\.\.\s*Total Possible Secrets: \d+\s*(.*?)\s*____", output_content, re.DOTALL)
        if secret_match:
            secrets = [line.strip() for line in secret_match.group(1).strip().split('\n') if line.strip()]
    except Exception as e:
        print(f"SubDomainizer çıktısı ayrıştırılırken hata: {e}")
    return subdomains, cloud_urls, secrets


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        target_domain_input = request.form.get('domain')
        run_sublist3r_flag = request.form.get('run_sublist3r')
        run_subdomainizer_flag = request.form.get('run_subdomainizer')
        run_ffuf_flag = request.form.get('run_ffuf')
        user_wordlist_path = request.form.get('wordlist')

        if not target_domain_input:
            return render_template('index.html', error="Hedef domain boş olamaz!")

        sanitized_domain_name = sanitize_domain_for_filename(target_domain_input)

        # Çıktı ve stderr dosyası isimleri
        sublist3r_output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_sublist3r_stdout.txt")
        sublist3r_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_sublist3r_stderr.txt")
        
        subdomainizer_output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_subdomainizer_stdout.txt")
        subdomainizer_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_subdomainizer_stderr.txt")
        
        # FFUF kendi JSON çıktısını yönetir, biz sadece konsol stdout/stderr'ini yakalayabiliriz (opsiyonel)
        ffuf_json_output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_ffuf.json")
        ffuf_console_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{sanitized_domain_name}_ffuf_stderr.txt")


        results_flags = {
            'sublist3r_run': False,
            'subdomainizer_run': False,
            'ffuf_run': False
        }
        
        current_ffuf_wordlist = None
        if run_ffuf_flag:
            if user_wordlist_path and user_wordlist_path.strip():
                if not os.path.isabs(user_wordlist_path):
                    current_ffuf_wordlist = os.path.join(BASE_DIR_APP, user_wordlist_path)
                else:
                    current_ffuf_wordlist = user_wordlist_path
                if not os.path.exists(current_ffuf_wordlist):
                    return render_template('index.html', error=f"Belirtilen FFUF kelime listesi bulunamadı: {current_ffuf_wordlist}")
            else:
                current_ffuf_wordlist = os.path.join(WORDLISTS_DIR, 'common_small.txt')
                if not os.path.exists(current_ffuf_wordlist):
                     return render_template('index.html', error=f"Varsayılan FFUF kelime listesi bulunamadı: {current_ffuf_wordlist}")

        if run_sublist3r_flag:
            print(f"Sublist3r çalıştırılıyor: {target_domain_input}")
            clean_target_for_sublist3r = target_domain_input.replace("https://", "").replace("http://", "").split('/')[0]
            stdout, stderr = run_sublist3r(clean_target_for_sublist3r, sublist3r_output_file) # stdout dosyaya yazılır
            with open(sublist3r_stderr_file, 'w', encoding='utf-8') as f_err:
                f_err.write(stderr if stderr else "")
            results_flags['sublist3r_run'] = True
            print(f"Sublist3r tamamlandı. Stdout: {sublist3r_output_file}, Stderr: {sublist3r_stderr_file}")

        if run_subdomainizer_flag:
            print(f"SubDomainizer çalıştırılıyor: {target_domain_input}")
            target_url_for_subdomainizer = target_domain_input
            if not target_domain_input.startswith(('http://', 'https://')):
                target_url_for_subdomainizer = f"https://{target_domain_input}"
            stdout, stderr = run_subdomainizer(target_url_for_subdomainizer, subdomainizer_output_file) # stdout dosyaya yazılır
            with open(subdomainizer_stderr_file, 'w', encoding='utf-8') as f_err:
                f_err.write(stderr if stderr else "")
            results_flags['subdomainizer_run'] = True
            print(f"SubDomainizer tamamlandı. Stdout: {subdomainizer_output_file}, Stderr: {subdomainizer_stderr_file}")

        if run_ffuf_flag and current_ffuf_wordlist:
            print(f"FFUF çalıştırılıyor: {target_domain_input} kelime listesi: {current_ffuf_wordlist}")
            target_url_for_ffuf = target_domain_input
            if not target_domain_input.startswith(('http://', 'https://')):
                 target_url_for_ffuf = f"https://{target_domain_input}"
            if not target_url_for_ffuf.endswith('/'):
                target_url_for_ffuf += '/'
            
            # FFUF kendi JSON çıktısını ffuf_json_output_file'a yazar.
            # run_ffuf, FFUF'un konsol stdout ve stderr'ini döndürür.
            ffuf_console_stdout, ffuf_console_stderr = run_ffuf(f"{target_url_for_ffuf}FUZZ", current_ffuf_wordlist, ffuf_json_output_file)
            with open(ffuf_console_stderr_file, 'w', encoding='utf-8') as f_err:
                 f_err.write(ffuf_console_stderr if ffuf_console_stderr else "")
            # ffuf_console_stdout'u da isterseniz bir dosyaya yazabilirsiniz.
            results_flags['ffuf_run'] = True
            print(f"FFUF tamamlandı. JSON Çıktı: {ffuf_json_output_file}, Konsol Stderr: {ffuf_console_stderr_file}")
        
        return redirect(url_for('show_results', 
                                display_domain_key=sanitized_domain_name, 
                                original_target=target_domain_input,
                                sublist3r_run=results_flags['sublist3r_run'],
                                subdomainizer_run=results_flags['subdomainizer_run'],
                                ffuf_run=results_flags['ffuf_run']
                                ))

    return render_template('index.html')

@app.route('/results/<display_domain_key>')
def show_results(display_domain_key):
    original_target = request.args.get('original_target', display_domain_key)
    sublist3r_run = request.args.get('sublist3r_run', 'False') == 'True'
    subdomainizer_run = request.args.get('subdomainizer_run', 'False') == 'True'
    ffuf_run = request.args.get('ffuf_run', 'False') == 'True'

    # Stdout içerikleri
    sublist3r_stdout_content = None
    subdomainizer_stdout_content = None # Bu artık parse edilecek
    ffuf_json_content = None
    
    # Stderr içerikleri
    sublist3r_stderr_content = None
    subdomainizer_stderr_content = None
    ffuf_console_stderr_content = None # FFUF'un konsol stderr'i

    # Ayrıştırılmış SubDomainizer sonuçları
    subdomainizer_subdomains = None
    subdomainizer_cloud_urls = None
    subdomainizer_secrets = None

    # Genel dosya okuma hataları
    file_read_error = {}

    def read_file_content(file_path, error_key):
        content = None
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                file_read_error[error_key] = f"{os.path.basename(file_path)} okunamadı: {e}"
        else:
            file_read_error[error_key] = f"{os.path.basename(file_path)} bulunamadı."
        return content

    if sublist3r_run:
        sublist3r_stdout_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_sublist3r_stdout.txt")
        sublist3r_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_sublist3r_stderr.txt")
        sublist3r_stdout_content = read_file_content(sublist3r_stdout_file, 'sublist3r_stdout')
        sublist3r_stderr_content = read_file_content(sublist3r_stderr_file, 'sublist3r_stderr')

    if subdomainizer_run:
        subdomainizer_stdout_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_subdomainizer_stdout.txt")
        subdomainizer_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_subdomainizer_stderr.txt")
        
        raw_subdomainizer_stdout = read_file_content(subdomainizer_stdout_file, 'subdomainizer_stdout')
        if raw_subdomainizer_stdout:
            subdomainizer_subdomains, subdomainizer_cloud_urls, subdomainizer_secrets = parse_subdomainizer_output(raw_subdomainizer_stdout)
        
        subdomainizer_stderr_content = read_file_content(subdomainizer_stderr_file, 'subdomainizer_stderr')
            
    if ffuf_run:
        ffuf_json_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_ffuf.json")
        ffuf_console_stderr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{display_domain_key}_ffuf_stderr.txt")
        ffuf_json_content = read_file_content(ffuf_json_file, 'ffuf_json')
        ffuf_console_stderr_content = read_file_content(ffuf_console_stderr_file, 'ffuf_stderr')

    return render_template('results_display.html', 
                           domain_title=original_target,
                           display_domain_key=display_domain_key,
                           
                           sublist3r_stdout_content=sublist3r_stdout_content,
                           sublist3r_stderr_content=sublist3r_stderr_content,
                           
                           # Ayrıştırılmış SubDomainizer sonuçları
                           subdomainizer_subdomains=subdomainizer_subdomains,
                           subdomainizer_cloud_urls=subdomainizer_cloud_urls,
                           subdomainizer_secrets=subdomainizer_secrets,
                           # SubDomainizer'ın ham stdout'unu artık doğrudan göstermiyoruz, parse ediyoruz.
                           # Eğer ham çıktıyı da göstermek isterseniz, onu da template'e yollayabilirsiniz.
                           subdomainizer_stderr_content=subdomainizer_stderr_content,
                           
                           ffuf_json_content=ffuf_json_content,
                           ffuf_console_stderr_content=ffuf_console_stderr_content,
                           
                           file_read_errors=file_read_error, # Dosya okuma hatalarını toplu gönder
                           
                           sublist3r_run=sublist3r_run,
                           subdomainizer_run=subdomainizer_run,
                           ffuf_run=ffuf_run
                           )

if __name__ == '__main__':
    app.run(debug=True)
