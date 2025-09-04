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
BRANCH = "feature/0.13.0-onviobr-ami-baking"
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
    """Search for FAILED/ERROR/CRITICAL in response body"""
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

    # Initialize outputs per environment
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
                for env in ENVIRONMENTS:
                    if env not in report:
                        report[env] = {}
                    report_env = report[env]
                    if svc not in report_env:
                        report_env[svc] = []
                    for base_location in api_locations:
                        for suffix in service_suffix_map[svc]:
                            # Build URL prefix
                            if env == "prod":
                                prefix = "https://onvio.com.br" if is_external else "https://int.onvio.com.br"
                            else:
                                prefix = f"https://{env}01.onvio.com.br"
                            url = f"{prefix}{base_location}{suffix}"
                            report_env[svc].append(url)
            else:
                print(f"⚠️ No /api location found in {filename}")

    # =========================
    # 🌐 Perform HTTP Requests & Print - Cleaned Professional Version
    # =========================
    for env in ENVIRONMENTS:
        print(f"\n============================")
        print(f"🌐 Environment: {env.upper()}")
        print("============================")

        env_services = report.get(env, {})
        if not env_services:
            print("⚠️ No services found for this environment")
            continue

        # Table header
        print(f"{'SERVICE':25} | {'OK':>5} | {'FAILED':>6}")
        print("-" * 45)

        for svc, urls in env_services.items():
            ok_count = 0
            fail_count = 0
            failed_urls = []

            for url in urls:
                try:
                    response = requests.get(url, timeout=TIMEOUT)
                    status_code = response.status_code
                    text = response.text.strip()
                    if status_code == 200 and not find_error_line(text):
                        ok_count += 1
                    else:
                        fail_count += 1
                        failed_urls.append(f"{url} ({status_code})")
                except requests.exceptions.RequestException:
                    fail_count += 1
                    failed_urls.append(f"{url} (CONNECTION ERROR)")

            # Print service summary
            print(f"{svc:25} | {ok_count:>5} | {fail_count:>6}")

            # Optional: print failed URLs only
            for fail_url in failed_urls:
                print(f"   ❌ {fail_url}")

    # =========================
    # 🧹 Cleanup
    # =========================
    if LOCAL_REPO_PATH.exists():
        shutil.rmtree(LOCAL_REPO_PATH)
        print(f"\n🧹 Cleaned up local repo {LOCAL_REPO_PATH}")

if __name__ == "__main__":
    status()
