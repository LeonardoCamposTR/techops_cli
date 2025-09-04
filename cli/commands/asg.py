import click
import subprocess, json
from InquirerPy import inquirer
from cli.utils import run_aws_cli

@click.command("terminate-asg-instances")
@click.argument("env")
@click.option("--profile", default="NON-PROD", help="AWS profile")
@click.option("--region", default=None, help="AWS region")
def terminate_asg_instances(env, profile, region):
    """Terminate EC2 instances in ASG by tags."""
    # ✅ your terminate logic (same as before)
    click.echo(f"Terminate ASG instances for {env} (profile={profile}, region={region})")
