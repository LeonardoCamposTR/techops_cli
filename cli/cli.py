# import click
# import json
# from pathlib import Path
# import subprocess
# import os
# import shutil
# import tempfile
# from InquirerPy import inquirer

# # -----------------------------
# # Repo Info
# # -----------------------------
# REPO_URL = "github.com/leonardoscampos/apidata.git"
# REPO_SUBDIR = "onviobr/deployer"

# # Default files (used only by promoting_qa)
# SOURCE_FILE = "lab-lab01.json"
# TARGET_FILE = "qa-qa01.json"


# # -----------------------------
# # Helper Functions
# # -----------------------------
# def run_cmd(cmd, cwd=None, check=True, capture_output=False):
#     """Run a shell command."""
#     result = subprocess.run(
#         cmd, cwd=cwd, check=check, text=True,
#         capture_output=capture_output
#     )
#     return result.stdout.strip() if capture_output else None


# def git_commit_push(repo_path: Path, files: list[str], commit_message: str):
#     """Commit and push file(s) to Git."""
#     click.echo(f"⚡ About to commit and push with message:\n  '{commit_message}'")
#     if click.confirm("Do you want to proceed?", default=True):
#         try:
#             for file in files:
#                 run_cmd(["git", "add", file], cwd=repo_path)
#             run_cmd(["git", "commit", "-m", commit_message], cwd=repo_path)
#             run_cmd(["git", "push"], cwd=repo_path)
#             click.echo(f"🚀 Changes committed and pushed: {commit_message}")
#         except subprocess.CalledProcessError as e:
#             click.echo(f"❌ Git command failed: {e}")
#     else:
#         click.echo("❌ Commit and push cancelled. Changes remain in local clone.")


# def promote_services(services, source_file, target_file):
#     """
#     Shared logic for promoting services from one JSON file to another.
#     """
#     if not services:
#         click.echo("❌ Please provide at least one service name.")
#         return

#     # Clone repo into a temporary directory
#     tmpdir = Path(tempfile.mkdtemp(prefix="repo_clone_"))
#     click.echo(f"📥 Cloning repository into {tmpdir} ...")
#     run_cmd(["git", "clone", REPO_URL, str(tmpdir)])

#     repo_path = tmpdir
#     deployer_path = repo_path / REPO_SUBDIR
#     src_file = deployer_path / source_file
#     tgt_file = deployer_path / target_file

#     if not src_file.exists():
#         click.echo(f"❌ Source file not found: {src_file}")
#         shutil.rmtree(tmpdir)
#         return
#     if not tgt_file.exists():
#         click.echo(f"❌ Target file not found: {tgt_file}")
#         shutil.rmtree(tmpdir)
#         return

#     # Load source & target JSON
#     with src_file.open() as f:
#         src_data = json.load(f)
#     with tgt_file.open() as f:
#         tgt_data = json.load(f)

#     src_services = src_data.get("services", {})
#     tgt_services = tgt_data.setdefault("services", {})

#     updates = []
#     for svc in services:
#         # Case-insensitive lookup
#         match = next((k for k in src_services if k.lower() == svc.lower()), None)
#         if not match:
#             click.echo(f"⚠️ Service '{svc}' not found in source file.")
#             continue

#         new_version = src_services[match]
#         old_version = tgt_services.get(match)
#         if old_version == new_version:
#             click.echo(f"ℹ️ {match} already at version {new_version}, no change.")
#             continue

#         tgt_services[match] = new_version
#         updates.append((match, old_version, new_version))

#     if not updates:
#         click.echo("✅ No updates applied.")
#         shutil.rmtree(tmpdir)
#         return

#     # Save updated target JSON
#     with tgt_file.open("w") as f:
#         json.dump(tgt_data, f, indent=2)

#     click.echo(f"💾 Target file updated: {tgt_file}")
#     for svc, old, new in updates:
#         click.echo(f"⚡ {svc}: {old or 'not present'} → {new}")

#     # Commit & push
#     commit_message = f"Promote services from {source_file} → {target_file}:\n" + "\n".join(
#         [f"- {svc}: {old or 'none'} → {new}" for svc, old, new in updates]
#     )
#     git_commit_push(repo_path, [str(tgt_file)], commit_message)

#     # Cleanup repo
#     click.echo("🧹 Cleaning up local clone...")
#     shutil.rmtree(tmpdir)
#     click.echo("✅ Done.")


# # -----------------------------
# # CLI Definition
# # -----------------------------
# @click.group()
# def cli():
#     """🚀 DevOps CLI - Utilities for environment setup & troubleshooting."""
#     pass


