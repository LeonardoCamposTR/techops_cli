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
def validate_git_repo(repo_path: Path) -> bool:
    """Check if Git repo is clean and up to date with remote."""
    click.echo("🔍 Validating Git repository status...")

    try:
        # Fetch remote updates
        subprocess.run(["git", "-C", str(repo_path), "fetch"], check=True, capture_output=True)

        # 1. Check for uncommitted changes
        diff_result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain=v1"],
            check=True, capture_output=True, text=True
        )
        if diff_result.stdout.strip():
            click.echo("❌ Repository has uncommitted changes. Please commit or stash before proceeding.")
            return False

        # 2. Check for ahead/behind status
        local_rev = subprocess.check_output(["git", "-C", str(repo_path), "rev-parse", "@"]).strip()
        remote_rev = subprocess.check_output(["git", "-C", str(repo_path), "rev-parse", "@{u}"]).strip()
        base_rev = subprocess.check_output(["git", "-C", str(repo_path), "merge-base", "@", "@{u}"]).strip()

        if local_rev == remote_rev:
            click.echo("✅ Repository is clean and up to date.")
            return True
        elif local_rev == base_rev:
            click.echo("❌ Repository is behind remote. Please pull latest changes before proceeding.")
            return False
        elif remote_rev == base_rev:
            click.echo("❌ Repository has local commits not pushed. Please push before proceeding.")
            return False
        else:
            click.echo("❌ Repository has diverged from remote. Please resolve before proceeding.")
            return False

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to validate repository: {e}")
        return False
    except subprocess.SubprocessError as e:
        click.echo(f"❌ Git check failed: {e}")
        return False


def git_commit_push_or_revert(repo_path: Path, file_path: Path, commit_message: str):
    """Commit and push a file to Git or revert if user declines."""
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
        click.echo("❌ Commit cancelled. Reverting changes...")
        try:
            subprocess.run(["git", "-C", str(repo_path), "restore", str(file_path)], check=True)
            click.echo(f"♻️  Changes reverted: {file_path}")
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Failed to revert changes: {e}")

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
    """Update QA JSON with version from LAB JSON for a given service (case-insensitive) and optionally commit/push."""

    # 🔒 Validate repo first
    if not validate_git_repo(BASE_PATH):
        return

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

    lab_services = lab_data.get("services", {})
    qa_services = qa_data.setdefault("services", {})

    # Normalize service names (case-insensitive)
    lab_lookup = {k.lower(): (k, v) for k, v in lab_services.items()}
    qa_lookup = {k.lower(): (k, v) for k, v in qa_services.items()}

    # Match service ignoring case
    service_lower = service.lower()
    if service_lower not in lab_lookup:
        click.echo(f"❌ Service '{service}' not found in LAB file.")
        return

    lab_key, lab_version = lab_lookup[service_lower]
    old_version = qa_lookup.get(service_lower, (service, None))[1]

    # Update QA JSON
    qa_services[lab_key] = lab_version

    # Save QA JSON
    with TARGET_FILE.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file updated: {TARGET_FILE}")
    click.echo(f"⚡ {lab_key}: {old_version or 'not present'} → {lab_version}")
    click.echo("ℹ️  You can now run `git status` outside the CLI to review changes.")

    # Ask user confirmation to commit & push or revert
    commit_message = f"Promote {lab_key} to QA: {lab_version}"
    git_commit_push_or_revert(BASE_PATH, TARGET_FILE, commit_message)

# -----------------------------
# Main Entry
# -----------------------------
def main():
    cli()

if __name__ == "__main__":
    main()
