#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import shutil
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

def cleanup_repo():
    """Remove cloned repository"""
    if LOCAL_REPO_PATH.exists():
        print(f"🧹 Removing local repo at {LOCAL_REPO_PATH}...")
        shutil.rmtree(LOCAL_REPO_PATH)

# =========================
# 💻 CLI Entry
# =========================
@click.command()
@click.argument("services", nargs=-1, required=True)
def status(services):
    """Check status of multiple services across all environments"""
    try:
        git_clone_or_update()

        config_folder = LOCAL_REPO_PATH / CONFIG_SUBPATH

        # Store results structured by service -> environment -> url -> status
        results = {}
        services_with_5xx = set()

        # Determine suffixes per service
        service_suffix_map = {}
        for svc in services:
            if svc.lower().startswith("bremployeeportal"):
                service_suffix_map[svc] = BREMPL_SUFFIXES
            else:
                service_suffix_map[svc] = DEFAULT_SUFFIXES

        # Iterate services
        for svc in services:
            matching_files = [f for f in os.listdir(config_folder)
                              if f.lower().startswith(svc.lower()) and f.endswith(".conf")]

            if not matching_files:
                print(f"⚠️ No config file found for service {svc}")
                continue

            results[svc] = {}

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

                if not api_locations:
                    print(f"⚠️ No /api location found in {filename}")
                    continue

                # Prepare environment URLs
                for env in ENVIRONMENTS:
                    if env not in results[svc]:
                        results[svc][env] = {}

                    for base_location in api_locations:
                        for suffix in service_suffix_map[svc]:
                            if env == "prod":
                                prefix = "https://onvio.com.br" if is_external else "https://int.onvio.com.br"
                            else:
                                prefix = f"https://{env}01.onvio.com.br"
                            url = f"{prefix}{base_location}{suffix}"
                            results[svc][env][url] = {"status": None, "error_line": None}

        # =========================
        # 🌐 Perform HTTP Requests and organize by environment
        # =========================
        results = {}  # Structure: { service: { env: { url: {status, error_line} } } }

        for svc, urls in output.items():
            results[svc] = {}
            suffixes = service_suffix_map[svc]
            for url in urls:
                env = next((e for e in ENVIRONMENTS if e in url.lower()), "prod")  # crude env detection
                if env not in results[svc]:
                    results[svc][env] = {}

                matched_suffix = next((s for s in suffixes if url.endswith(s)), None)
                info = {"status": None, "error_line": None}

                try:
                    response = requests.get(url, timeout=TIMEOUT)
                    info["status"] = response.status_code
                    if response.status_code == 200:
                        err_line = find_error_line(response.text)
                        info["error_line"] = err_line
                except requests.exceptions.RequestException as e:
                    info["status"] = f"CONNECTION ERROR ({e})"

                results[svc][env][url] = info

        # =========================
        # 📝 Pretty Report: Detailed + Environment Summary
        # =========================
        service_ok_count = 0
        total_services = len(results)

        print("\n==========================")
        print("🔍 DETAILED URL REPORT")
        print("==========================\n")

        for svc, env_data in results.items():
            print(f"{svc}:")
            service_has_error = False
            for env, urls_info in env_data.items():
                print(f"  [{env.upper()}]")
                for url, info in urls_info.items():
                    status = info["status"]
                    err_line = info.get("error_line")
                    if status == 200 and not err_line:
                        print(f"    {url} - ✅ OK")
                    elif isinstance(status, int) and 500 <= status <= 599:
                        print(f"    {url} - ❌ HTTP {status} (Server Error)")
                        service_has_error = True
                    elif status == 404:
                        print(f"    {url} - ❌ HTTP 404 NOT FOUND")
                        service_has_error = True
                    elif err_line:
                        print(f"    {url} - ⚠️ FAILED in response")
                        print(f"      Line: {err_line}")
                        service_has_error = True
                    else:
                        print(f"    {url} - ❌ {status}")
                        service_has_error = True
                print()
            if not service_has_error:
                service_ok_count += 1

        # =========================
        # 🌐 Summary by environment
        # =========================
        print("\n==========================")
        print("📊 SUMMARY BY ENVIRONMENT")
        print("==========================\n")

        for env in ENVIRONMENTS:
            total_ok = total_5xx = total_404 = total_failed_content = 0
            for svc, env_data in results.items():
                if env not in env_data:
                    continue
                for url, info in env_data[env].items():
                    status = info["status"]
                    err_line = info.get("error_line")
                    if status == 200 and not err_line:
                        total_ok += 1
                    elif isinstance(status, int) and 500 <= status <= 599:
                        total_5xx += 1
                    elif status == 404:
                        total_404 += 1
                    elif err_line:
                        total_failed_content += 1
            print(f"Environment: {env.upper()}")
            print(f"  ✅ OK URLs: {total_ok}")
            print(f"  ❌ 5xx Errors: {total_5xx}")
            print(f"  ❌ 404 Errors: {total_404}")
            print(f"  ⚠️ Failed Content: {total_failed_content}")
            print("---------------------------------------------")
            
    finally:
        # Always cleanup the repo
        cleanup_repo()

if __name__ == "__main__":
    status()
