import subprocess
import click
import json
import tempfile
import shutil
from pathlib import Path

REPO_URL = "git@github.com:tr/a202606_mastersafdevops-apidata.git"
REPO_SUBDIR = "onviobr/deployer"

def run_cmd(cmd, cwd=None, check=True, capture_output=False):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        capture_output=capture_output
    )
    return result.stdout.strip() if capture_output else None

def git_commit_push(repo_path: Path, files: list[str], commit_message: str):
    click.echo(f"⚡ About to commit and push:\n{commit_message}")
    run_cmd(["git", "add"] + files, cwd=repo_path)
    run_cmd(["git", "commit", "-m", commit_message], cwd=repo_path)
    run_cmd(["git", "push"], cwd=repo_path)

def promote_services(services, source_file, target_file):
    """
    Shared logic for promoting services from one JSON file to another.
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
    src_file = deployer_path / source_file
    tgt_file = deployer_path / target_file

    if not src_file.exists():
        click.echo(f"❌ Source file not found: {src_file}")
        shutil.rmtree(tmpdir)
        return
    if not tgt_file.exists():
        click.echo(f"❌ Target file not found: {tgt_file}")
        shutil.rmtree(tmpdir)
        return

    # Load source & target JSON
    with src_file.open() as f:
        src_data = json.load(f)
    with tgt_file.open() as f:
        tgt_data = json.load(f)

    src_services = src_data.get("services", {})
    tgt_services = tgt_data.setdefault("services", {})

    updates = []
    for svc in services:
        # Case-insensitive lookup
        match = next((k for k in src_services if k.lower() == svc.lower()), None)
        if not match:
            click.echo(f"⚠️ Service '{svc}' not found in source file.")
            continue

        new_version = src_services[match]
        old_version = tgt_services.get(match)
        if old_version == new_version:
            click.echo(f"ℹ️ {match} already at version {new_version}, no change.")
            continue

        tgt_services[match] = new_version
        updates.append((match, old_version, new_version))

    if not updates:
        click.echo("✅ No updates applied.")
        shutil.rmtree(tmpdir)
        return

    # Show the updates
    click.echo(f"💾 Target file updated: {tgt_file}")
    for svc, old, new in updates:
        click.echo(f"⚡ {svc}: {old or 'not present'} → {new}")

    # Ask for confirmation before commit & push
    if click.confirm("📝 Do you want to commit and push these changes?", default=True):
        commit_message = f"Promote services from {source_file} → {target_file}:\n" + "\n".join(
            [f"- {svc}: {old or 'none'} → {new}" for svc, old, new in updates]
        )
        git_commit_push(repo_path, [str(tgt_file)], commit_message)
    else:
        click.echo("❌ Changes were not pushed.")

    # Cleanup repo
    click.echo("🧹 Cleaning up local clone...")
    shutil.rmtree(tmpdir)
    click.echo("✅ Done.")

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
