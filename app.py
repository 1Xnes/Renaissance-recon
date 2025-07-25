import os
import subprocess
import json
import threading
import time
import re # Import re for ANSI code stripping
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from urllib.parse import quote_plus, unquote_plus, urlparse
import requests # For fetching JS files
import google.generativeai as genai # For Gemini API
from dotenv import load_dotenv # To load .env file

load_dotenv() # Load environment variables from .env

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("UYARI: GEMINI_API_KEY .env dosyasında bulunamadı. AI Chat özelliği çalışmayabilir.")

# Ensure output directory exists
# Create 'output' directory if it doesn't exist to store scan results
if not os.path.exists('output'):
    os.makedirs('output')

# Ensure tools directory exists
# Create 'tools' directory if it doesn't exist (though tools are expected to be pre-populated)
if not os.path.exists('tools'):
    os.makedirs('tools')

# Ensure wordlists directory exists
# Create 'wordlists' directory if it doesn't exist (wordlists should be present)
if not os.path.exists('wordlists'):
    os.makedirs('wordlists')

# Global dictionary to store scan statuses
scan_statuses = {}

def strip_ansi_codes(text):
    """Removes ANSI escape codes from a string."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_tool_path(tool_name_with_subdir):
    # Helper function to get the absolute path to a tool's executable script.
    # tool_name_with_subdir should be like 'Sublist3r/sublist3r' or 'SubDomainizer/SubDomainizer'
    # It assumes the script has the same name as the last part of tool_name_with_subdir and a .py extension.
    script_name = os.path.basename(tool_name_with_subdir)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', tool_name_with_subdir + '.py')

def get_wordlist_path(wordlist_name):
    # Helper function to get the absolute path to a wordlist.
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wordlists', wordlist_name)

def update_scan_status(scan_folder, tool_name, status, message=""):
    """Update the status of a scan in the global dictionary"""
    if scan_folder not in scan_statuses:
        scan_statuses[scan_folder] = {}
    scan_statuses[scan_folder][tool_name] = {
        'status': status,
        'message': message,
        'last_update': datetime.now().strftime('%H:%M:%S')
    }
    # Print to terminal
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {scan_folder} - {tool_name}: {status} {message}")

def fetch_js_content(url):
    """Fetches the content of a JS file from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.text
    except requests.RequestException as e:
        return f"Error fetching {url}: {str(e)}"

def run_command(command, output_file_base_for_logs, tool_name, scan_folder):
    # Runs a command and captures its stdout and stderr, saving them to files.
    # command: The command to run (list of strings).
    # output_file_base_for_logs: The base name for stdout/stderr log files (e.g., "google.com_").
    # tool_name: The name of the tool being run (e.g., "sublist3r", "ffuf").

    stdout_path = f"output/{output_file_base_for_logs}{tool_name}_stdout.txt"
    stderr_path = f"output/{output_file_base_for_logs}{tool_name}_stderr.txt"
    
    # For ffuf, the JSON output path is determined by its own '-o' argument in the command.
    # This function primarily handles stdout/stderr logging.

    try:
        update_scan_status(scan_folder, tool_name, "Başlatılıyor...")
        
        # Execute the command
        # text=True ensures stdout/stderr are strings
        # cwd sets the current working directory for the subprocess, useful if tools expect to be run from their own directory
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', cwd=os.path.dirname(os.path.abspath(__file__)))
        
        update_scan_status(scan_folder, tool_name, "Çalışıyor...")
        
        # For FFUF, we don't use timeout
        if tool_name == 'ffuf':
            stdout, stderr = process.communicate()
        else:
            # For other tools, use 5-minute timeout
            stdout, stderr = process.communicate(timeout=300)

        # Write stdout to its log file
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write(stdout)
        # Write stderr to its log file
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(stderr)

        if process.returncode == 0:
            update_scan_status(scan_folder, tool_name, "Tamamlandı")
        else:
            update_scan_status(scan_folder, tool_name, "Hata", f"Return code: {process.returncode}")

    except subprocess.TimeoutExpired:
        # Handle command timeout
        error_message = f"Komut zaman aşımına uğradı (300 saniye)."
        update_scan_status(scan_folder, tool_name, "Zaman Aşımı", error_message)
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write(error_message)
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(error_message)
    except Exception as e:
        # Handle other exceptions during command execution
        error_message = f"Komut çalıştırılırken bir hata oluştu: {str(e)}"
        update_scan_status(scan_folder, tool_name, "Hata", error_message)
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write("") # No stdout if command failed early
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(error_message)

