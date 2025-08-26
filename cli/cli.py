import click
import json
from pathlib import Path

# -----------------------------
# Paths
# -----------------------------
BASE_PATH = Path("/home/leonardoscampos/gits/a202606_mastersafdevops-apidata/onviobr/deployer")
SOURCE_FILE = BASE_PATH / "lab-lab01.json"
TARGET_FILE = BASE_PATH / "qa-qa01.json"

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
    """Update QA JSON with version from LAB JSON for a given service."""
    if not SOURCE_FILE.exists():
        click.echo(f"❌ LAB file not found: {SOURCE_FILE}")
        return
    if not TARGET_FILE.exists():
        click.echo(f"❌ QA file not found: {TARGET_FILE}")
        return

    # Load LAB JSON
    with SOURCE_FILE.open() as f:
        lab_data = json.load(f)

    # Load QA JSON
    with TARGET_FILE.open() as f:
        qa_data = json.load(f)

    # Search service in LAB
    lab_version = None
    for svc in lab_data.get("services", []):
        if svc.get("name").lower() == service.lower():
            lab_version = svc.get("version")
            break

    if not lab_version:
        click.echo(f"❌ Service '{service}' not found in LAB file.")
        return

    # Update QA JSON
    updated = False
    for svc in qa_data.get("services", []):
        if svc.get("name").lower() == service.lower():
            svc["version"] = lab_version
            updated = True
            break

    if not updated:
        # If service not found in QA, add it
        qa_data.setdefault("services", []).append({"name": service, "version": lab_version})
        click.echo(f"ℹ Service '{service}' added to QA with version {lab_version}.")
    else:
        click.echo(f"✅ Service '{service}' updated in QA to version {lab_version}.")

    # Save QA JSON
    with TARGET_FILE.open("w") as f:
        json.dump(qa_data, f, indent=2)

    click.echo(f"💾 QA file saved: {TARGET_FILE}")


def main():
    cli()


if __name__ == "__main__":
    main()
