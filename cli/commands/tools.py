from cloud-tools

@tools.command()
@click.argument("profile", required=False)
def login(profile):
    args = ["login"]
    if profile:
        args += ["--profile", profile.upper()]
    cloud-tools.main(args=args, standalone_mode=False)