def run_scan_tool(tool_name, target_url, scan_folder, wordlist_path=None):
    """Run a specific tool in a separate thread"""
    if tool_name == 'sublist3r':
        sublist3r_py_path = get_tool_path('Sublist3r/sublist3r')
        parsed_url = urlparse(target_url)
        domain_for_sublist3r = parsed_url.netloc or parsed_url.path.split('/')[0]
        command = ['python', sublist3r_py_path, '-d', domain_for_sublist3r]
        run_command(command, os.path.join(scan_folder, "sublist3r_"), "sublist3r", scan_folder)
    
    elif tool_name == 'subdomainizer':
        subdomainizer_py_path = get_tool_path('SubDomainizer/SubDomainizer')
        command = ['python', subdomainizer_py_path, '-u', target_url]
        run_command(command, os.path.join(scan_folder, "subdomainizer_"), "subdomainizer", scan_folder)
    
    elif tool_name == 'ffuf':
        ffuf_target_url = target_url
        if not ffuf_target_url.endswith('/'):
            ffuf_target_url += '/'
        ffuf_target_url += 'FUZZ'
        
        ffuf_json_output_filename_base = scan_folder
        ffuf_output_json_path = os.path.join('output', scan_folder, f"{ffuf_json_output_filename_base}_ffuf.json")
        
        command = [
            'ffuf', '-u', ffuf_target_url, '-w', wordlist_path,
            '-o', ffuf_output_json_path, '-of', 'json',
            '-c',
            '-mc', '200,204,301,302,307,401,403,405,500'
        ]
        run_command(command, os.path.join(scan_folder, "ffuf_"), "ffuf", scan_folder)

def sanitize_filename(name):
    # Replaces characters that are problematic in filenames.
    # This is crucial for creating safe filenames from user input (targets/URLs).
    name = name.replace("http://", "")
    name = name.replace("https://", "")
    name = name.replace("/", "_").replace(":", "_").replace("#", "_").replace("?", "_").replace("&", "_")
    # Remove or replace other potentially problematic characters as needed
    name = "".join(c for c in name if c.isalnum() or c in ('_', '-')).strip()
    return name

@app.route('/', methods=['GET', 'POST'])
def index():
    # Main page route: handles form submission for starting a scan.
    recent_scans = []
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    scan_log_file = os.path.join(output_dir, 'scan_log.json')
    import json
    if os.path.exists(scan_log_file):
        with open(scan_log_file, 'r', encoding='utf-8') as f:
            scan_log = json.load(f)
        # Son eklenenler en üstte olacak şekilde ters sırala
        recent_scans = list(reversed(scan_log))
    else:
        # Eski yöntem: sadece klasör isimleri
        for folder in os.listdir(output_dir):
            if folder.startswith('arama'):
                recent_scans.append({'folder': folder, 'target': folder})
        recent_scans.sort(key=lambda x: x['folder'], reverse=True)

    if request.method == 'POST':
        target_url = request.form.get('target')
        if not target_url:
            return render_template('index.html', error="Hedef URL boş olamaz veya formda 'target' alanı eksik.")
        safe_target_for_url = quote_plus(target_url)
        # Araç seçimlerini al
        selected_tools = []
        if request.form.get('run_sublist3r'):
            selected_tools.append('sublist3r')
        if request.form.get('run_subdomainizer'):
            selected_tools.append('subdomainizer')
        if request.form.get('run_ffuf'):
            selected_tools.append('ffuf')
        # Araçları virgül ile birleştirip parametre olarak ilet
        tools_param = ','.join(selected_tools)
        scan_folder_name = f"arama{len(recent_scans)+1}_{sanitize_filename(unquote_plus(target_url))}"
        scan_folder_path = os.path.join(output_dir, scan_folder_name)
        os.makedirs(scan_folder_path, exist_ok=True)
        # Log tarama geçmişi
        scan_log_file = os.path.join(output_dir, 'scan_log.json')
        import json
        if os.path.exists(scan_log_file):
            with open(scan_log_file, 'r', encoding='utf-8') as f:
                scan_log = json.load(f)
        else:
            scan_log = []
        # Aynı folder varsa tekrar ekleme
        if not any(entry['folder'] == scan_folder_name for entry in scan_log):
            # FFUF için wordlist alanını da kaydet
            ffuf_wordlist = request.form.get('wordlist', '').strip()
            if not ffuf_wordlist:
                ffuf_wordlist = get_wordlist_path('common_small.txt')
            scan_log.append({'folder': scan_folder_name, 'target': target_url, 'tools': selected_tools, 'ffuf_wordlist': ffuf_wordlist})
        with open(scan_log_file, 'w', encoding='utf-8') as f:
            json.dump(scan_log, f, ensure_ascii=False, indent=2)
        
        # Start scan threads
        threads = []
        for tool in selected_tools:
            wordlist_path = ffuf_wordlist if tool == 'ffuf' else None
            thread = threading.Thread(
                target=run_scan_tool,
                args=(tool, target_url, scan_folder_name, wordlist_path)
            )
            thread.start()
            threads.append(thread)
        
        return redirect(url_for('run_scans', scan_folder=scan_folder_name))
    return render_template('index.html', recent_scans=recent_scans)

