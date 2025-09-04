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

@aws.command("connect-prod")
@click.argument("service")
@click.option("--profile", default="prod", help="AWS profile")
@click.option("--region", default=None, help="AWS region")
def connect_asg_instance_ssm(service, profile, region):
    """
    Connect via SSM Session Manager to instances filtered by the 'service' tag.
    """

    # Build base AWS CLI args
    base_args = []
    if profile:
        base_args += ["--profile", profile]
    if region:
        base_args += ["--region", region]

    # Get all ASGs
    asg_data = run_aws_cli(["autoscaling", "describe-auto-scaling-groups"] + base_args)
    asgs = asg_data.get("AutoScalingGroups", [])

    if not asgs:
        click.echo("❌ No Auto Scaling Groups found.")
        return

    # Collect all instances matching the service tag
    instance_ids = [
        inst["InstanceId"]
        for asg in asgs
        if any(t["Key"] == "service" and t["Value"].lower() == service.lower() for t in asg.get("Tags", []))
        for inst in asg.get("Instances", [])
    ]

    if not instance_ids:
        click.echo(f"❌ No instances found for service={service}")
        return

    # User selects instance
    try:
        selected_instance = inquirer.select(
            message="Select instance to connect via SSM:",
            choices=instance_ids
        ).execute()
    except KeyboardInterrupt:
        click.echo("\n❌ Exiting by user interrupt.")
        return

    click.echo(f"⚡ Connecting to instance {selected_instance} via SSM...")

    # Run SSM session
    subprocess.run(
        ["aws", "ssm", "start-session", "--target", selected_instance] + base_args,
        check=True
    )
