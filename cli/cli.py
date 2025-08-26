import click
import json
from pathlib import Path
import subprocess
import shutil

# -----------------------------
# Paths
# -----------------------------
BASE_PATH = Path("/home/leonardoscampos/gits/a202606_mastersafdevops-apidata/onviobr/deployer")
SOURCE_FILE = BASE_PATH / "lab-lab01.json"
TARGET_FILE = BASE_PATH / "qa-qa01.json"

# -----------------------------
# Helper Functions
# -----------------------------
def git_commit_push(repo_path: Path, file_path: Path, commit_message: str):
    """Add, commit, and push a file to Git in the given repository, with confirmation.
       Reverts file if user cancels."""
    
    # Backup file
    backup_file = file_path.with_suffix(file_path.suffix + ".bak")
    shutil.copy(file_path, backup_file)
    
    click.echo(f"⚡ About to commit and push {file_path} with message:\n  '{commit_message}'")
    if click.confirm("Do you want to proceed?", default=True):
        try:
            subprocess.run(["git", "-C", str(repo_path), "add", str(file_path)], check=True)
            subprocess.run(["git", "-C", str(repo_path), "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "-C", str(repo_path), "push"], check=True)
            click.echo(f"🚀 Changes committed and pushed to Git: {commit_message}")
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Git command failed: {e}")
    else:
        # Revert file from backup
        shutil.move(backup_file, file_path)
        click.echo(f"❌ Commit and push cancelled. Changes reverted for {file_path}.")
        return
    
    # Remove backup if commit succeeded
    if backup_file.exists():
        backup_file.unlink()


# -----------------------------
# CLI Definition
# -----------------------------
@click.group()
def cli():
    """🚀 DevOps CLI - Utilities for environment setup & troubleshooting."""
    pass


# -----------------------------
# Promoting to QA
# -----------------------------
@cli.command()
@click.argument("service")
def promoting_qa(service):
    """Update QA JSON with version from LAB JSON for a given service and push to Git."""
    if not SOURCE_FILE.exists():
        click.echo(f"❌ LAB file not found: {SOURCE_FILE}")
        return
    if not TARGET_FILE.exists():
        click.echo(f"❌ QA file not found: {TARGET_FILE}")
        return

    # Load LAB JSON
    with SOURCE_FILE.open() as f:
        lab_data = json.load(f)

    # Load QA JSON
    with TARGET_FILE.open() as f:
        qa_data = json.load(f)

    # Get version from LAB
    lab_version = lab_data.get("services", {}).get(service)
    if not lab_version:
        click.echo(f"❌ Service '{service}' not found in LAB file.")
        return

    # Update QA JSON
    qa_services = qa_data.setdefault("services", {})
    old_version = qa_services.get(service)
    qa_services[service] = lab_version

    if old_version:
        click.echo(f"✅ Service '{service}' updated in QA: {old_version} → {lab_version}")
    else:
        click.echo(f"ℹ Service '{service}' added to QA with version {lab_version}")

    # Save QA JSON
    with TARGET_FILE.open("w") as f:
        json.dump(qa_data, f, indent=2)
    click.echo(f"💾 QA file saved: {TARGET_FILE}")

    # Commit & push using reusable function
    commit_message = f"Promote {service} to QA: {lab_version}"
    git_commit_push(BASE_PATH, TARGET_FILE, commit_message)


def main():
    cli()


if __name__ == "__main__":
    main()
