# Ape Etherscan Plugin

Etherscan Explorer Plugin for Ethereum-based networks.

## Dependencies

* [python3](https://www.python.org/downloads) version 3.7 or greater, python3-dev

## Installation

### via `pip`

You can install the latest release via [`pip`](https://pypi.org/project/pip/):

```bash
pip install ape-etherscan
```

### via `setuptools`

You can clone the repository and use [`setuptools`](https://github.com/pypa/setuptools) for the most up-to-date version:

```bash
git clone https://github.com/ApeWorX/ape-etherscan.git
cd ape-etherscan
python3 setup.py install
```

## Quick Usage

When you have this plugin installed, Etherscan explorer URLs appear in CLI output.

```bash
INFO: Submitted 0x123321123321123321123321123aaaadaaaee4b2aaa07901b80716cc357a9646
etherscan URL: https://rinkeby.etherscan.io/tx/0x123321123321123321123321123aaaadaaaee4b2aaa07901b80716cc357a9646
```

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## License

This project is licensed under the [Apache 2.0](LICENSE).
