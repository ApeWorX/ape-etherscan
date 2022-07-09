# Ape Etherscan Plugin

The following blockchain explorers are supported in this plugin:

* [Etherscan](https://etherscan.io/) for Ethereum networks.
* [Ftmscan](https://ftmscan.com) plugin for Fantom networks.
* [Arbiscan]("https://arbiscan.io") plugin for Arbitrum networks.

## Dependencies

* [python3](https://www.python.org/downloads) version 3.7.2 or greater, python3-dev

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

## Transaction URLs

When you have this plugin installed, Etherscan explorer URLs appear in CLI output.

```bash
INFO: Submitted 0x123321123321123321123321123aaaadaaaee4b2aaa07901b80716cc357a9646
etherscan URL: https://rinkeby.etherscan.io/tx/0x123321123321123321123321123aaaadaaaee4b2aaa07901b80716cc357a9646
```

## Contract Types

The `ape-etherscan` plugin also assists in fetching `contract_types`.
Use the `Contract` top-level construct to create contract instances.
When the explorer plugin locates a contract type for a given address, the `Contract` return-value uses that contract type.

```python
from ape import accounts, Contract

contract = Contract("0x55a8a39bc9694714e2874c1ce77aa1e599461e18")
receipt = contract.call_mutable_method("arg0", sender=accounts.load("acct"))
```

The first line `contract = Contract("0x55a8a39bc9694714e2874c1ce77aa1e599461e18")` first checks if ape has a cached contract-type for the address `0x55a8a39bc9694714e2874c1ce77aa1e599461e18`.
If it does not find a cached contract type, it uses explorer plugins to attempt to fetch one.
The contract type is then cached to disk (and in memory for the active session) so that subsequent invocations don't require HTTP calls.
The return value from `Contract` is a `ContractInstance`, so it is connected to your active provider and ready for transactions.

**NOTE**: Vyper contracts from Etherscan always return the name `Vyper_contract`.
However, if the plugin detects that the contract type has a method named `symbol`, it will use the return value from that call instead.

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## License

This project is licensed under the [Apache 2.0](LICENSE).
