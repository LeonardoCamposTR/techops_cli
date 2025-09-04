#!/usr/bin/env python3
import os
import re
import subprocess
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

def build_service_urls(service, base_locations, suffixes, is_external):
    urls = []
    for env in ENVIRONMENTS:
        prefix = ""
        if env == "prod":
            prefix_external = "https://onvio.com.br"
            prefix_internal = "https://int.onvio.com.br"
            prefix = prefix_external if is_external else prefix_internal
        else:
            prefix = f"https://{env}01.onvio.com.br"
        for loc in base_locations:
            for suffix in suffixes:
                urls.append((env, f"{prefix}{loc}{suffix}"))
    return urls

def print_env_report(report):
    """Print a clean professional report"""
    for env in ENVIRONMENTS:
        print(f"\n{'='*60}")
        print(f"🌐 ENVIRONMENT: {env.upper()}")
        print(f"{'='*60}")
        env_services = report.get(env, {})
        for svc, urls in env_services.items():
            print(f"\n📌 Service: {svc}")
            print(f"{'URL':60} | STATUS")
            print("-"*80)
            ok_count = 0
            fail_count = 0
            for url in urls:
                try:
                    response = requests.get(url, timeout=TIMEOUT)
                    status_code = response.status_code
                    text = response.text.strip()
                    if status_code == 200:
                        err_line = find_error_line(text)
                        if err_line:
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
                    status = "❌ CONNECTION ERROR"
                    fail_count += 1
                print(f"{url:60} | {status}")
            print(f"\nSummary for {svc}: ✅ OK: {ok_count} | ❌ Failed: {fail_count}")
        print(f"{'-'*60}")

# =========================
# 💻 CLI Entry
# =========================
@click.command()
@click.argument("services", nargs=-1, required=True)
def status(services):
    """Check status of multiple services across all environments"""
    git_clone_or_update()
    config_folder = LOCAL_REPO_PATH / CONFIG_SUBPATH

    report = {env: {} for env in ENVIRONMENTS}

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

        for filename in matching_files:
            file_path = config_folder / filename
            is_external = "extern" in filename.lower()

            with open(file_path, "r") as f:
                content = f.read()

            base_locations = [loc.strip() for loc in LOCATION_REGEX.findall(content) if loc.strip().startswith("/")]
            if not base_locations:
                print(f"⚠️ No /api location found in {filename}")
                continue

            urls = build_service_urls(svc, base_locations, service_suffix_map[svc], is_external)

            # Fill report
            for env, url in urls:
                if svc not in report[env]:
                    report[env][svc] = []
                report[env][svc].append(url)

    # Print professional report
    print_env_report(report)

    # Cleanup
    if LOCAL_REPO_PATH.exists():
        shutil.rmtree(LOCAL_REPO_PATH)
        print(f"\n🧹 Cleaned up local repo {LOCAL_REPO_PATH}")

if __name__ == "__main__":
    status()
