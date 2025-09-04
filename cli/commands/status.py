# cli/commands/status.py
import os
import re
import subprocess
from pathlib import Path
import click
import requests

REPO_URL = "git@github.com:yourorg/yourrepo.git"
BRANCH = "develop"  # Hardcoded branch
LOCAL_REPO_PATH = Path("/tmp/techops_status_repo")
CONFIG_SUBPATH = "resources/nginx/etc/nginx/locations"
SUFFIXES = [
    "v1/statuscheck",
    "v1/resourcecheck",
    "v1/resourceinspect"
]
ENVS = ["lab", "qa", "sat", "prod"]
TIMEOUT = 5

location_regex = re.compile(r'location\s+([^\s{]+)')

def run_cmd(cmd, cwd=None, check=True, capture_output=False):
    """Run a shell command."""
    result = subprocess.run(
        cmd, cwd=cwd, check=check, text=True,
        capture_output=capture_output
    )
    return result.stdout.strip() if capture_output else None

def clone_or_pull_repo():
    """Clone repo if not exists, otherwise pull changes and switch to branch."""
    if LOCAL_REPO_PATH.exists():
        click.echo("📂 Repo exists, pulling latest changes...")
        run_cmd(["git", "fetch"], cwd=LOCAL_REPO_PATH)
        run_cmd(["git", "checkout", BRANCH], cwd=LOCAL_REPO_PATH)
        run_cmd(["git", "pull", "origin", BRANCH], cwd=LOCAL_REPO_PATH)
    else:
        click.echo(f"📥 Cloning repo into {LOCAL_REPO_PATH} ...")
        run_cmd(["git", "clone", "-b", BRANCH, REPO_URL, str(LOCAL_REPO_PATH)])
    return LOCAL_REPO_PATH

@click.command("status")
@click.argument("service_names", nargs=-1)  # multiple services
def status(service_names):
    """Check status for one or more services across all environments."""
    if not service_names:
        click.echo("❌ Please provide at least one service name.")
        return

    click.echo(f"🔄 Preparing repository on branch: {BRANCH}")
    config_folder = clone_or_pull_repo() / CONFIG_SUBPATH

    for service_name in service_names:
        service_name = service_name.lower()
        click.echo(f"\n✅ Checking status for service: {service_name}")

        output = {}

        for filename in os.listdir(config_folder):
            if not filename.endswith(".conf"):
                continue
            if not filename.lower().startswith(service_name):
                continue

            file_path = config_folder / filename
            with open(file_path, "r") as f:
                content = f.read()

            matches = location_regex.findall(content)
            api_locations = [loc.strip() for loc in matches if loc.strip().startswith("/")]

            if api_locations:
                urls = []
                for env in ENVS:
                    if "extern" in filename.lower():
                        prefix = f"https://{env}01.onvio.com.br"
                    elif "intern" in filename.lower():
                        prefix = f"https://{env}01.int.onvio.com.br"
                    else:
                        continue
                    for base_location in api_locations:
                        for suffix in SUFFIXES:
                            urls.append(f"{prefix}{base_location}{suffix}")
                output[filename] = urls

        if not output:
            click.echo(f"⚠️ No matching config files found for {service_name}")
            continue

        # make requests
        click.echo("\n🔍 Request Results:\n")
        for fname, urls in output.items():
            click.echo(f"{fname}:")
            for url in urls:
                try:
                    r = requests.get(url, timeout=TIMEOUT)
                    status = r.status_code
                    if status == 200:
                        click.echo(f"  {url} - ✅ OK")
                    else:
                        click.echo(f"  {url} - ❌ HTTP {status}")
                except requests.exceptions.RequestException as e:
                    click.echo(f"  {url} - ❌ CONNECTION ERROR ({e})")
            click.echo()