@app.route('/scan/<scan_folder>')
def run_scans(scan_folder):
    return redirect(url_for('show_results', scan_folder=scan_folder))

@app.route('/scan_status/<scan_folder>')
def get_scan_status(scan_folder):
    """API endpoint to get current scan status"""
    if scan_folder in scan_statuses:
        return jsonify(scan_statuses[scan_folder])
    return jsonify({})

@app.route('/results/<scan_folder>')
def show_results(scan_folder):
    # scan_folder ör: arama1_googlecom
    import re
    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    scan_folder_path = os.path.join(output_base, scan_folder)
    # scan_log.json'dan hedefi bul
    scan_log_file = os.path.join(output_base, 'scan_log.json')
    target_info = {}
    tools_run = []
    ffuf_wordlist_used = ""

    if os.path.exists(scan_log_file):
        with open(scan_log_file, 'r', encoding='utf-8') as f:
            scan_log = json.load(f)
        for entry in scan_log:
            if entry['folder'] == scan_folder:
                target_info = entry
                tools_run = entry.get('tools', [])
                ffuf_wordlist_used = entry.get('ffuf_wordlist', get_wordlist_path('common_small.txt'))
                break
    
    target_url = target_info.get('target', scan_folder) # Fallback to scan_folder if target not in log
    results_paths = {
        'target': target_url,
        'sublist3r_stdout': os.path.join(scan_folder_path, "sublist3r_sublist3r_stdout.txt"),
        'sublist3r_stderr': os.path.join(scan_folder_path, "sublist3r_sublist3r_stderr.txt"),
        'subdomainizer_stdout': os.path.join(scan_folder_path, "subdomainizer_subdomainizer_stdout.txt"),
        'subdomainizer_stderr': os.path.join(scan_folder_path, "subdomainizer_subdomainizer_stderr.txt"),
        'ffuf_json': os.path.join(scan_folder_path, f"{scan_folder}_ffuf.json"),
        'ffuf_stderr': os.path.join(scan_folder_path, "ffuf_ffuf_stderr.txt"),
    }

    # --- Read Sublist3r Output ---
    sublist3r_stdout_content = ""
    try:
        with open(results_paths['sublist3r_stdout'], 'r', encoding='utf-8') as f:
            sublist3r_stdout_content = strip_ansi_codes(f.read())
        # Define the line that marks the end of Google enumeration in Sublist3r output
        google_enum_finished_line = "[*] Google search finished."
        if google_enum_finished_line in sublist3r_stdout_content:
            content_after_google_enum = sublist3r_stdout_content.split(google_enum_finished_line, 1)[-1]
            # Split into lines and remove leading/trailing whitespace from each
            lines_after_google_enum = [line.strip() for line in content_after_google_enum.split('\n')]
            
            # Filter out empty lines and lines that are known to be status/error messages from Sublist3r
            potential_subdomain_lines = [
                line for line in lines_after_google_enum 
                if line and not line.startswith(('[!]', '[-]', '[~]', '[*]')) and not "Error:" in line
            ]
            # If no such lines exist, append the "No subdomains found" message.
            if not potential_subdomain_lines:
                sublist3r_stdout_content += "\n\n[Bilgi] Belirtilen kriterlere göre alt alan adı bulunamadı (Google taraması sonrası)."
    except FileNotFoundError:
        sublist3r_stdout_content = "Sublist3r standart çıktı dosyası bulunamadı."
    except Exception as e:
        sublist3r_stdout_content = f"Sublist3r standart çıktı okunurken bir hata oluştu: {str(e)}"

    sublist3r_stderr_content = ""
    try:
        with open(results_paths['sublist3r_stderr'], 'r', encoding='utf-8') as f:
            sublist3r_stderr_content = strip_ansi_codes(f.read())
    except FileNotFoundError:
        sublist3r_stderr_content = "Sublist3r hata dosyası bulunamadı."
    except Exception as e:
        sublist3r_stderr_content = f"Sublist3r hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # --- Read SubDomainizer Output ---
    subdomainizer_stdout_content = ""
    subdomainizer_cloudurls = []
    try:
        with open(results_paths['subdomainizer_stdout'], 'r', encoding='utf-8') as f:
            subdomainizer_stdout_content = strip_ansi_codes(f.read())
            # Cloud URL'leri ayrıştır
            cloud_section = None
            lines = subdomainizer_stdout_content.splitlines()
            for idx, line in enumerate(lines):
                if line.strip().startswith('Total Cloud URLs:'):
                    # Sonraki satırlardan boş satır veya "_" ile başlayan satıra kadar olanları al
                    cloud_section = []
                    for l in lines[idx+1:]:
                        if not l.strip() or l.strip().startswith('_'):
                            break
                        cloud_section.append(l.strip())
                    break
            if cloud_section:
                subdomainizer_cloudurls = cloud_section
    except FileNotFoundError:
        subdomainizer_stdout_content = "SubDomainizer standart çıktı dosyası bulunamadı."
    except Exception as e:
        subdomainizer_stdout_content = f"SubDomainizer sonuçları okunurken bir hata oluştu: {str(e)}"

    subdomainizer_stderr_content = ""
    try:
        with open(results_paths['subdomainizer_stderr'], 'r', encoding='utf-8') as f:
            subdomainizer_stderr_content = strip_ansi_codes(f.read())
    except FileNotFoundError:
        subdomainizer_stderr_content = "SubDomainizer hata dosyası bulunamadı."
    except Exception as e:
        subdomainizer_stderr_content = f"SubDomainizer hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # --- Read FFUF Output ---
    ffuf_json_raw = None
    ffuf_json_parsed = None # None means still processing or no data, [] means processed but empty
    ffuf_js_files = []
    try:
        # Check if ffuf output file exists and is not empty
        if os.path.exists(results_paths['ffuf_json']) and os.path.getsize(results_paths['ffuf_json']) > 0:
            with open(results_paths['ffuf_json'], 'r', encoding='utf-8') as f:
                ffuf_json_raw = f.read()
                try:
                    ffuf_data = json.loads(ffuf_json_raw)
                    ffuf_json_parsed = ffuf_data.get('results', [])
                    # FFUF ile bulunan JS dosyalarını ayıkla
                    for result in ffuf_json_parsed:
                        if result.get('url', '').endswith('.js'):
                            ffuf_js_files.append(result.get('url'))
                except json.JSONDecodeError:
                    ffuf_json_parsed = [] # Mark as processed but failed to parse
                    print(f"Error decoding FFUF JSON: {results_paths['ffuf_json']}")
        else:
            # Dosya yoksa veya boşsa, tarama devam ediyor veya FFUF hiç çalıştırılmamış olabilir.
            # Eğer FFUF'un durumu "Tamamlandı" veya "Hata" ise ve dosya hala yoksa, o zaman gerçekten sonuç yoktur.
            current_ffuf_status = scan_statuses.get(scan_folder, {}).get('ffuf', {}).get('status')
            if current_ffuf_status in ["Tamamlandı", "Hata", "Zaman Aşımı"]:
                ffuf_json_parsed = [] # FFUF tamamlandı ama dosya yok/boş = sonuç yok
            # else: ffuf_json_parsed None olarak kalır (devam ediyor)

    except Exception as e:
        print(f"Error reading or processing FFUF output {results_paths['ffuf_json']}: {e}")
        ffuf_json_parsed = [] # Hata durumunda işlenmiş ama boş olarak işaretle

    ffuf_stderr_content = ""
    try:
        with open(results_paths['ffuf_stderr'], 'r', encoding='utf-8') as f:
            ffuf_stderr_content = strip_ansi_codes(f.read())
    except FileNotFoundError:
        ffuf_stderr_content = "FFUF konsol hata dosyası bulunamadı."
    except Exception as e:
        ffuf_stderr_content = f"FFUF konsol hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # Render the results template with all collected data
    return render_template('results_display.html',
                           target=target_url,
                           sublist3r_stdout=sublist3r_stdout_content,
                           sublist3r_stderr=sublist3r_stderr_content,
                           subdomainizer_stdout=subdomainizer_stdout_content,
                           subdomainizer_stderr=subdomainizer_stderr_content,
                           subdomainizer_cloudurls=subdomainizer_cloudurls,
                           ffuf_json_raw=ffuf_json_raw,
                           ffuf_json_parsed=ffuf_json_parsed,
                           ffuf_stderr=ffuf_stderr_content,
                           ffuf_js_files=ffuf_js_files,
                           tools_run=tools_run,
                           scan_folder=scan_folder,
                           GEMINI_API_KEY_AVAILABLE=bool(GEMINI_API_KEY))

