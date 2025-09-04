import shutil
import subprocess
import requests
from pathlib import Path

# =========================
# CONFIGURATION
# =========================
REPO_URL = "git@github.com:yourorg/yourrepo.git"
BRANCH = "develop"  # Hardcoded branch
LOCAL_REPO_PATH = Path("/tmp/techops_status_repo")
CONFIG_SUBPATH = "resources/nginx/etc/nginx/locations"
TIMEOUT = 5

ENVIRONMENTS = ["lab", "qa", "sat", "prod"]

SERVICE_PREFIXES = {
    "lab": "lab01",
    "qa": "qa01",
    "sat": "sat01",
}

PROD_URLS = {
    "external": "https://onvio.com.br",
    "internal": "https://int.onvio.com.br"
}

SUFFIXES = ["healthcheck"]

# =========================
# HELPER FUNCTIONS
# =========================
def clone_repo():
    if LOCAL_REPO_PATH.exists():
        shutil.rmtree(LOCAL_REPO_PATH)
    subprocess.run(["git", "clone", REPO_URL, str(LOCAL_REPO_PATH)], check=True)
    subprocess.run(["git", "checkout", BRANCH], cwd=str(LOCAL_REPO_PATH), check=True)
    subprocess.run(["git", "pull"], cwd=str(LOCAL_REPO_PATH), check=True)

def find_nginx_files(service_name):
    config_path = LOCAL_REPO_PATH / CONFIG_SUBPATH
    matching_files = []
    for f in config_path.glob(f"{service_name}*"):
        # Skip suffixes if service starts with bremployeeportal
        if service_name.startswith("bremployeeportal") and any(f.name.endswith(suffix) for suffix in SUFFIXES):
            continue
        if f.is_file():
            matching_files.append(f)
    return matching_files

def parse_locations(file_path):
    locations = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("location"):
                # Simple parsing of nginx location block
                parts = line.split()
                if len(parts) >= 2:
                    url = parts[1].rstrip(";")
                    locations.append(url)
    return locations

def build_urls(service_name, location):
    urls = []
    for env in ENVIRONMENTS:
        if env in SERVICE_PREFIXES:
            prefix = SERVICE_PREFIXES[env]
            urls.append(f"https://{prefix}.onvio.com.br{location}")
        elif env == "prod":
            urls.append(f"{PROD_URLS['external']}{location}")
            urls.append(f"{PROD_URLS['internal']}{location}")
    return urls

def find_error_line(html_text):
    # Customize if needed; basic example: detect "<error>"
    return "<error>" in html_text.lower()

# =========================
# MAIN FUNCTION
# =========================
def status_services(service_names):
    clone_repo()
    report = {env: {} for env in ENVIRONMENTS}

    for service in service_names:
        files = find_nginx_files(service)
        for f in files:
            locations = parse_locations(f)
            urls = []
            for loc in locations:
                urls.extend(build_urls(service, loc))
            # Store urls by environment
            for env in ENVIRONMENTS:
                env_urls = [u for u in urls if f"{env}" in u or env == "prod"]
                if service not in report[env]:
                    report[env][service] = []
                report[env][service].extend(env_urls)

    # =========================
    # REPORTING
    # =========================
    for env in ENVIRONMENTS:
        print(f"\n============================")
        print(f"🌐 Environment: {env.upper()}")
        print("============================")
        
        env_services = report.get(env, {})
        env_ok_services = 0
        env_failed_services = 0
        
        for svc, urls in env_services.items():
            ok_count = 0
            fail_count = 0
            print(f"\n📌 Service: {svc}")
            print(f"{'URL':70} | STATUS")
            print("-" * 85)
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=TIMEOUT)
                    status_code = response.status_code
                    text = response.text.strip()
                    if status_code == 200:
                        if find_error_line(text):
                            status = "⚠️ FAILED"
                            fail_count += 1
                        else:
                            status = "✅ OK"
                            ok_count += 1
                    elif status_code == 404:
                        status = "❌ 404 NOT FOUND"
                        fail_count += 1
                    elif 500 <= status_code <= 599:
                        status = f"❌ HTTP {status_code}"
                        fail_count += 1
                    else:
                        status = f"❌ HTTP {status_code}"
                        fail_count += 1
                except requests.exceptions.RequestException:
                    status = f"❌ CONNECTION ERROR"
                    fail_count += 1
                print(f"{url:70} | {status}")
            
            print(f"\nSummary for {svc}: ✅ OK: {ok_count} | ❌ Failed: {fail_count}")
            if fail_count == 0:
                env_ok_services += 1
            else:
                env_failed_services += 1

        # Environment summary
        total_services = env_ok_services + env_failed_services
        success_percent = (env_ok_services / total_services * 100) if total_services else 0
        print("\n-----------------------------")
        print(f"🌟 Environment Summary ({env.upper()}):")
        print(f"Total services: {total_services}")
        print(f"✅ OK: {env_ok_services}")
        print(f"❌ Failed: {env_failed_services}")
        print(f"Success rate: {success_percent:.2f}%")
        print("-----------------------------\n")

    # Cleanup
    if LOCAL_REPO_PATH.exists():
        shutil.rmtree(LOCAL_REPO_PATH)
