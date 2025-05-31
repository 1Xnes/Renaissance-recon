import os
import subprocess
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from urllib.parse import quote_plus, unquote_plus, urlparse

app = Flask(__name__)

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
    decoded_target_url = scan_folder
    tools_run = ['sublist3r', 'subdomainizer', 'ffuf']  # Varsayılan, eğer scan_log yoksa hepsi gösterilsin
    if os.path.exists(scan_log_file):
        import json
        with open(scan_log_file, 'r', encoding='utf-8') as f:
            scan_log = json.load(f)
        for entry in scan_log:
            if entry['folder'] == scan_folder:
                decoded_target_url = entry['target']
                tools_run = entry.get('tools', tools_run)
                break
    results_paths = {
        'target': decoded_target_url,
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
            sublist3r_stdout_content = f.read()
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
            sublist3r_stderr_content = f.read()
    except FileNotFoundError:
        sublist3r_stderr_content = "Sublist3r hata dosyası bulunamadı."
    except Exception as e:
        sublist3r_stderr_content = f"Sublist3r hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # --- Read SubDomainizer Output ---
    subdomainizer_stdout_content = ""
    subdomainizer_cloudurls = []
    try:
        with open(results_paths['subdomainizer_stdout'], 'r', encoding='utf-8') as f:
            subdomainizer_stdout_content = f.read()
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
            subdomainizer_stderr_content = f.read()
    except FileNotFoundError:
        subdomainizer_stderr_content = "SubDomainizer hata dosyası bulunamadı."
    except Exception as e:
        subdomainizer_stderr_content = f"SubDomainizer hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # --- Read FFUF Output ---
    ffuf_json_content_parsed = None # For parsed JSON data (list of results)
    ffuf_json_content_raw = ""    # For raw JSON string (fallback or for display)
    try:
        with open(results_paths['ffuf_json'], 'r', encoding='utf-8') as f:
            ffuf_json_content_raw = f.read() 
            if ffuf_json_content_raw.strip(): # Proceed if file is not empty
                data = json.loads(ffuf_json_content_raw)
                # FFUF JSON structure has a 'results' key which is a list of findings.
                ffuf_json_content_parsed = data.get('results', []) 
            else: # File is empty or only whitespace
                ffuf_json_content_parsed = [] # Treat as no results
                ffuf_json_content_raw = "{}" # Represent empty JSON for raw display
    except FileNotFoundError:
        ffuf_json_content_raw = "FFUF JSON sonuç dosyası bulunamadı."
        ffuf_json_content_parsed = [] # Pass empty list to template to avoid errors if file not found
    except json.JSONDecodeError:
        # If JSON parsing fails, ffuf_json_content_parsed remains None.
        # The raw content (ffuf_json_content_raw) will be shown in the template.
        # No need to set ffuf_json_content_raw again, it's already read.
        ffuf_json_content_parsed = None 
    except Exception as e:
        ffuf_json_content_raw = f"FFUF JSON okunurken bir hata oluştu: {str(e)}"
        ffuf_json_content_parsed = [] # Pass empty list on other errors

    ffuf_stderr_content = ""
    try:
        with open(results_paths['ffuf_stderr'], 'r', encoding='utf-8') as f:
            ffuf_stderr_content = f.read()
    except FileNotFoundError:
        ffuf_stderr_content = "FFUF konsol hata dosyası bulunamadı."
    except Exception as e:
        ffuf_stderr_content = f"FFUF konsol hata günlükleri okunurken bir hata oluştu: {str(e)}"

    # Render the results template with all collected data
    return render_template('results_display.html',
                           target=decoded_target_url,
                           sublist3r_stdout=sublist3r_stdout_content,
                           sublist3r_stderr=sublist3r_stderr_content,
                           subdomainizer_stdout=subdomainizer_stdout_content,
                           subdomainizer_stderr=subdomainizer_stderr_content,
                           subdomainizer_cloudurls=subdomainizer_cloudurls,
                           ffuf_json_parsed=ffuf_json_content_parsed, 
                           ffuf_json_raw=ffuf_json_content_raw, 
                           ffuf_stderr=ffuf_stderr_content,
                           tools_run=tools_run,
                           scan_folder=scan_folder)

if __name__ == '__main__':
    # Run the Flask development server
    # Debug mode should be False in a production environment
    app.run(debug=True)
