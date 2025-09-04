# TechOps CLI

TechOps CLI is a command-line tool designed to streamline and automate common technical operations tasks. It provides a set of commands for managing infrastructure, deployments, and monitoring, making it easier for DevOps and engineering teams to work efficiently.

## Features
- Modular command structure for easy extension
- Infrastructure management commands
- Deployment and promotion tools
- Status monitoring utilities
- Extensible utilities for custom workflows

## Installation

You can install TechOps CLI using pip:

```bash
pip install .
```

Or, if you are developing locally:

```bash
pip install -e .
```

## Usage


Run the CLI using:

```bash
python -m cli <command> [options]
```

### Real Command Examples

- Promote services from LAB to QA:
	```bash
	python -m cli promoting-qa <service1> <service2> ...
	```
- Promote services from QA to SAT:
	```bash
	python -m cli promoting-sat <service1> <service2> ...
	```
- Check status of multiple services:
	```bash
	python -m cli status <service1> <service2> ...
	```
- AWS login (multi-login):
	```bash
	python -m cli aws login
	```
- Connect to an instance via SSM:
	```bash
	python -m cli aws connect <env> <service> --region <region>
	```

## Command Structure

Commands are organized in the `cli/commands/` directory:
- `promoting.py`: Promotion-related commands
- `status.py`: Status and monitoring commands
- `tools.py`: Utility commands

## Development

To contribute or extend the CLI:
1. Clone the repository
2. Add new commands in `cli/commands/`
3. Update `cli/cli.py` to register new commands
4. Submit a pull request

## License

This project is licensed under the terms of the LICENSE file.

## Support

For issues or feature requests, please open an issue on GitHub.
