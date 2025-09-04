import subprocess
import click

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
def connect(service):
    cmd = ["aws", "ssm", "start-session", "--profile" "prod", "--target", service]