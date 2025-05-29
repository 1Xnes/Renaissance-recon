from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import threading
import time
import json
from recon_wrappers import run_ffuf, run_sublist3r, run_subdomainizer

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Or a fixed secret string for production
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
WORDLISTS_DIR = os.path.join(BASE_DIR, 'wordlists')

# Ensure output and wordlists directories exist
for dir_path in [OUTPUT_DIR, WORDLISTS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Path to the default ffuf wordlist
FFUF_WORDLIST_PATH = os.path.join(WORDLISTS_DIR, "common_small.txt")
if not os.path.exists(FFUF_WORDLIST_PATH):
    try:
        with open(FFUF_WORDLIST_PATH, "w") as f:
            # Added more common entries, including robots.txt
            f.write("admin\nlogin\nindex.html\nREADME.md\nconfig\n.git\napi\nuploads\nstatic\njs\ncss\ntest\nbackup\nold\nrobots.txt\n.htaccess\n.env\nconfig.js\nmain.js\napp.js\n")
        print(f"Sample ffuf wordlist created: {FFUF_WORDLIST_PATH}")
    except Exception as e:
        print(f"Could not create sample ffuf wordlist: {e}")

# Store active scans and their states
active_scans = {} # {scan_id: {status, tool, target, results_file, results_data, error_message, command_used, timestamp}}
scan_id_counter = 0
scan_lock = threading.Lock() # To synchronize access to scan_id_counter and active_scans

def run_scan_job(scan_id, tool_name, target_input):
    """
    Runs the specified reconnaissance tool in a separate thread and updates its status.
    """
    status_update_prefix = f"{tool_name} ({scan_id})"
    
    with scan_lock:
        active_scans[scan_id]["status"] = f"{status_update_prefix} - Preparing..."
    print(f"[THREAD-{scan_id}] Preparing for '{tool_name}' scan on '{target_input}'.")
    
    wrapper_response = None
    try:
        with scan_lock:
             active_scans[scan_id]["status"] = f"{status_update_prefix} - Running..."
        
        if tool_name == "ffuf":
            # ffuf_target_url = target_input # The wrapper now handles adding /FUZZ
            if not os.path.exists(FFUF_WORDLIST_PATH):
                 raise FileNotFoundError(f"ffuf wordlist not found: {FFUF_WORDLIST_PATH}")
            # Pass an empty string in extensions to also check for paths without extensions
            wrapper_response = run_ffuf(target_input, FFUF_WORDLIST_PATH, 
                                        extensions=[".html", ".php", ".txt", ".js", ".json", ""], 
                                        output_format="json")
        
        elif tool_name == "sublist3r":
            # Sublist3r expects a domain name, not a full URL
            domain_for_sublist3r = target_input.replace("http://", "").replace("https://", "").split("/")[0]
            wrapper_response = run_sublist3r(domain_for_sublist3r)
            
        elif tool_name == "subdomainizer":
            # SubDomainizer expects a full URL
            url_for_subdomainizer = target_input
            if not url_for_subdomainizer.startswith(('http://', 'https://')):
                url_for_subdomainizer = f"http://{url_for_subdomainizer}" # Default to http
            wrapper_response = run_subdomainizer(url_for_subdomainizer)
        else:
            raise ValueError(f"Unknown tool specified: {tool_name}")

        # Update scan status based on wrapper response
        with scan_lock:
            active_scans[scan_id]["command_used"] = wrapper_response.get("command_used", "Unknown")
            if wrapper_response and wrapper_response.get("error"):
                active_scans[scan_id]["status"] = f"{status_update_prefix} - Error Occurred"
                active_scans[scan_id]["error_message"] = wrapper_response["error"]
                print(f"[THREAD-{scan_id}] Error during {tool_name} scan: {wrapper_response['error']}")
            elif wrapper_response:
                active_scans[scan_id]["status"] = f"{status_update_prefix} - Completed"
                active_scans[scan_id]["results_data"] = wrapper_response.get("results") # Store parsed results directly
                active_scans[scan_id]["results_file"] = wrapper_response.get("output_file")
                print(f"[THREAD-{scan_id}] {tool_name} scan completed. Output file: {wrapper_response.get('output_file')}")
            else: # Should not happen if wrappers always return a dict
                active_scans[scan_id]["status"] = f"{status_update_prefix} - Error (No Response from Wrapper)"
                active_scans[scan_id]["error_message"] = f"The wrapper for {tool_name} returned no data."
                print(f"[ERROR][THREAD-{scan_id}] {tool_name} wrapper returned None.")

    except Exception as e:
        with scan_lock:
            active_scans[scan_id]["status"] = f"{status_update_prefix} - Critical Error in Job"
            active_scans[scan_id]["error_message"] = str(e)
        print(f"[CRITICAL ERROR][THREAD-{scan_id}] Unexpected error in {tool_name} job: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    global scan_id_counter # Ensure we're modifying the global counter
    
    # Get form data, default to empty if not POST or field not present
    target_domain_input = request.form.get('target_domain', '')
    tools_to_run = request.form.getlist('tools_to_run')
    
    message_parts = [] # For success messages
    error_message_global = None # For form validation or global errors

    if request.method == 'POST':
        if not target_domain_input:
            error_message_global = "Please enter a target domain/URL."
        elif not tools_to_run:
            error_message_global = "Please select at least one tool to run."
        else:
            for tool_name in tools_to_run:
                with scan_lock: # Synchronize access to shared resources
                    scan_id_counter += 1
                    current_scan_id = f"scan_{scan_id_counter}"
                    
                    active_scans[current_scan_id] = {
                        "status": "Queued", 
                        "tool": tool_name,
                        "target": target_domain_input,
                        "results_file": None,
                        "results_data": None, # Store parsed results here
                        "error_message": None,
                        "command_used": None, # Store the actual command run
                        "timestamp": time.time()
                    }
                
                try:
                    # Start the scan job in a new thread
                    scan_thread = threading.Thread(target=run_scan_job, args=(current_scan_id, tool_name, target_domain_input))
                    scan_thread.daemon = True # Allow main program to exit even if threads are running
                    scan_thread.start()
                    message_parts.append(f"{tool_name} scan ({current_scan_id}) for '{target_domain_input}' has been queued.")
                except Exception as e_thread_start:
                    thread_start_error = f"Failed to start thread for {tool_name}: {e_thread_start}"
                    with scan_lock:
                        active_scans[current_scan_id]['status'] = "Thread Start Error"
                        active_scans[current_scan_id]['error_message'] = thread_start_error
                    print(f"[ERROR] {thread_start_error}")
                    if error_message_global: error_message_global += f" | {thread_start_error}" 
                    else: error_message_global = thread_start_error
            
            if not error_message_global and message_parts: # Only show success if no global errors
                final_message = " | ".join(message_parts)
            else:
                final_message = None # Errors will be shown by error_message_global
            
    # Sort scans by timestamp (newest first) for display
    with scan_lock:
        # Create a list of tuples to sort, then convert back to dict for template
        # This is safer if active_scans is modified during iteration (though less likely here)
        sorted_scans_list = sorted(list(active_scans.items()), key=lambda item: item[1].get('timestamp', 0), reverse=True)
        # Pass the sorted list of tuples (scan_id, details) to the template
        # Template can iterate through this directly
    
    # If it's a GET request, or a POST that didn't set a specific message/error
    final_message_to_template = final_message if request.method == 'POST' and not error_message_global else None
    error_to_template = error_message_global if request.method == 'POST' else None


    return render_template('index.html', 
                           target_domain_input=target_domain_input, # Preserve input value on POST
                           message=final_message_to_template,
                           error=error_to_template,
                           active_scans_list=sorted_scans_list) # Pass sorted list of tuples


@app.route('/scan_status/<scan_id>')
def scan_status_api(scan_id):
    with scan_lock: # Ensure thread-safe access
        # print(f"API: /scan_status/{scan_id}. Current active_scans keys: {list(active_scans.keys())}") # DEBUG
        scan_info_dict = active_scans.get(scan_id)
    
    if not scan_info_dict:
        return jsonify({"error": "Invalid scan ID", "scan_id": scan_id}), 404
    
    # Return a copy to avoid issues if the dict is modified by another thread while creating JSON
    with scan_lock:
        response_data = dict(scan_info_dict) 
    
    # Don't send full results_data in status, it can be large
    if "results_data" in response_data:
        del response_data["results_data"] 

    return jsonify(response_data)


@app.route('/get_scan_results/<scan_id>')
def get_scan_results_api(scan_id):
    with scan_lock:
        scan_info_dict = active_scans.get(scan_id)
    
    if not scan_info_dict:
        return jsonify({"error": "Invalid scan ID"}), 404
    
    with scan_lock: # Make a copy for processing
        scan_info_for_processing = dict(scan_info_dict)

    if not scan_info_for_processing["status"].endswith("Completed"):
        return jsonify({"error": "Scan not yet completed or encountered an error.", 
                        "status": scan_info_for_processing["status"]}), 400

    # 1. Prefer results_data (parsed results from memory)
    if scan_info_for_processing.get("results_data") is not None:
        return jsonify({
            "scan_id": scan_id,
            "target": scan_info_for_processing["target"],
            "tool": scan_info_for_processing["tool"],
            "results_source": "memory",
            "results": scan_info_for_processing["results_data"],
            "command_used": scan_info_for_processing.get("command_used")
        })
    
    # 2. Fallback to reading from results_file if results_data is empty but file exists
    results_file_path = scan_info_for_processing.get("results_file")
    if not results_file_path or not os.path.exists(results_file_path):
        return jsonify({"error": "Results file not found or path is undefined.", 
                        "path_checked": results_file_path, 
                        "status": scan_info_for_processing["status"]}), 404

    try:
        parsed_file_results = None
        with open(results_file_path, 'r', encoding='utf-8') as f:
            tool_type = scan_info_for_processing["tool"]
            
            if tool_type == "ffuf": # ffuf JSON output contains a "results" list
                raw_data = json.load(f)
                parsed_file_results = raw_data.get("results", [])
            elif tool_type == "sublist3r": # Sublist3r output is a text file, one subdomain per line
                parsed_file_results = [line.strip() for line in f if line.strip()]
            elif tool_type == "subdomainizer": # SubDomainizer text output is parsed by its wrapper
                # The wrapper should return the parsed dict in 'results'.
                # If we are reading the file here, it means 'results_data' was None.
                # This implies we might need to re-parse, or ensure wrapper always populates results_data
                # For simplicity, assume if results_data is None but file exists, we re-parse.
                # This is redundant if wrapper already parsed. Ideally wrapper's result is trusted.
                # Let's assume results_data should be populated by the wrapper.
                # If results_data is None but file exists, it's an inconsistency.
                # Here, we'll try to parse it like the wrapper for robustness.
                file_content = f.read()
                parsed_file_results = parse_subdomainizer_text_output(file_content) # Use the parser from recon_wrappers
            else:
                # For other tools, read as plain text or indicate unknown format
                file_content_preview = f.read(2048) # Read first 2KB as preview
                parsed_file_results = f"Raw file content (preview for {tool_type}):\n{file_content_preview}" \
                                      if os.path.getsize(results_file_path) > 0 else "File is empty."
            
        return jsonify({
            "scan_id": scan_id,
            "target": scan_info_for_processing["target"],
            "tool": scan_info_for_processing["tool"],
            "results_source": "file",
            "results_file_path": results_file_path, # For informational purposes
            "results": parsed_file_results,
            "command_used": scan_info_for_processing.get("command_used")
        })
    except json.JSONDecodeError as je:
        return jsonify({"error": f"Failed to parse results JSON file: {str(je)}", "file": results_file_path}), 500
    except Exception as e:
        return jsonify({"error": f"Error reading/parsing results file: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)