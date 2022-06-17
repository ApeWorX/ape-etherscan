# Ape Etherscan Plugin

Etherscan Explorer Plugin for Ethereum-based networks.

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
Use the `Contract` top-level ape construct to create contract instances.
When you have an explorer plugin installed and it locates a contract type at the give address, the `Contract` return-value will use that contract type.

```python
from ape import accounts, Contract

# The following with fetch a contract type from mainnet using the `ape-explorer` plugin.
# The contract type is then cached to disc (and in memory for the active session) so that subsequent invocations don't require HTTP calls.
# The return value from `Contract` is a `ContractInstance`, so it is connected to your active provider and ready for transactions.
contract_from_mainnet = Contract("0x55a8a39bc9694714e2874c1ce77aa1e599461e18")
receipt = contract_from_mainnet.call_mutable_method("arg0", sender=accounts.load("acct"))
```

**NOTE**: Vyper contracts from Etherscan always return the name `Vyper_contract`.
However, if the plugin detects that the contract type has a method named `symbol`, it will use the return value from that call instead.

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## License

This project is licensed under the [Apache 2.0](LICENSE).
