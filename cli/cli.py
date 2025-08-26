import click
import json
from pathlib import Path
import subprocess
import os

# -----------------------------
# Paths
# -----------------------------
BASE_PATH = Path(os.getenv("REPO_BASE_PATH"))
SOURCE_FILE = BASE_PATH / "lab-lab01.json"
TARGET_FILE = BASE_PATH / "qa-qa01.json"

# -----------------------------
# Helper Functions
# -----------------------------
def git_commit_push(repo_path: Path, file_path: Path, commit_message: str):
    """Commit and push a file to Git in the given repository."""
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
        click.echo("❌ Commit and push cancelled. File remains updated.")


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
    """Update QA JSON with version from LAB JSON for a given service and optionally commit/push."""
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

    # Update QA JSON immediately
    qa_services = qa_data.setdefault("services", {})
    old_version = qa_services.get(service)
    qa_services[service] = lab_version

    # Save QA JSON
    with TARGET_FILE.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file updated: {TARGET_FILE}")
    click.echo(f"⚡ {service}: {old_version or 'not present'} → {lab_version}")
    click.echo("You can now run `git status` outside the CLI to review changes.")

    # Ask user confirmation to commit & push
    commit_message = f"Promote {service} to QA: {lab_version}"
    git_commit_push(BASE_PATH, TARGET_FILE, commit_message)


def main():
    cli()


if __name__ == "__main__":
    main()
