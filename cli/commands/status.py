import click

@click.command("status")
def status():
    """Show TechOps status."""
    click.echo("✅ TechOps is up and running 🚀")