import click
import subprocess, json
from InquirerPy import inquirer
from cli.utils import run_aws_cli

@click.command("terminate-asg-instances")
@click.argument("env")
@click.option("--profile", default="NON-PROD", help="AWS profile")
@click.option("--region", default=None, help="AWS region")

def run_aws_cli(command: list) -> dict:
    """Run AWS CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["aws"] + command + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ AWS CLI command failed: {e.stderr}")
        raise

def terminate_asg_instances(env, profile, region):
    """
    Terminate all EC2 instances in one or more Auto Scaling Groups
    filtered by tags: platform=onviobr + Name=<env>.
    """

    # Build base AWS CLI args
    base_args = []
    if profile:
        base_args += ["--profile", profile]
    if region:
        base_args += ["--region", region]

    # Get all ASGs
    asg_data = run_aws_cli(
        ["autoscaling", "describe-auto-scaling-groups"] + base_args
    )

    asgs = asg_data.get("AutoScalingGroups", [])
    if not asgs:
        click.echo("❌ No Auto Scaling Groups found.")
        return

    # Filter ASGs by platform=onviobr + Name=<env>
    matching_asgs = [
        asg for asg in asgs
        if any(t["Key"] == "platform" and t["Value"] == "onviobr" for t in asg.get("Tags", []))
        and any(t["Key"] == "name" and t["Value"].lower() == env.lower() for t in asg.get("Tags", []))
    ]

    if not matching_asgs:
        click.echo(f"❌ No ASGs found with platform=onviobr and Name={env}")
        return

    # Multi-select ASG using checkbox
    choices = [asg["AutoScalingGroupName"] for asg in matching_asgs]
    selected_asgs = inquirer.checkbox(
        message="Select ASG(s) to terminate (press SPACE to select, ENTER to confirm, q to exit):",
        choices=choices,
        instruction="Use SPACE to select, ENTER to confirm, q to quit"
    ).execute()

    if not selected_asgs:
        click.echo("❌ No ASGs selected. Exiting.")
        return

    click.echo(f"⚡ Selected ASGs: {', '.join(selected_asgs)}")

    for asg_name in selected_asgs:
        # Get instances from ASG
        instances_data = run_aws_cli(
            ["autoscaling", "describe-auto-scaling-groups", "--auto-scaling-group-names", asg_name] + base_args
        )
        instance_ids = [
            inst["InstanceId"]
            for asg in instances_data.get("AutoScalingGroups", [])
            for inst in asg.get("Instances", [])
        ]
        if not instance_ids:
            click.echo(f"ℹ️ No instances found in ASG {asg_name}")
            continue

        click.echo(f"⚡ Terminating instances in ASG {asg_name}: {', '.join(instance_ids)}")
        if click.confirm("Do you want to proceed?", default=False):
            subprocess.run(
                ["aws", "ec2", "terminate-instances", "--instance-ids"] + instance_ids + base_args,
                check=True,
            )
            click.echo("🚀 Termination initiated.")
        else:
            click.echo(f"❌ Termination cancelled for ASG {asg_name}.")
            
    click.echo(f"Terminate ASG instances for {env} (profile={profile}, region={region})")
