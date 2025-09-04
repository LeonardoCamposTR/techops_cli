#!/usr/bin/env python3
import click
import subprocess
import re
from pathlib import Path
import requests

# =========================
# 🔧 Configurations
# =========================

# Hardcoded repo and branch
REPO_PATH = Path("/home/leonardoscampos/gits/a202606_mastersafdevops-tools-builder/onviobr/resources/nginx")
BRANCH = "main"  # specify the branch you want

CONFIG_FOLDER = REPO_PATH / "etc/nginx/locations"

# Default suffixes
SUFFIXES = [
    "v1/statuscheck",
    "v1/resourcecheck",
    "v1/resourceinspect"
]

# Environments
ENVS = ["lab", "qa", "sat", "prod"]

# Regex to extract nginx location blocks
location_regex = re.compile(r'location\s+([^\s{]+)')

# Request timeout
TIMEOUT = 5

# =========================
# 🔍 Helper Functions
# =========================

def git_pull_branch(repo_path: Path, branch: str):
    if not repo_path.exists():
        raise RuntimeError(f"Repository path does not exist: {repo_path}")

    # Ensure we are on the branch
    subprocess.run(["git", "-C", str(repo_path), "fetch"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "checkout", branch], check=True)
    subprocess.run(["git", "-C", str(repo_path), "pull"], check=True)
    print(f"✅ Pulled latest changes for branch '{branch}'")

def find_error_line(text):
    keywords = ['FAILED', 'ERROR', 'CRITICAL']
    pattern = re.compile(r'(' + '|'.join(keywords) + r')', re.IGNORECASE)
    for line in text.splitlines():
        if pattern.search(line):
            return line.strip()
    return None

# =========================
# 🟢 CLI Command
# =========================

@click.command()
@click.argument("service_names", nargs=-1, required=True)
def status(service_names):
    """
    Check status for one or more services.
    Example:
      techops status service1 service2
    """
    # Pull latest branch
    git_pull_branch(REPO_PATH, BRANCH)

    for service_name in service_names:
        service_name = service_name.lower()
        click.echo(f"\n✅ Checking status for service: {service_name}")

        output = {}

        # Dynamic suffixes for special services
        suffixes = SUFFIXES
        if service_name.startswith("bremployeeportal"):
            suffixes = ["healthcheck"]

        # Find relevant .conf files
        for filename in CONFIG_FOLDER.iterdir():
            if not filename.name.endswith(".conf"):
                continue
            if not filename.name.lower().startswith(service_name):
                continue

            with open(filename, "r") as f:
                content = f.read()

            matches = location_regex.findall(content)
            api_locations = [loc.strip() for loc in matches if loc.strip().startswith("/")]

            if api_locations:
                urls = []
                for env in ENVS:
                    if "extern" in filename.name.lower():
                        prefix = f"https://{env}01.onvio.com.br"
                    elif "intern" in filename.name.lower():
                        prefix = f"https://{env}01.int.onvio.com.br"
                    else:
                        continue
                    for base_location in api_locations:
                        for suffix in suffixes:
                            urls.append(f"{prefix}{base_location}{suffix}")
                output[filename.name] = urls
            else:
                click.echo(f"⚠️ No /api location found in {filename.name}")

        # Make HTTP requests
        for conf_file, urls in output.items():
            click.echo(f"\nFile: {conf_file}")
            for url in urls:
                matched_suffix = next((s for s in suffixes if url.endswith(s)), None)
                try:
                    response = requests.get(url, timeout=TIMEOUT)
                    status_code = response.status_code
                    text = response.text.strip()

                    if status_code == 200:
                        error_line = find_error_line(text)
                        if error_line:
                            click.echo(f"  {url} - ⚠️ FAILED in response: {error_line}")
                        else:
                            click.echo(f"  {url} - ✅ OK")
                    elif status_code == 404:
                        click.echo(f"  {url} - ❌ HTTP 404 NOT FOUND")
                    elif 500 <= status_code <= 599:
                        click.echo(f"  {url} - ❌ HTTP {status_code} (Server Error)")
                    else:
                        click.echo(f"  {url} - ❌ HTTP {status_code}")

                except requests.exceptions.RequestException as e:
                    click.echo(f"  {url} - ❌ CONNECTION ERROR ({e})")

if __name__ == "__main__":
    status()
