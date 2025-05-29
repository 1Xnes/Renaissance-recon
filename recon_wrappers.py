import subprocess
import os
import re
import json
import sys

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')
WORDLISTS_DIR = os.path.join(BASE_DIR, 'wordlists')


# Ensure necessary directories exist
for dir_path in [OUTPUT_DIR, WORDLISTS_DIR, TOOLS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"Directory created: {dir_path}")

def run_ffuf(target_url, wordlist_path, extensions=None, output_format="json"):
    # Prepare target URL and display URL
    original_target_url_for_display = target_url
    if not target_url.endswith("/FUZZ"):
        target_url = target_url.rstrip('/') + "/FUZZ"
        print(f"[INFO] ffuf target URL automatically set to: {target_url}")
    else:
        original_target_url_for_display = target_url[:-5] # Remove /FUZZ for display

    if not os.path.exists(wordlist_path):
        msg = f"Wordlist not found: {wordlist_path}"
        print(f"[ERROR] {msg}")
        return {"error": msg, "results": [], "output_file": None, "command_used": ""}

    # Sanitize domain part for filename
    domain_part_for_file = original_target_url_for_display.split("//")[-1].split("/")[0].replace(":", "_").replace(".", "_")
    output_file_base = os.path.join(OUTPUT_DIR, f"{domain_part_for_file}_ffuf")
    
    # Command: use -s for silent mode for ffuf v2.1.0
    command = ["ffuf", "-s", "-w", wordlist_path, "-u", target_url, "-mc", "200,204,301,302,307,401,403"]

    if extensions:
        valid_extensions = [ext.strip() for ext in extensions if ext and ext.strip()] # Filter out empty strings
        if valid_extensions:
            ext_string = ",".join(valid_extensions)
            command.extend(["-e", ext_string])
        elif "" in extensions and len(extensions) == 1: # Only empty extension means no specific extension
            pass # ffuf will fuzz without -e
        elif "" in extensions: # if ["", ".php"] -> handle this or let ffuf decide. ffuf -e ".php," might be an issue
             print(f"[WARN] Empty string in extensions list for ffuf: {extensions}. This might lead to unexpected behavior with -e flag.")


    output_file_path = None
    if output_format == "json":
        output_file_path = f"{output_file_base}.json"
        command.extend(["-o", output_file_path, "-of", "json"])
    else:
        output_file_path = f"{output_file_base}.txt"
        command.extend(["-o", output_file_path])

    command_str = ' '.join(command)
    print(f"[INFO] Running ffuf command: {command_str}")

    found_paths = []
    error_message = None
    final_output_file = None

    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=300, encoding='utf-8', errors='ignore')

        if process.returncode == 0 or process.returncode == 1: # ffuf might return 1 if no results but not an error
            print(f"[SUCCESS] ffuf scan completed for: {original_target_url_for_display}")
            if output_format == "json" and output_file_path and os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
                try:
                    with open(output_file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for result in data.get("results", []):
                        found_paths.append({
                            "url": result.get("url"),
                            "status": result.get("status"),
                            "length": result.get("length")
                        })
                    print(f"[INFO] Parsed {len(found_paths)} results from JSON output.")
                    final_output_file = output_file_path
                except json.JSONDecodeError as je:
                    file_content_preview = ""
                    try:
                        with open(output_file_path, 'r', encoding='utf-8') as f_err:
                            file_content_preview = f_err.read(200)
                    except Exception: pass
                    error_message = f"Failed to parse ffuf JSON output: {je}. File: {output_file_path}. Content (first 200 chars): '{file_content_preview}'"
                    print(f"[ERROR] {error_message}")
                except Exception as e_file:
                    error_message = f"Error reading ffuf JSON file: {e_file}. File: {output_file_path}"
                    print(f"[ERROR] {error_message}")
            elif output_file_path and os.path.exists(output_file_path):
                print(f"[INFO] ffuf output ({output_format}) saved to: {output_file_path}")
                final_output_file = output_file_path
                if not found_paths:
                     print(f"[INFO] ffuf non-JSON output or unparsed JSON. File available at: {output_file_path}")
            
            if not error_message and not found_paths:
                 print(f"[INFO] ffuf scan found no matching paths for {original_target_url_for_display} or could not parse them.")

        else: # ffuf exited with an error code other than 0 or 1
            error_message = f"ffuf exited with error. Return code: {process.returncode}."
            # Log only the first line of stderr/stdout if they are too long
            if process.stderr: error_message += f" stderr: {process.stderr.strip().splitlines()[0] if process.stderr.strip() else '(empty)'}"
            if process.stdout: error_message += f" stdout: {process.stdout.strip().splitlines()[0] if process.stdout.strip() else '(empty)'}"
            print(f"[ERROR] {error_message}")

    except FileNotFoundError:
        error_message = "ffuf command not found. Ensure it's installed and in your system's PATH."
        print(f"[ERROR] {error_message}")
    except subprocess.TimeoutExpired:
        error_message = f"ffuf scan timed out for {original_target_url_for_display}."
        print(f"[ERROR] {error_message}")
    except Exception as e:
        error_message = f"An unexpected error occurred while running ffuf for {original_target_url_for_display}: {e}"
        print(f"[ERROR] {error_message}")
    
    return {"error": error_message, "results": found_paths, "output_file": final_output_file, "command_used": command_str}

def run_sublist3r(target_domain, output_dir=OUTPUT_DIR):
    tool_script_path = os.path.join(TOOLS_DIR, "Sublist3r", "sublist3r.py")
    if not os.path.exists(tool_script_path):
        msg = f"Sublist3r script not found: {tool_script_path}"
        print(f"[ERROR] {msg}")
        return {"error": msg, "results": [], "output_file": None, "command_used": ""}

    sanitized_domain_name = target_domain.replace(".", "_")
    output_file_name = f"{sanitized_domain_name}_sublist3r.txt"
    output_file_path = os.path.join(output_dir, output_file_name)

    # Sublist3r can be slow, consider adding -t (threads) or specific engines -e google,yahoo
    command = [sys.executable, tool_script_path, "-d", target_domain, "-o", output_file_path]
    command_str = ' '.join(command)
    print(f"[INFO] Running Sublist3r command: {command_str}")
    
    subdomains_found = []
    error_msg = None
    actual_output_file = None

    try:
        # Sublist3r often prints to stdout regardless of -o, especially errors or progress
        process = subprocess.run(command, capture_output=True, text=True, timeout=400, encoding='utf-8', errors='ignore')
        
        # Prioritize reading from the output file if it exists and has content
        if os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
            print(f"[INFO] Sublist3r output file found: {output_file_path}")
            with open(output_file_path, 'r', encoding='utf-8') as f:
                subdomains_found = [line.strip() for line in f if line.strip() and '.' in line.strip()]
            actual_output_file = output_file_path
            print(f"[INFO] Sublist3r read {len(subdomains_found)} subdomains from file.")
        elif process.stdout: # Fallback to stdout if file is empty or not created
            print("[INFO] Sublist3r output file empty or not created, parsing stdout.")
            # Basic regex to find domain-like strings in stdout
            # Sublist3r output varies, this might need refinement.
            # It often lists them one per line after "Searching in..." messages.
            # A more robust way is to find lines that are valid subdomains of the target.
            raw_stdout_lines = process.stdout.splitlines()
            for line in raw_stdout_lines:
                cleaned_line = line.strip()
                if cleaned_line.endswith(f".{target_domain}") and cleaned_line != target_domain:
                    if cleaned_line not in subdomains_found: # Avoid duplicates
                        subdomains_found.append(cleaned_line)
            if subdomains_found:
                 print(f"[INFO] Sublist3r parsed {len(subdomains_found)} potential subdomains from stdout.")
            else:
                 print("[INFO] No subdomains parsed from Sublist3r stdout.")
        
        if process.returncode == 0:
            print(f"[SUCCESS] Sublist3r scan (nominally) completed for: {target_domain}")
            if not subdomains_found:
                print(f"[INFO] Sublist3r found no subdomains for {target_domain}.")
        else: # Sublist3r exited with an error
            error_msg = f"Sublist3r exited with error code {process.returncode}."
            if process.stderr: error_msg += f" stderr: {process.stderr.strip()}"
            # Sometimes error info is in stdout for Sublist3r
            if process.stdout and not subdomains_found: error_msg += f" stdout (first 200 chars): {process.stdout.strip()[:200]}"
            print(f"[ERROR] {error_msg.splitlines()[0] if error_msg else 'Unknown Sublist3r error'}")
            
    except FileNotFoundError: # For sys.executable or tool_script_path
        error_msg = f"Could not run Sublist3r. Python: {sys.executable} or Script: {tool_script_path} not found."
        print(f"[ERROR] {error_msg}")
    except subprocess.TimeoutExpired:
        error_msg = f"Sublist3r scan timed out for {target_domain}."
        print(f"[ERROR] {error_msg}")
    except Exception as e:
        error_msg = f"An unexpected error occurred while running Sublist3r for {target_domain}: {e}"
        print(f"[ERROR] {error_msg}")

    return {"error": error_msg, "results": list(set(subdomains_found)), "output_file": actual_output_file, "command_used": command_str}


def parse_subdomainizer_text_output(file_content):
    """
    Parses the text output of SubDomainizer to extract secrets, cloud assets, and JS subdomains.
    This is a basic parser and might need adjustments based on exact SubDomainizer output format.
    """
    parsed_results = {
        "secrets": [],
        "cloud_assets": [],
        "subdomains_from_js": []
    }
    current_section = None

    # Regex patterns (very basic, might need refinement)
    # Secrets can be very diverse. This looks for common keywords.
    secret_keywords = [
        'api_key', 'apikey', 'secret', 'password', 'token', 'auth', 'key',
        'aws_access_key_id', 'aws_secret_access_key', 'AZURE_', 'GCP_', 'firebase', 'slack_token'
    ]
    # This is a very naive secret finder, real secret scanning is much more complex.
    # SubDomainizer itself has more sophisticated entropy based checks. We are parsing its *reported* secrets.
    
    # Cloud patterns (common prefixes/suffixes)
    s3_pattern = re.compile(r"s3://[a-zA-Z0-9.-]+")
    cloudfront_pattern = re.compile(r"[a-zA-Z0-9.-]+\.cloudfront\.net")
    # Add more patterns for Azure, GCP, DigitalOcean if SubDomainizer lists them clearly

    for line in file_content.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Section detection (example, adjust to actual SubDomainizer output headers)
        if "Subdomains found from javascripts" in line_stripped or "Subdomains found in JS files" in line_stripped:
            current_section = "subdomains_from_js"
            continue
        elif "Secrets Found" in line_stripped or "Potential Secrets" in line_stripped:
            current_section = "secrets"
            continue
        elif "Cloud URLs Found" in line_stripped or "Cloud Assets" in line_stripped or "S3 Buckets" in line_stripped:
            current_section = "cloud_assets"
            continue
        
        # Data extraction based on current section
        if current_section == "subdomains_from_js":
            # Assuming subdomains are listed one per line under the header
            if '.' in line_stripped and not line_stripped.startswith(('http', '*', '[')): # Basic validation
                parsed_results["subdomains_from_js"].append(line_stripped)
        
        elif current_section == "secrets":
            # SubDomainizer might list secrets more directly.
            # If it's just "keyword: value", we might need to capture that.
            # For now, if the line contains a keyword, add the line.
            if any(keyword in line_stripped.lower() for keyword in secret_keywords):
                 parsed_results["secrets"].append(line_stripped) # Store the whole line for context
        
        elif current_section == "cloud_assets":
            if s3_pattern.search(line_stripped):
                parsed_results["cloud_assets"].extend(s3_pattern.findall(line_stripped))
            if cloudfront_pattern.search(line_stripped):
                parsed_results["cloud_assets"].extend(cloudfront_pattern.findall(line_stripped))
            # Add other cloud URL parsing if SubDomainizer lists them generically

    # Remove duplicates
    for key in parsed_results:
        parsed_results[key] = sorted(list(set(parsed_results[key])))
        
    return parsed_results


def run_subdomainizer(target_url, output_dir=OUTPUT_DIR):
    tool_script_path = os.path.join(TOOLS_DIR, "SubDomainizer", "SubDomainizer.py")
    if not os.path.exists(tool_script_path):
        msg = f"SubDomainizer script not found: {tool_script_path}"
        print(f"[ERROR] {msg}")
        return {"error": msg, "results": {}, "output_file": None, "command_used": ""}

    url_for_tool = target_url
    if not target_url.startswith(('http://', 'https://')):
        url_for_tool = f"http://{target_url}" # SubDomainizer usually expects a full URL
    
    domain_part_for_file = url_for_tool.split("//")[-1].split("/")[0].replace(":", "_").replace(".", "_")
    # SubDomainizer's -o typically creates a .txt file. We will parse this text file.
    # The log showed it creating a .json file but writing text to it. We'll aim for .txt.
    output_file_name_txt = f"{domain_part_for_file}_subdomainizer.txt"
    output_file_path_txt = os.path.join(output_dir, output_file_name_txt)

    # SubDomainizer does not have a direct JSON output flag mentioned in its help usually.
    # It saves its console-like output to the file specified by -o.
    command = [sys.executable, tool_script_path, "-u", url_for_tool, "-o", output_file_path_txt]
    # Consider adding: -san (AWS same account), -g (GitHub search), -k (skip health check) for more thorough scans
    command_str = ' '.join(command)
    print(f"[INFO] Running SubDomainizer command: {command_str}")

    parsed_results_data = {"secrets": [], "cloud_assets": [], "subdomains_from_js": []}
    error_msg = None
    actual_output_file = None

    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='ignore')

        if process.returncode == 0:
            print(f"[SUCCESS] SubDomainizer scan (nominally) completed for: {url_for_tool}")
            if os.path.exists(output_file_path_txt) and os.path.getsize(output_file_path_txt) > 0:
                actual_output_file = output_file_path_txt
                print(f"[INFO] SubDomainizer output file found: {actual_output_file}. Parsing content...")
                with open(actual_output_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                parsed_results_data = parse_subdomainizer_text_output(file_content)
                print(f"[INFO] SubDomainizer text output parsed. Secrets: {len(parsed_results_data['secrets'])}, Cloud: {len(parsed_results_data['cloud_assets'])}, JS Subs: {len(parsed_results_data['subdomains_from_js'])}")
            else: # File not created or empty
                # Sometimes SubDomainizer prints to stdout even with -o if there are issues or few results
                stdout_content = process.stdout.strip()
                if stdout_content:
                    print(f"[INFO] SubDomainizer output file empty/not found. Parsing stdout (length: {len(stdout_content)}).")
                    parsed_results_data = parse_subdomainizer_text_output(stdout_content)
                    print(f"[INFO] SubDomainizer stdout parsed. Secrets: {len(parsed_results_data['secrets'])}, Cloud: {len(parsed_results_data['cloud_assets'])}, JS Subs: {len(parsed_results_data['subdomains_from_js'])}")
                    if not (parsed_results_data["secrets"] or parsed_results_data["cloud_assets"] or parsed_results_data["subdomains_from_js"]):
                         error_msg = "SubDomainizer ran but no specific data could be parsed from stdout."
                else:
                    error_msg = f"SubDomainizer output file was not created or is empty: {output_file_path_txt}. Stdout was also empty."
                print(f"[WARN] {error_msg if error_msg else 'SubDomainizer output file issue.'}")
        else: # process.returncode != 0
            error_msg = f"SubDomainizer exited with error code {process.returncode}."
            if process.stderr: error_msg += f" stderr: {process.stderr.strip()}"
            if process.stdout: error_msg += f" stdout (first 200 chars): {process.stdout.strip()[:200]}"
            print(f"[ERROR] {error_msg.splitlines()[0] if error_msg else 'Unknown SubDomainizer error'}")
            
    except FileNotFoundError:
        error_msg = f"Could not run SubDomainizer. Python: {sys.executable} or Script: {tool_script_path} not found."
        print(f"[ERROR] {error_msg}")
    except subprocess.TimeoutExpired:
        error_msg = f"SubDomainizer scan timed out for {url_for_tool}."
        print(f"[ERROR] {error_msg}")
    except Exception as e:
        error_msg = f"An unexpected error occurred while running SubDomainizer for {url_for_tool}: {e}"
        print(f"[ERROR] {error_msg}")

    return {"error": error_msg, "results": parsed_results_data, "output_file": actual_output_file, "command_used": command_str}

if __name__ == '__main__':
    print("Reconnaissance Wrappers Module")
    # Example usage for testing (uncomment and adapt paths/targets as needed):
    # test_ffuf_wordlist = os.path.join(WORDLISTS_DIR, "common_small.txt")
    # if not os.path.exists(test_ffuf_wordlist):
    #     with open(test_ffuf_wordlist, "w") as f: f.write("admin\nlogin\n.git\nrobots.txt\n")
    # print("\n--- ffuf Test ---")
    # ffuf_test_results = run_ffuf("http://testphp.vulnweb.com", test_ffuf_wordlist, extensions=[""], output_format="json")
    # print(json.dumps(ffuf_test_results, indent=2))

    # print("\n--- Sublist3r Test (example.com) ---")
    # sublist3r_test_results = run_sublist3r("example.com")
    # print(json.dumps(sublist3r_test_results, indent=2))

    # print("\n--- SubDomainizer Test (http://example.com) ---")
    # subdomainizer_test_results = run_subdomainizer("http://example.com")
    # print(json.dumps(subdomainizer_test_results, indent=2))
    pass