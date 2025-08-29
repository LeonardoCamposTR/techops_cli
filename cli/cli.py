import click
import json
from pathlib import Path
import subprocess
import os
import shutil
import tempfile

# -----------------------------
# Repo Info
# -----------------------------
REPO_URL = "git@gitlab.com:your-org/your-repo.git"
REPO_SUBDIR = "onvio/deployer"
SOURCE_FILE = "lab-lab01.json"
TARGET_FILE = "qa-qa01.json"


# -----------------------------
# Helper Functions
# -----------------------------
def run_cmd(cmd, cwd=None, check=True, capture_output=False):
    """Run a shell command."""
    result = subprocess.run(
        cmd, cwd=cwd, check=check, text=True,
        capture_output=capture_output
    )
    return result.stdout.strip() if capture_output else None


def git_commit_push(repo_path: Path, files: list[str], commit_message: str):
    """Commit and push file(s) to Git."""
    click.echo(f"⚡ About to commit and push with message:\n  '{commit_message}'")
    if click.confirm("Do you want to proceed?", default=True):
        try:
            for file in files:
                run_cmd(["git", "add", file], cwd=repo_path)
            run_cmd(["git", "commit", "-m", commit_message], cwd=repo_path)
            run_cmd(["git", "push"], cwd=repo_path)
            click.echo(f"🚀 Changes committed and pushed: {commit_message}")
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Git command failed: {e}")
    else:
        click.echo("❌ Commit and push cancelled. Changes remain in local clone.")


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
@click.argument("services", nargs=-1)
def promoting_qa(services):
    """
    Update QA JSON with version(s) from LAB JSON for one or more services
    and optionally commit/push.
    """
    if not services:
        click.echo("❌ Please provide at least one service name.")
        return

    # Clone repo into a temporary directory
    tmpdir = Path(tempfile.mkdtemp(prefix="repo_clone_"))
    click.echo(f"📥 Cloning repository into {tmpdir} ...")
    run_cmd(["git", "clone", REPO_URL, str(tmpdir)])

    repo_path = tmpdir
    deployer_path = repo_path / REPO_SUBDIR
    src_file = deployer_path / SOURCE_FILE
    tgt_file = deployer_path / TARGET_FILE

    if not src_file.exists():
        click.echo(f"❌ LAB file not found: {src_file}")
        shutil.rmtree(tmpdir)
        return
    if not tgt_file.exists():
        click.echo(f"❌ QA file not found: {tgt_file}")
        shutil.rmtree(tmpdir)
        return

    # Load LAB & QA JSON
    with src_file.open() as f:
        lab_data = json.load(f)
    with tgt_file.open() as f:
        qa_data = json.load(f)

    lab_services = lab_data.get("services", {})
    qa_services = qa_data.setdefault("services", {})

    updates = []
    for svc in services:
        # Case-insensitive lookup
        match = next((k for k in lab_services if k.lower() == svc.lower()), None)
        if not match:
            click.echo(f"⚠️ Service '{svc}' not found in LAB file.")
            continue

        lab_version = lab_services[match]
        old_version = qa_services.get(match)
        if old_version == lab_version:
            click.echo(f"ℹ️ {match} already at version {lab_version}, no change.")
            continue

        qa_services[match] = lab_version
        updates.append((match, old_version, lab_version))

    if not updates:
        click.echo("✅ No updates applied.")
        shutil.rmtree(tmpdir)
        return

    # Save updated QA JSON
    with tgt_file.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file updated: {tgt_file}")
    for svc, old, new in updates:
        click.echo(f"⚡ {svc}: {old or 'not present'} → {new}")

    # Commit & push
    commit_message = "Promote services to QA:\n" + "\n".join(
        [f"- {svc}: {old or 'none'} → {new}" for svc, old, new in updates]
    )
    git_commit_push(repo_path, [str(tgt_file)], commit_message)

    # Cleanup repo
    click.echo("🧹 Cleaning up local clone...")
    shutil.rmtree(tmpdir)
    click.echo("✅ Done.")


def main():
    cli()


if __name__ == "__main__":
    main()