@app.route('/fetch_external_js')
def fetch_external_js():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parametresi eksik."}), 400
    
    # Güvenlik için basit bir kontrol: Sadece http ve https protokollerine izin ver
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ['http', 'https']:
        return jsonify({"error": "Geçersiz URL şeması."}), 400

    try:
        content = fetch_js_content(url) # fetch_js_content zaten requests kullanıyor
        if content.startswith("Error fetching"):
             return jsonify({"error": content}), 500
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ai_chat/<scan_folder>', methods=['GET'])
def ai_chat_page(scan_folder):
    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    scan_folder_path = os.path.join(output_base, scan_folder)
    scan_log_file = os.path.join(output_base, 'scan_log.json')

    target_url = ""
    tools_run_for_scan = []
    if os.path.exists(scan_log_file):
        with open(scan_log_file, 'r', encoding='utf-8') as f:
            scan_log = json.load(f)
        for entry in scan_log:
            if entry['folder'] == scan_folder:
                target_url = entry['target']
                tools_run_for_scan = entry.get('tools', [])
                break
    
    if not target_url:
        return "Tarama bilgisi bulunamadı.", 404

    # Base context for AI
    ai_initial_context = "You are a Cyber Security Tool named Renaissance Recon (Rönesans). Below you will have some sublist3r, subdomainizer and ffuf results, and potentially JavaScript file contents. You should give ideas and probabilities based on that and chat with the user. Respond in language user talks.\n\n"
    ai_initial_context += f"Scan Target: {target_url}\n\n"

    # --- Gather data for AI context ---
    data_for_ai = {"target": target_url}

    # Sublist3r
    if 'sublist3r' in tools_run_for_scan:
        sublist3r_stdout_path = os.path.join(scan_folder_path, "sublist3r_sublist3r_stdout.txt")
        if os.path.exists(sublist3r_stdout_path):
            with open(sublist3r_stdout_path, 'r', encoding='utf-8') as f:
                data_for_ai['sublist3r_stdout'] = f.read()
        else:
            data_for_ai['sublist3r_stdout'] = "Sublist3r output not found."
        ai_initial_context += "--- Sublist3r Output ---\n" + data_for_ai['sublist3r_stdout'] + "\n\n"

    # SubDomainizer
    if 'subdomainizer' in tools_run_for_scan:
        subdomainizer_stdout_path = os.path.join(scan_folder_path, "subdomainizer_subdomainizer_stdout.txt")
        if os.path.exists(subdomainizer_stdout_path):
            with open(subdomainizer_stdout_path, 'r', encoding='utf-8') as f:
                data_for_ai['subdomainizer_stdout'] = f.read()
        else:
            data_for_ai['subdomainizer_stdout'] = "SubDomainizer output not found."
        ai_initial_context += "--- SubDomainizer Output ---\n" + data_for_ai['subdomainizer_stdout'] + "\n\n"
    
    # FFUF
    ffuf_results_for_ai = "FFUF scan was not run or results are not available."
    if 'ffuf' in tools_run_for_scan:
        ffuf_json_path = os.path.join(scan_folder_path, f"{scan_folder}_ffuf.json")
        if os.path.exists(ffuf_json_path):
            try:
                with open(ffuf_json_path, 'r', encoding='utf-8') as f:
                    ffuf_data_raw = f.read()
                    ffuf_data = json.loads(ffuf_data_raw)
                    data_for_ai['ffuf_results'] = ffuf_data.get('results', [])
                    ffuf_results_for_ai = "--- FFUF Results ---\n"
                    if data_for_ai['ffuf_results']:
                        for res in data_for_ai['ffuf_results']:
                            ffuf_results_for_ai += f"- URL: {res.get('url')}, Status: {res.get('status')}, Length: {res.get('length')}\n"
                    else:
                        ffuf_results_for_ai += "No paths found by FFUF or results were filtered out.\n"
                    
                    # Potansiyel olarak FFUF ile bulunan .js dosyalarını da ekleyebiliriz.
                    ffuf_js_files_content = ""
                    for res in data_for_ai.get('ffuf_results', []):
                        url = res.get('url')
                        if url and url.endswith('.js'):
                            # JS dosyasının içeriğini çek
                            js_content = fetch_js_content(url)
                            ffuf_js_files_content += f"\n\n--- JS File: {url} ---\n{js_content}"
                    if ffuf_js_files_content:
                        ffuf_results_for_ai += ffuf_js_files_content
            except Exception as e:
                ffuf_results_for_ai = f"--- FFUF Results ---\nError processing FFUF results: {str(e)}\n"
        else:
            ffuf_results_for_ai = "--- FFUF Results ---\nFFUF JSON output file not found.\n"
    ai_initial_context += ffuf_results_for_ai + "\n"
    
    return render_template('ai_chat.html', scan_folder=scan_folder, initial_context=ai_initial_context, target_url=target_url)

