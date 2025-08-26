import click
import json
from pathlib import Path
import subprocess
import os
import shutil
import tempfile

# -----------------------------
# Configuration
# -----------------------------
REPO_URL = "git@github.com:org/repo.git"  # Set your repo URL here

# -----------------------------
# Helper Functions
# -----------------------------
def run_command(cmd, cwd=None):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def git_clone_temp(repo_url: str):
    """Clone a git repo to a temporary directory."""
    tmp_dir = Path(tempfile.mkdtemp())
    click.echo(f"🔄 Cloning repo {repo_url} into {tmp_dir}...")
    subprocess.run(["git", "clone", repo_url, str(tmp_dir)], check=True)
    return tmp_dir

def git_commit_push(repo_path: Path, file_path: Path, commit_message: str):
    """Commit and push a file to Git in the given repository."""
    click.echo(f"⚡ Committing and pushing {file_path} with message:\n  '{commit_message}'")
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
        subprocess.run(["git", "-C", str(repo_path), "restore", str(file_path)], check=True)
        click.echo("↩️  Changes reverted.")

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
@click.argument("source_file")
@click.argument("target_file")
def promoting_qa(service, source_file, target_file):
    """Update QA JSON from LAB JSON and commit to repo."""
    tmp_repo = git_clone_temp(REPO_URL)

    source_path = tmp_repo / source_file
    target_path = tmp_repo / target_file

    if not source_path.exists():
        click.echo(f"❌ LAB file not found: {source_path}")
        shutil.rmtree(tmp_repo)
        return
    if not target_path.exists():
        click.echo(f"❌ QA file not found: {target_path}")
        shutil.rmtree(tmp_repo)
        return

    with source_path.open() as f:
        lab_data = json.load(f)
    with target_path.open() as f:
        qa_data = json.load(f)

    # Case-insensitive service lookup
    service_map = {k.lower(): k for k in lab_data.get("services", {})}
    key = service_map.get(service.lower())
    if not key:
        click.echo(f"❌ Service '{service}' not found in LAB file.")
        shutil.rmtree(tmp_repo)
        return

    lab_version = lab_data["services"][key]
    old_version = qa_data.setdefault("services", {}).get(key)
    qa_data["services"][key] = lab_version

    with target_path.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file updated: {target_path}")
    click.echo(f"⚡ {key}: {old_version or 'not present'} → {lab_version}")
    click.echo("🔹 You can run `git status` outside the CLI to review changes before commit.")

    commit_message = f"Promote {key} to QA: {lab_version}"
    git_commit_push(tmp_repo, target_path, commit_message)

    shutil.rmtree(tmp_repo)
    click.echo("🗑️  Temporary repo deleted.")

# -----------------------------
# ASG Terminate Command
# -----------------------------
@cli.command()
@click.argument("env")
def terminate_asg_instances(env):
    """Select one or more ASGs with platform=onviobr and terminate their instances."""
    try:
        # Get all ASGs with platform=onviobr
        output = run_command(["aws", "autoscaling", "describe-auto-scaling-groups",
                              "--query", "AutoScalingGroups[?contains(Tags[?Key=='platform'].Value, 'onviobr')].[AutoScalingGroupName,Tags]"])
        asgs = json.loads(output)
        # Filter by env tag
        filtered_asgs = [asg[0] for asg in asgs
                         if any(t["Key"] == "Name" and env.lower() in t["Value"].lower() for t in asg[1])]

        if not filtered_asgs:
            click.echo(f"❌ No ASGs found for env '{env}'.")
            return

        click.echo("Select ASGs to terminate (comma separated numbers):")
        for i, asg in enumerate(filtered_asgs, 1):
            click.echo(f"{i}) {asg}")

        selection = click.prompt("Enter selection", default="1")
        indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip().isdigit()]
        selected_asgs = [filtered_asgs[i] for i in indices if 0 <= i < len(filtered_asgs)]

        click.echo(f"⚡ Selected ASGs: {selected_asgs}")
        if click.confirm("Proceed to terminate instances?", default=False):
            for asg_name in selected_asgs:
                instances_output = run_command(["aws", "autoscaling", "describe-auto-scaling-groups",
                                                "--auto-scaling-group-names", asg_name,
                                                "--query", "AutoScalingGroups[0].Instances[].InstanceId"])
                instance_ids = json.loads(instances_output)
                for instance_id in instance_ids:
                    click.echo(f"⏹ Terminating instance {instance_id} in {asg_name}...")
                    subprocess.run(["aws", "ec2", "terminate-instances", "--instance-ids", instance_id], check=True)
            click.echo("✅ Termination commands executed.")
        else:
            click.echo("❌ Termination cancelled.")

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ AWS CLI command failed: {e}")

# -----------------------------
# Main
# -----------------------------
def main():
    cli()

if __name__ == "__main__":
    main()
