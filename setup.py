#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

extras_require = {
    "test": [  # `test` GitHub Action jobs uses this
        "ape-arbitrum",  # Needed for Arbitrum integration
        "ape-base",  # Needed for Base networks integration
        "ape-blast",  # Needed for Blast networks integration
        "ape-bsc",  # For testing BSC integration
        "ape-fantom",  # For testing Fantom integration
        "ape-optimism",  # Needed for Optimism integration
        "ape-polygon",  # Needed for Polygon integration
        "ape-polygon-zkevm",  # Needed for Polygon ZkEVM integration
        "ape-infura",  # Needed for live network tests
        "ape-solidity",  # Needed for contract verification tests
        "pytest>=6.0",  # Core testing package
        "pytest-xdist",  # Multi-process runner
        "pytest-cov",  # Coverage analyzer plugin
        "hypothesis>=6.2.0,<7",  # Strategy-based fuzzer
        "pytest-mock",  # Test mocker
    ],
    "lint": [
        "black>=24.4.2,<25",  # auto-formatter and linter
        "mypy>=1.10.1,<2",  # Static type analyzer
        "types-requests>=2.28.7",  # Needed due to mypy typeshed
        "types-setuptools",  # Needed due to mypy typeshed
        "types-PyYAML",  # Needed due to mypy typeshed
        "flake8>=7.1.0,<8",  # Style linter
        "flake8-breakpoint>=1.1.0,<2",  # Detect breakpoints left in code
        "flake8-print>=5.0.0,<6",  # Detect print statements left in code
        "isort>=5.13.2,<6",  # Import sorting linter
        "mdformat>=0.7.17",  # Auto-formatter for markdown
        "mdformat-gfm>=0.3.5",  # Needed for formatting GitHub-flavored markdown
        "mdformat-frontmatter>=0.4.1",  # Needed for frontmatters-style headers in issue templates
        "mdformat-pyproject>=0.0.1",  # Allows configuring in pyproject.toml
    ],
    "doc": [
        "Sphinx>=6.1.3,<7",  # Documentation generator
        "sphinx_rtd_theme>=1.2.0,<2",  # Readthedocs.org theme
        "towncrier>=19.2.0,<20",  # Generate release notes
    ],
    "release": [  # `release` GitHub Action job uses this
        "setuptools",  # Installation tool
        "setuptools-scm",  # Installation tool
        "wheel",  # Packaging tool
        "twine",  # Package upload tool
    ],
    "dev": [
        "commitizen",  # Manage commits and publishing releases
        "pre-commit",  # Ensure that linters are run prior to committing
        "pytest-watch",  # `ptw` test watcher/runner
        "IPython",  # Console for interacting
        "ipdb",  # Debugger (Must use `export PYTHONBREAKPOINT=ipdb.set_trace`)
    ],
}

# NOTE: `pip install -e .'[dev]'` to install package
extras_require["dev"] = (
    extras_require["test"]
    + extras_require["lint"]
    + extras_require["doc"]
    + extras_require["release"]
    + extras_require["dev"]
)

with open("./README.md") as readme:
    long_description = readme.read()


setup(
    name="ape-etherscan",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="""ape-etherscan: Etherscan Explorer Plugin for Ethereum-based networks""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ApeWorX Ltd.",
    author_email="admin@apeworx.io",
    url="https://github.com/ApeWorX/ape-etherscan",
    include_package_data=True,
    install_requires=[
        "eth-ape>=0.8.8,<0.9",
        "ethpm_types",  # Use same version as eth-ape
        "requests",  # Use same version as eth-ape
        "yarl",  # Use same version as eth-ape
    ],
    python_requires=">=3.9,<4",
    extras_require=extras_require,
    py_modules=["ape_etherscan"],
    license="Apache-2.0",
    zip_safe=False,
    keywords="ethereum",
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={"ape_etherscan": ["py.typed"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
