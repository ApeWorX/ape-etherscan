# Ape Etherscan Plugin

The following blockchain explorers are supported in this plugin:

* [Etherscan](https://etherscan.io/) for Ethereum networks.
* [Ftmscan](https://ftmscan.com) for Fantom networks.
* [Arbiscan]("https://arbiscan.io") for Arbitrum networks.
* [Optimistic Etherscan]("https://optimistic.etherscan.io") for Optimism networks.

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

## Set up the environment

Specify API keys as environment variables. You could put them in your shell's config like `~/.profile`
or use a tool like [direnv](https://direnv.net/) and store them locally in `.envrc`.

You can also specify multiple comma-separated keys, a random key will be chosen for each request.
This could be useful if you hit API rate limits.

You can obtain an API key by registering with Etherscan and visitng [this page](https://etherscan.io/myapikey).

```bash
export ETHERSCAN_API_KEY=SAMPLE_KEY
export FTMSCAN_API_KEY=SAMPLE_KEY
export ARBISCAN_API_KEY=SAMPLE_KEY
```

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

The first line `contract = Contract("0x55a8a39bc9694714e2874c1ce77aa1e599461e18")` checks if ape has a cached contract-type for the address `0x55a8a39bc9694714e2874c1ce77aa1e599461e18`.
If it does not find a cached contract type, it uses an explorer plugin to attempt to find one.
If found, the contract type is then cached to disk and in memory for the active session so that subsequent invocations don't require HTTP calls.
The return value from `Contract` is a `ContractInstance`, so it is connected to your active provider and ready for transactions.

**NOTE**: Vyper contracts from Etherscan always return the name `Vyper_contract`.
However, if the plugin detects that the contract type has a method named `symbol`, it will use the return value from that call instead.

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## License

This project is licensed under the [Apache 2.0](LICENSE).