@app.route('/gemini_chat', methods=['POST'])
def gemini_chat_handler():
    if not GEMINI_API_KEY:
        return jsonify({"error": "Gemini API key not configured."}), 500

    data = request.json
    user_message = data.get('message')
    history_raw = data.get('history', []) # Expecting [{'role': 'user'/'model', 'parts': ['text']}]

    if not user_message:
        return jsonify({"error": "No message provided."}), 400

    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Construct history for the API
        chat_history = []
        for entry in history_raw:
            role = entry.get('role')
            parts = entry.get('parts')
            if role and parts:
                 chat_history.append({'role': role, 'parts': parts})
        
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(user_message)
        
        # Check for content and finish reason before accessing response.text
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            return jsonify({"reply": response.text})
        else:
            error_detail = "No valid content part in response."
            if response.prompt_feedback:
                error_detail += f" Prompt Feedback: {response.prompt_feedback}."
            if response.candidates and response.candidates[0].finish_reason:
                error_detail += f" Finish Reason: {response.candidates[0].finish_reason}."
            if response.candidates and response.candidates[0].safety_ratings:
                error_detail += f" Safety Ratings: {response.candidates[0].safety_ratings}."
            print(f"Gemini API Error: {error_detail}") # Log to server console
            return jsonify({"error": f"AI yanıtı alınamadı veya içerik filtrelendi. Detay: {error_detail}"}), 500

    except Exception as e:
        print(f"Gemini API Exception: {str(e)}") # Log to server console
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Sunucuyu tüm arayüzlerde (0.0.0.0) çalıştırın, böylece Docker container dışından erişilebilir olur.
    app.run(debug=True, host='0.0.0.0', port=5000)
