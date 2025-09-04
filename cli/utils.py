import subprocess
import click
import json
import tempfile
import shutil
from pathlib import Path

REPO_URL = "github.com/leonardoscampos/apidata.git"
REPO_SUBDIR = "onviobr/deployer"

def run_cmd(cmd, cwd=None, check=True, capture_output=False):
    result = subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=capture_output)
    return result.stdout.strip() if capture_output else None

def git_commit_push(repo_path: Path, files: list[str], commit_message: str):
    click.echo(f"⚡ About to commit and push:\n{commit_message}")
    run_cmd(["git", "add"] + files, cwd=repo_path)
    run_cmd(["git", "commit", "-m", commit_message], cwd=repo_path)
    run_cmd(["git", "push"], cwd=repo_path)

def promote_services(services, source_file, target_file):
    # 🔁 paste your promote logic here (same as before)
    pass

def run_aws_cli(command: list) -> dict:
    try:
        result = subprocess.run(
            ["aws"] + command + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ AWS CLI command failed: {e.stderr}")
        raise
