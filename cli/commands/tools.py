import click
from InquirerPy import inquirer
from cli.utils import run_aws_cli
import subprocess

@click.group()
def aws():
    """🔧 AWS commands."""
    pass

@aws.command("login")
def login():
    cmd = ["cloud-tool", "multilogin", "-i", "~/.venv/profiles.csv"]
    subprocess.run(cmd, check=True)

@aws.command("connect")
@click.argument("env")
@click.argument("service")
@click.option("--region", default=None, help="AWS region")
def connect_instance_ssm(env, service, region):
    """
    Connect via SSM Session Manager to instances filtered by environment and service.

    Usage:
        connect {env} {service}
    """

    # Map environments to AWS profile and ASG tag
    env_map = {
        "lab": {"profile": "preprod", "tag_key": "env", "tag_value": "lab"},
        "qa": {"profile": "preprod", "tag_key": "env", "tag_value": "qa"},
        "sat": {"profile": "preprod", "tag_key": "env", "tag_value": "sat"},
        "prod": {"profile": "prod", "tag_key": "name", "tag_value": "prod"},
    }

    env_lower = env.lower()
    if env_lower not in env_map:
        click.echo(f"❌ Unknown environment '{env}'. Valid: lab, qa, sat, prod.")
        return

    profile = env_map[env_lower]["profile"]
    tag_key = env_map[env_lower]["tag_key"]
    tag_value = env_map[env_lower]["tag_value"]

    # Build AWS CLI base args
    base_args = ["--profile", profile]
    if region:
        base_args += ["--region", region]

    click.echo(f"⚡ Searching instances for env={env}, service={service} using profile={profile}...")

    # Get all ASGs
    asg_data = run_aws_cli(["autoscaling", "describe-auto-scaling-groups"] + base_args)
    asgs = asg_data.get("AutoScalingGroups", [])

    if not asgs:
        click.echo("❌ No Auto Scaling Groups found.")
        return

    # Collect all instances matching the environment and service tags
    instance_ids = [
        inst["InstanceId"]
        for asg in asgs
        if any(t["Key"].lower() == tag_key.lower() and t["Value"].lower() == tag_value.lower() for t in asg.get("Tags", []))
        and any(t["Key"].lower() == "service" and t["Value"].lower() == service.lower() for t in asg.get("Tags", []))
        for inst in asg.get("Instances", [])
    ]

    if not instance_ids:
        click.echo(f"❌ No instances found for env={env} and service={service}")
        return

    # Auto-select if only one instance
    if len(instance_ids) == 1:
        selected_instance = instance_ids[0]
        click.echo(f"⚡ Only one instance found: {selected_instance}. Connecting automatically...")
    else:
        # Let user select instance
        try:
            selected_instance = inquirer.select(
                message="Select instance to connect via SSM:",
                choices=instance_ids
            ).execute()
        except KeyboardInterrupt:
            click.echo("\n❌ Exiting by user interrupt.")
            return

    click.echo(f"⚡ Connecting to instance {selected_instance} via SSM...")

    # Start SSM session
    subprocess.run(
        ["aws", "ssm", "start-session", "--target", selected_instance] + base_args,
        check=True
    )
