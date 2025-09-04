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
        # 🌐 Perform HTTP Requests
        # =========================
        print("\n🔍 Request Results:\n")

        for svc, env_data in results.items():
            print(f"{svc}:")
            for env, urls in env_data.items():
                print(f"  [{env}]")
                for url in urls.keys():
                    try:
                        response = requests.get(url, timeout=TIMEOUT)
                        status_code = response.status_code
                        text = response.text.strip()
                        urls[url]["status"] = status_code

                        if status_code == 200:
                            err_line = find_error_line(text)
                            if err_line:
                                urls[url]["error_line"] = err_line
                                print(f"    {url} - ⚠️ FAILED in response")
                                print(f"       Line: {err_line}")
                            else:
                                print(f"    {url} - ✅ OK")
                        elif status_code == 404:
                            print(f"    {url} - ❌ HTTP 404 NOT FOUND")
                        elif 500 <= status_code <= 599:
                            print(f"    {url} - ❌ HTTP {status_code} (Server Error)")
                            services_with_5xx.add(svc)
                        else:
                            print(f"    {url} - ❌ HTTP {status_code}")

                    except requests.exceptions.RequestException as e:
                        urls[url]["status"] = "CONNECTION ERROR"
                        print(f"    {url} - ❌ CONNECTION ERROR ({e})")
                        services_with_5xx.add(svc)

        # =========================
        # 📝 Pretty Report by Environment
        # =========================
        print("\n==========================")
        print("📝 REPORT BY ENVIRONMENT")
        print("==========================\n")

        for env in ENVIRONMENTS:
            print(f"Environment: {env.upper()}")
            for svc, env_data in results.items():
                if env in env_data:
                    urls = env_data[env]
                    for url, info in urls.items():
                        status = info["status"]
                        err_line = info.get("error_line")
                        line_info = f" - {err_line}" if err_line else ""
                        print(f"  {svc}: {url} - {status}{line_info}")
            print("---------------------------------------------")

        if services_with_5xx:
            print("❌ Services with 500+ errors:")
            for s in sorted(services_with_5xx):
                print(f"- {s}")
        else:
            print("✅ No services with 500+ errors")
        print("==============================================")

    finally:
        # Always cleanup the repo
        cleanup_repo()

if __name__ == "__main__":
    status()