# # -----------------------------
# # Promoting to QA
# # -----------------------------
# @cli.command()
# @click.argument("services", nargs=-1)
# def promoting_qa(services):
#     """Promote services from LAB → QA."""
#     promote_services(services, "lab-lab01.json", "qa-qa01.json")


# # -----------------------------
# # Promoting to SAT
# # -----------------------------
# @cli.command()
# @click.argument("services", nargs=-1)
# def promoting_sat(services):
#     """Promote services from QA → SAT."""
#     promote_services(services, "qa-qa01.json", "sat-sat01.json")



# # -----------------------------
# # ASG Terminate Functions
# # -----------------------------
# def run_aws_cli(command: list) -> dict:
#     """Run AWS CLI command and return parsed JSON output."""
#     try:
#         result = subprocess.run(
#             ["aws"] + command + ["--output", "json"],
#             capture_output=True,
#             text=True,
#             check=True,
#         )
#         return json.loads(result.stdout)
#     except subprocess.CalledProcessError as e:
#         click.echo(f"❌ AWS CLI command failed: {e.stderr}")
#         raise

# @cli.command("terminate-asg-instances")
# @click.argument("env")
# @click.option("--profile", default="NON-PROD", help="AWS profile (from ~/.aws/credentials)")
# @click.option("--region", default=None, help="AWS region (overrides ~/.aws/config)")
# def terminate_asg_instances(env, profile, region):
#     """
#     Terminate all EC2 instances in one or more Auto Scaling Groups
#     filtered by tags: platform=onviobr + Name=<env>.
#     """

#     # Build base AWS CLI args
#     base_args = []
#     if profile:
#         base_args += ["--profile", profile]
#     if region:
#         base_args += ["--region", region]

#     # Get all ASGs
#     asg_data = run_aws_cli(
#         ["autoscaling", "describe-auto-scaling-groups"] + base_args
#     )

#     asgs = asg_data.get("AutoScalingGroups", [])
#     if not asgs:
#         click.echo("❌ No Auto Scaling Groups found.")
#         return

#     # Filter ASGs by platform=onviobr + Name=<env>
#     matching_asgs = [
#         asg for asg in asgs
#         if any(t["Key"] == "platform" and t["Value"] == "onviobr" for t in asg.get("Tags", []))
#         and any(t["Key"] == "name" and t["Value"].lower() == env.lower() for t in asg.get("Tags", []))
#     ]

#     if not matching_asgs:
#         click.echo(f"❌ No ASGs found with platform=onviobr and Name={env}")
#         return

#     # Multi-select ASG using checkbox
#     choices = [asg["AutoScalingGroupName"] for asg in matching_asgs]
#     selected_asgs = inquirer.checkbox(
#         message="Select ASG(s) to terminate (press SPACE to select, ENTER to confirm, q to exit):",
#         choices=choices,
#         instruction="Use SPACE to select, ENTER to confirm, q to quit"
#     ).execute()

#     if not selected_asgs:
#         click.echo("❌ No ASGs selected. Exiting.")
#         return

#     click.echo(f"⚡ Selected ASGs: {', '.join(selected_asgs)}")

#     for asg_name in selected_asgs:
#         # Get instances from ASG
#         instances_data = run_aws_cli(
#             ["autoscaling", "describe-auto-scaling-groups", "--auto-scaling-group-names", asg_name] + base_args
#         )
#         instance_ids = [
#             inst["InstanceId"]
#             for asg in instances_data.get("AutoScalingGroups", [])
#             for inst in asg.get("Instances", [])
#         ]
#         if not instance_ids:
#             click.echo(f"ℹ️ No instances found in ASG {asg_name}")
#             continue

#         click.echo(f"⚡ Terminating instances in ASG {asg_name}: {', '.join(instance_ids)}")
#         if click.confirm("Do you want to proceed?", default=False):
#             subprocess.run(
#                 ["aws", "ec2", "terminate-instances", "--instance-ids"] + instance_ids + base_args,
#                 check=True,
#             )
#             click.echo("🚀 Termination initiated.")
#         else:
#             click.echo(f"❌ Termination cancelled for ASG {asg_name}.")

# @cli.command("status")
# def techops_status():
#     """Show TechOps status."""
#     click.echo("✅ TechOps is up and running 🚀")

# def main():
#     cli()


# if __name__ == "__main__":
#     main()


import click
from cli.commands.promoting import promoting_qa, promoting_sat
from cli.commands.asg import terminate_asg_instances
from cli.commands.status import status
from cli.commands.tools import tools

@click.group()
def techops():
    """🔧 TechOps commands."""
    pass

# Register subcommands
techops.add_command(promoting_qa)
techops.add_command(promoting_sat)
techops.add_command(terminate_asg_instances)
techops.add_command(status)

def main():
    techops()

if __name__ == "__main__":
    main()
