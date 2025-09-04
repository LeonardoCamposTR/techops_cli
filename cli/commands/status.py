#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from pathlib import Path
import requests
import click

# =========================
# 🔧 Configurations
# =========================
REPO_URL = "git@github.com:tr/a202606_mastersafdevops-tools-builder.git"
BRANCH = "feature/0.13.0-onviobr-ami-baking"  # Hardcoded branch
LOCAL_REPO_PATH = Path("/tmp/techops_status_repo")
CONFIG_SUBPATH = "onviobr/resources/nginx/etc/nginx/locations"

# ENVIRONMENTS
ENVIRONMENTS = ["lab", "qa", "sat", "prod"]

# Default suffixes
DEFAULT_SUFFIXES = ["v1/statuscheck", "v1/resourcecheck", "v1/resourceinspect"]
# Special suffixes for bremployeeportal
BREMPL_SUFFIXES = ["healthcheck"]

# Regex to extract nginx locations
LOCATION_REGEX = re.compile(r'location\s+([^\s{]+)')

TIMEOUT = 5

# =========================
# 📝 Functions
# =========================
def git_clone_or_update():
    """Clone repo if missing, else pull latest branch"""
    if LOCAL_REPO_PATH.exists():
        print(f"📦 Repo exists, pulling latest changes in {BRANCH} branch...")
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "fetch"], check=True)
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "checkout", BRANCH], check=True)
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "pull", "origin", BRANCH], check=True)
    else:
        print(f"📦 Cloning repo {REPO_URL} into {LOCAL_REPO_PATH}...")
        subprocess.run(["git", "clone", "-b", BRANCH, REPO_URL, str(LOCAL_REPO_PATH)], check=True)

def find_error_line(text):
    keywords = ['FAILED', 'ERROR', 'CRITICAL']
    pattern = re.compile(r'(' + '|'.join(keywords) + r')', re.IGNORECASE)
    for line in text.splitlines():
        if pattern.search(line):
            return line.strip()
    return None

# =========================
# 💻 CLI Entry
# =========================
@click.command()
@click.argument("services", nargs=-1, required=True)
def status(services):
    """Check status of multiple services across all environments"""
    git_clone_or_update()

    config_folder = LOCAL_REPO_PATH / CONFIG_SUBPATH

    output = {}
    error_5xx_counts = {}
    error_404_counts = {}
    content_error_counts = {}
    error_details = {}
    services_with_5xx = set()
    total_services = len(services)
    service_ok_count = 0

    # Determine suffixes per service
    service_suffix_map = {}
    for svc in services:
        if svc.lower().startswith("bremployeeportal"):
            service_suffix_map[svc] = BREMPL_SUFFIXES
        else:
            service_suffix_map[svc] = DEFAULT_SUFFIXES
        # Initialize error counters per suffix
        for suffix in service_suffix_map[svc]:
            error_5xx_counts[suffix] = 0
            error_404_counts[suffix] = 0
            content_error_counts[suffix] = 0
            error_details[suffix] = []

    # Iterate services
    for svc in services:
        matching_files = [f for f in os.listdir(config_folder)
                          if f.lower().startswith(svc.lower()) and f.endswith(".conf")]

        if not matching_files:
            print(f"⚠️ No config file found for service {svc}")
            continue

        for filename in matching_files:
            file_path = config_folder / filename

            # Determine internal/external type
            if "extern" in filename.lower():
                is_external = True
            elif "intern" in filename.lower():
                is_external = False
            else:
                print(f"⚠️ File {filename} doesn't specify internal/external, skipping.")
                continue

            with open(file_path, "r") as f:
                content = f.read()

            matches = LOCATION_REGEX.findall(content)
            api_locations = [loc.strip() for loc in matches if loc.strip().startswith("/")]

            if api_locations:
                urls = []
                for base_location in api_locations:
                    for suffix in service_suffix_map[svc]:
                        for env in ENVIRONMENTS:
                            # Build URL prefix
                            if env == "prod":
                                prefix = "https://onvio.com.br" if is_external else "https://int.onvio.com.br"
                            else:
                                prefix = f"https://{env}01.onvio.com.br"
                            urls.append(f"{prefix}{base_location}{suffix}")
                output[svc] = urls
            else:
                print(f"⚠️ No /api location found in {filename}")

    # =========================
    # 🌐 Perform HTTP Requests
    # =========================
    print("\n🔍 Request Results:\n")

    for svc, urls in output.items():
        service_has_error = False
        print(f"{svc}:")
        suffixes = service_suffix_map[svc]

        for url in urls:
            matched_suffix = next((s for s in suffixes if url.endswith(s)), None)
            try:
                response = requests.get(url, timeout=TIMEOUT)
                status_code = response.status_code
                text = response.text.strip()

                if status_code == 200:
                    err_line = find_error_line(text)
                    if err_line:
                        print(f"  {url} - ⚠️ FAILED in response")
                        print(f"    Line: {err_line}")
                        if matched_suffix:
                            content_error_counts[matched_suffix] += 1
                            error_details[matched_suffix].append((svc, url, "FAILED in response", err_line))
                        service_has_error = True
                    else:
                        print(f"  {url} - ✅ OK")
                elif status_code == 404:
                    print(f"  {url} - ❌ HTTP 404 NOT FOUND")
                    if matched_suffix:
                        error_404_counts[matched_suffix] += 1
                        error_details[matched_suffix].append((svc, url, "HTTP 404", None))
                    service_has_error = True
                elif 500 <= status_code <= 599:
                    print(f"  {url} - ❌ HTTP {status_code} (Server Error)")
                    if matched_suffix:
                        error_5xx_counts[matched_suffix] += 1
                        error_details[matched_suffix].append((svc, url, f"HTTP {status_code}", None))
                    service_has_error = True
                    services_with_5xx.add(svc)
                else:
                    print(f"  {url} - ❌ HTTP {status_code}")
                    if matched_suffix:
                        error_details[matched_suffix].append((svc, url, f"HTTP {status_code}", None))
                    service_has_error = True

            except requests.exceptions.RequestException as e:
                print(f"  {url} - ❌ CONNECTION ERROR ({e})")
                service_has_error = True
                if matched_suffix:
                    error_details[matched_suffix].append((svc, url, f"CONNECTION ERROR ({e})", None))

        print()
        if not service_has_error:
            service_ok_count += 1

    # =========================
    # 📝 Pretty Report
    # =========================
    success_percent = (service_ok_count / total_services) * 100 if total_services else 0

    print("\n==========================")
    print(f"📝 PRETTY REPORT")
    print("==========================\n")
    print(f"Total services: {total_services}")
    print(f"Success: {service_ok_count}/{total_services} ({success_percent:.2f}%)")
    print("---------------------------------------------")

    for suffix in set(s for sl in service_suffix_map.values() for s in sl):
        err_5xx = error_5xx_counts[suffix]
        err_404 = error_404_counts[suffix]
        print(f"{suffix} errors (500-599): {err_5xx}/{total_services} | Not Found (404): {err_404}/{total_services}")
    print("---------------------------------------------")

    if services_with_5xx:
        print("❌ Services with 500+ errors:")
        for s in sorted(services_with_5xx):
            print(f"- {s}")
    else:
        print("✅ No services with 500+ errors")
    print("==============================================")

if __name__ == "__main__":
    status()
