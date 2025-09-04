import click
from cli.utils import promote_services

@click.command("promoting-qa")
@click.argument("services", nargs=-1)
def promoting_qa(services):
    """Promote services from LAB → QA."""
    promote_services(services, "lab-lab01.json", "qa-qa01.json")

@click.command("promoting-sat")
@click.argument("services", nargs=-1)
def promoting_sat(services):
    """Promote services from QA → SAT."""
    promote_services(services, "qa-qa01.json", "sat-sat01.json")