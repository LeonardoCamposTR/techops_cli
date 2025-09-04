import subprocess

@tools.command()
@click.argument("profile", required=False)
def login(profile):
    cmd = ["cloud-tools", "login"]
    if profile:
        cmd += ["--profile", profile.upper()]
    subprocess.run(cmd, check=True)