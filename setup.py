from setuptools import setup, find_packages

setup(
    name="techops_cli",
    version="1.0.0",
    packages=find_packages(),  # This finds the techops_cli folder automatically
    include_package_data=True,
    install_requires=[
        "click",
        "InquirerPy",
        
    ],
    entry_points={
        "console_scripts": [
            "techops=cli.cli:main",  # path to main() inside techops_cli.py
        ],
    },
    author="Leonardo Campos",
    description="TechOps CLI - Utilities for environment setup & troubleshooting",
    python_requires=">=3.8",
)