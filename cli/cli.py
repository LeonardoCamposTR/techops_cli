import click
import json
from pathlib import Path
import subprocess
import os

# -----------------------------
# Repo and file paths
# -----------------------------
BASE_PATH = Path(os.getenv("REPO_BASE_PATH", "/tmp/repository")) / "onvio/deployer"
LAB_FILE = BASE_PATH / "lab-lab01.json"
QA_FILE = BASE_PATH / "qa-qa01.json"

REPO_URL = "git@github.com:your-org/your-repo.git"  # <--- set your repo URL here

# -----------------------------
# Helper Functions
# -----------------------------
def clone_repo_if_missing():
    """Clone the repository if the path does not exist."""
    if not BASE_PATH.exists():
        click.echo(f"🔄 Cloning repository to {BASE_PATH}...")
        BASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", REPO_URL, str(BASE_PATH)], check=True)
        click.echo("✅ Repository cloned.")

def ensure_repo_up_to_date(repo_path: Path):
    """Ensure the git repository is up to date before modifying files."""
    click.echo("🔄 Checking if repository is up to date...")
    try:
        subprocess.run(["git", "-C", str(repo_path), "fetch"], check=True, capture_output=True)
        status_result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "-uno"],
            capture_output=True, text=True, check=True
        )
        if "Your branch is up to date" not in status_result.stdout:
            click.echo("❌ Repository is not up to date. Please pull the latest changes first.")
            raise click.Abort()
        click.echo("✅ Repository is up to date.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git check failed: {e}")
        raise click.Abort()

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
        click.echo("❌ Commit and push cancelled. Running `git restore` to revert file...")
        try:
            subprocess.run(["git", "-C", str(repo_path), "restore", str(file_path)], check=True)
            click.echo("↩️  Changes reverted successfully.")
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
    """Update QA JSON with version from LAB JSON for a given service and optionally commit/push."""
    clone_repo_if_missing()
    ensure_repo_up_to_date(BASE_PATH)

    if not LAB_FILE.exists():
        click.echo(f"❌ LAB file not found: {LAB_FILE}")
        return
    if not QA_FILE.exists():
        click.echo(f"❌ QA file not found: {QA_FILE}")
        return

    # Load LAB JSON
    with LAB_FILE.open() as f:
        lab_data = json.load(f)

    # Load QA JSON
    with QA_FILE.open() as f:
        qa_data = json.load(f)

    # Case-insensitive search
    service_map = {k.lower(): k for k in lab_data.get("services", {})}
    key = service_map.get(service.lower())
    if not key:
        click.echo(f"❌ Service '{service}' not found in LAB file.")
        return

    # Get version from LAB
    lab_version = lab_data["services"][key]

    # Update QA JSON immediately
    qa_services = qa_data.setdefault("services", {})
    old_version = qa_services.get(key)
    qa_services[key] = lab_version

    # Save QA JSON
    with QA_FILE.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file updated: {QA_FILE}")
    click.echo(f"⚡ {key}: {old_version or 'not present'} → {lab_version}")
    click.echo("You can now run `git status` outside the CLI to review changes.")

    # Ask user confirmation to commit & push
    commit_message = f"Promote {key} to QA: {lab_version}"
    git_commit_push(BASE_PATH, QA_FILE, commit_message)

# -----------------------------
# ASG Terminate Functions
# -----------------------------
def run_aws_cli(command: list) -> dict:
    """Run AWS CLI command and return parsed JSON output."""
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

@cli.command("terminate-asg-instances")
@click.argument("env")
@click.option("--profile", default="NON-PROD", help="AWS profile (from ~/.aws/credentials)")
@click.option("--region", default=None, help="AWS region (overrides ~/.aws/config)")
def terminate_asg_instances(env, profile, region):
    """
    Terminate all EC2 instances in one or more Auto Scaling Groups
    filtered by tags: platform=onviobr + name=<env>.
    """

    # Build base AWS CLI args
    base_args = []
    if profile:
        base_args += ["--profile", profile]
    if region:
        base_args += ["--region", region]

    # Get all ASGs
    asg_data = run_aws_cli(
        ["autoscaling", "describe-auto-scaling-groups"] + base_args
    )

    asgs = asg_data.get("AutoScalingGroups", [])
    if not asgs:
        click.echo("❌ No Auto Scaling Groups found.")
        return

    # Filter ASGs by platform=onviobr + name=<env>
    matching_asgs = []
    for asg in asgs:
        tags = {t["Key"]: t["Value"] for t in asg.get("Tags", [])}
        if tags.get("platform") == "onviobr" and tags.get("name", "").lower() == env.lower():
            matching_asgs.append(asg)

    if not matching_asgs:
        click.echo(f"❌ No ASGs found with platform=onviobr and name={env}")
        return

    # Show ASGs and allow multi-selection
    click.echo(f"🔍 Matching ASGs with platform=onviobr and name={env}:")
    for i, asg in enumerate(matching_asgs, 1):
        click.echo(f"{i}. {asg['AutoScalingGroupName']}")

    selected_indices = click.prompt(
        "Enter ASG numbers to terminate (comma separated), or q to quit",
        default="q"
    )
    if selected_indices.lower() == "q":
        click.echo("❌ Termination cancelled.")
        return

    try:
        selected_indices = [int(x.strip()) for x in selected_indices.split(",")]
    except ValueError:
        click.echo("❌ Invalid selection")
        return

    selected_asgs = []
    for idx in selected_indices:
        if 1 <= idx <= len(matching_asgs):
            selected_asgs.append(matching_asgs[idx - 1])
        else:
            click.echo(f"❌ Invalid index: {idx}")

    if not selected_asgs:
        click.echo("❌ No valid ASGs selected")
        return

    # Terminate instances in each selected ASG
    for asg in selected_asgs:
        asg_name = asg["AutoScalingGroupName"]
        instance_ids = [inst["InstanceId"] for inst in asg.get("Instances", [])]
        if not instance_ids:
            click.echo(f"ℹ️ No instances found in ASG {asg_name}")
            continue
        click.echo(f"⚡ Terminating instances in ASG {asg_name}: {', '.join(instance_ids)}")
        if click.confirm(f"Do you want to proceed terminating ASG {asg_name}?", default=False):
            subprocess.run(
                ["aws", "ec2", "terminate-instances", "--instance-ids"] + instance_ids + base_args,
                check=True,
            )
            click.echo("🚀 Termination initiated.")
        else:
            click.echo("❌ Termination cancelled.")

# -----------------------------
# CLI Entry
# -----------------------------
def main():
    cli()

if __name__ == "__main__":
    main()
