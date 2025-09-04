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
REPO_URL = "git@github.com:yourorg/yourrepo.git"
BRANCH = "develop"  # Hardcoded branch
LOCAL_REPO_PATH = Path("/tmp/techops_status_repo")
CONFIG_SUBPATH = "resources/nginx/etc/nginx/locations"

ENVIRONMENTS = ["lab", "qa", "sat", "prod"]

DEFAULT_SUFFIXES = ["v1/statuscheck", "v1/resourcecheck", "v1/resourceinspect"]
BREMPL_SUFFIXES = ["healthcheck"]

LOCATION_REGEX = re.compile(r'location\s+([^\s{]+)')
TIMEOUT = 5

# =========================
# 📝 Functions
# =========================
def git_clone_or_update():
    if LOCAL_REPO_PATH.exists():
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "fetch"], check=True)
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "checkout", BRANCH], check=True)
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "pull", "origin", BRANCH], check=True)
    else:
        subprocess.run(["git", "clone", "-b", BRANCH, REPO_URL, str(LOCAL_REPO_PATH)], check=True)

def find_error_line(text):
    keywords = ['FAILED', 'ERROR', 'CRITICAL']
    pattern = re.compile(r'(' + '|'.join(keywords) + r')', re.IGNORECASE)
    for line in text.splitlines():
        if pattern.search(line):
            return line.strip()
    return None

def cleanup_repo():
    if LOCAL_REPO_PATH.exists():
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

        # Prepare error tracking per service, per env, per suffix
        report = {}
        for svc in services:
            report[svc] = {}
            suffixes = BREMPL_SUFFIXES if svc.lower().startswith("bremployeeportal") else DEFAULT_SUFFIXES
            for env in ENVIRONMENTS:
                report[svc][env] = {suf: [] for suf in suffixes}

        # Iterate services
        for svc in services:
            matching_files = [f for f in os.listdir(config_folder)
                              if f.lower().startswith(svc.lower()) and f.endswith(".conf")]
            if not matching_files:
                print(f"⚠️ No config file found for service {svc}")
                continue

            for filename in matching_files:
                file_path = config_folder / filename
                is_external = "extern" in filename.lower()
                is_internal = "intern" in filename.lower()

                if not (is_external or is_internal):
                    print(f"⚠️ File {filename} doesn't specify internal/external, skipping.")
                    continue

                with open(file_path, "r") as f:
                    content = f.read()

                matches = LOCATION_REGEX.findall(content)
                api_locations = [loc.strip() for loc in matches if loc.strip().startswith("/")]

                if not api_locations:
                    print(f"⚠️ No /api location found in {filename}")
                    continue

                suffixes = BREMPL_SUFFIXES if svc.lower().startswith("bremployeeportal") else DEFAULT_SUFFIXES

                # Build all URLs per environment & suffix
                urls_to_check = []
                for base_location in api_locations:
                    for suf in suffixes:
                        for env in ENVIRONMENTS:
                            if env == "prod":
                                prefix = "https://onvio.com.br" if is_external else "https://int.onvio.com.br"
                            else:
                                prefix = f"https://{env}01.onvio.com.br"
                            urls_to_check.append((env, suf, f"{prefix}{base_location}{suf}"))

                # HTTP Requests
                for env, suf, url in urls_to_check:
                    try:
                        resp = requests.get(url, timeout=TIMEOUT)
                        status_code = resp.status_code
                        text = resp.text.strip()
                        err_line = find_error_line(text) if status_code == 200 else None

                        if status_code == 200 and not err_line:
                            continue  # OK, no record
                        elif err_line:
                            report[svc][env][suf].append(f"FAILED in response: {err_line}")
                        elif status_code == 404:
                            report[svc][env][suf].append("HTTP 404 NOT FOUND")
                        elif 500 <= status_code <= 599:
                            report[svc][env][suf].append(f"HTTP {status_code} Server Error")
                        else:
                            report[svc][env][suf].append(f"HTTP {status_code}")

                    except requests.exceptions.RequestException as e:
                        report[svc][env][suf].append(f"CONNECTION ERROR ({e})")

        # =========================
        # 📝 Pretty Report per Environment
        # =========================
        print("\n==========================")
        print("📝 STATUS REPORT PER ENVIRONMENT")
        print("==========================\n")

        for svc, envs in report.items():
            print(f"Service: {svc}")
            for env, suf_dict in envs.items():
                print(f"  Environment: {env}")
                for suf, errors in suf_dict.items():
                    if errors:
                        for e in errors:
                            print(f"    {suf}: ❌ {e}")
                    else:
                        print(f"    {suf}: ✅ OK")
            print("-----------------------------------")

    finally:
        cleanup_repo()

if __name__ == "__main__":
    status()
