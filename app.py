import os
import subprocess
import json
from flask import Flask, render_template, request, redirect, url_for
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


def get_tool_path(tool_name_with_subdir):
    # Helper function to get the absolute path to a tool's executable script.
    # tool_name_with_subdir should be like 'Sublist3r/sublist3r' or 'SubDomainizer/SubDomainizer'
    # It assumes the script has the same name as the last part of tool_name_with_subdir and a .py extension.
    script_name = os.path.basename(tool_name_with_subdir)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', tool_name_with_subdir + '.py')

def get_wordlist_path(wordlist_name):
    # Helper function to get the absolute path to a wordlist.
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wordlists', wordlist_name)

def run_command(command, output_file_base_for_logs, tool_name):
    # Runs a command and captures its stdout and stderr, saving them to files.
    # command: The command to run (list of strings).
    # output_file_base_for_logs: The base name for stdout/stderr log files (e.g., "google.com_").
    # tool_name: The name of the tool being run (e.g., "sublist3r", "ffuf").

    stdout_path = f"output/{output_file_base_for_logs}{tool_name}_stdout.txt"
    stderr_path = f"output/{output_file_base_for_logs}{tool_name}_stderr.txt"
    
    # For ffuf, the JSON output path is determined by its own '-o' argument in the command.
    # This function primarily handles stdout/stderr logging.

    try:
        # Execute the command
        # text=True ensures stdout/stderr are strings
        # cwd sets the current working directory for the subprocess, useful if tools expect to be run from their own directory
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', cwd=os.path.dirname(os.path.abspath(__file__)))
        stdout, stderr = process.communicate(timeout=300) # Timeout after 5 minutes

        # Write stdout to its log file
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write(stdout)
        # Write stderr to its log file
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(stderr)

        # ffuf writes its own JSON file as specified in its command arguments.
        # This function doesn't need to return the JSON path as it's constructed before calling run_command.

    except subprocess.TimeoutExpired:
        # Handle command timeout
        timeout_message = "Komut zaman aşımına uğradı (300 saniye)."
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write(timeout_message)
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(timeout_message)
    except Exception as e:
        # Handle other exceptions during command execution
        error_message = f"Komut çalıştırılırken bir hata oluştu: {str(e)}"
        with open(stdout_path, 'w', encoding='utf-8') as f_out:
            f_out.write("") # No stdout if command failed early
        with open(stderr_path, 'w', encoding='utf-8') as f_err:
            f_err.write(error_message)


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
        return redirect(url_for('run_scans', target=safe_target_for_url, tools=tools_param))
    return render_template('index.html')

@app.route('/scan/<target>')
@app.route('/scan/<target>/<tools>')
def run_scans(target, tools=None):
    # Scan execution route: decodes target, prepares commands, and runs them.
    decoded_target_url = unquote_plus(target) # The full URL as provided by the user
    selected_tools = []
    if tools:
        selected_tools = tools.split(',')
    else:
        # Geriye dönük uyumluluk için, eğer parametre yoksa hepsini çalıştır
        selected_tools = ['sublist3r', 'subdomainizer', 'ffuf']

    # For Sublist3r, we need just the domain name.
    parsed_url = urlparse(decoded_target_url)
    domain_for_sublist3r = parsed_url.netloc
    if not domain_for_sublist3r:
        domain_for_sublist3r = parsed_url.path.split('/')[0]
    if not domain_for_sublist3r:
        return redirect(url_for('index', error="Geçersiz hedef: Alan adı çıkarılamadı."))

    log_file_base = sanitize_filename(decoded_target_url) + "_"

    # Her araç için çıktı klasörü oluştur
    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    for tool in ['sublist3r', 'subdomainizer', 'ffuf']:
        tool_dir = os.path.join(output_base, tool)
        if not os.path.exists(tool_dir):
            os.makedirs(tool_dir)

    # --- Sublist3r ---
    if 'sublist3r' in selected_tools:
        sublist3r_py_path = get_tool_path('Sublist3r/sublist3r')
        sublist3r_command = ['python', sublist3r_py_path, '-d', domain_for_sublist3r]
        run_command(sublist3r_command, f"sublist3r/{log_file_base}", "sublist3r")

    # --- SubDomainizer ---
    if 'subdomainizer' in selected_tools:
        subdomainizer_py_path = get_tool_path('SubDomainizer/SubDomainizer')
        subdomainizer_command = ['python', subdomainizer_py_path, '-u', decoded_target_url]
        run_command(subdomainizer_command, f"subdomainizer/{log_file_base}", "subdomainizer")

    # --- FFUF ---
    if 'ffuf' in selected_tools:
        ffuf_target_url = decoded_target_url
        if not ffuf_target_url.endswith('/'):
            ffuf_target_url += '/'
        ffuf_target_url += 'FUZZ'
        ffuf_wordlist_path = get_wordlist_path('common_small.txt')
        ffuf_json_output_filename_base = sanitize_filename(decoded_target_url)
        ffuf_output_json_path = os.path.join(output_base, 'ffuf', f"{ffuf_json_output_filename_base}_ffuf.json")
        ffuf_command = [
            'ffuf', '-u', ffuf_target_url, '-w', ffuf_wordlist_path,
            '-o', ffuf_output_json_path, '-of', 'json',
            '-c',
            '-mc', '200,204,301,302,307,401,403,405,500'
        ]
        run_command(ffuf_command, f"ffuf/{log_file_base}", "ffuf")

    return redirect(url_for('show_results', target=target, tools=tools))


@app.route('/results/<target>')
@app.route('/results/<target>/<tools>')
def show_results(target, tools=None):
    # Results display route: reads scan output files and renders them in the template.
    decoded_target_url = unquote_plus(target)
    log_file_base = sanitize_filename(decoded_target_url) + "_"
    ffuf_json_filename_base = sanitize_filename(decoded_target_url)
    # Yeni çıktı yolları (her araç için ayrı klasör)
    results_paths = {
        'target': decoded_target_url,
        'sublist3r_stdout': f"output/sublist3r/{log_file_base}sublist3r_stdout.txt",
        'sublist3r_stderr': f"output/sublist3r/{log_file_base}sublist3r_stderr.txt",
        'subdomainizer_stdout': f"output/subdomainizer/{log_file_base}subdomainizer_stdout.txt",
        'subdomainizer_stderr': f"output/subdomainizer/{log_file_base}subdomainizer_stderr.txt",
        'ffuf_json': f"output/ffuf/{ffuf_json_filename_base}_ffuf.json",
        'ffuf_stderr': f"output/ffuf/{log_file_base}ffuf_stderr.txt",
    }

    # --- Read Sublist3r Output ---
    sublist3r_stdout_content = ""
    try:
        with open(results_paths['sublist3r_stdout'], 'r', encoding='utf-8') as f:
            sublist3r_stdout_content = f.read()
        
        # Check for "No subdomains found" condition for Sublist3r
        # This logic looks for a specific line and then checks if subsequent lines are empty or only status/errors.
        google_enum_finished_line = "[~] Finished now the Google Enumeration ..."
        if google_enum_finished_line in sublist3r_stdout_content:
            # Extract content after the "Finished Google Enumeration" line
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
    try:
        with open(results_paths['subdomainizer_stdout'], 'r', encoding='utf-8') as f:
            subdomainizer_stdout_content = f.read()
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
                           ffuf_json_parsed=ffuf_json_content_parsed, 
                           ffuf_json_raw=ffuf_json_content_raw, 
                           ffuf_stderr=ffuf_stderr_content)


if __name__ == '__main__':
    # Run the Flask development server
    # Debug mode should be False in a production environment
    app.run(debug=True)
