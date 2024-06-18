# Quick Start

The following blockchain explorers are supported in this plugin:

- [Etherscan](https://etherscan.io/) for Ethereum networks.
- [Ftmscan](https://ftmscan.com) for Fantom networks.
- [Arbiscan](https://arbiscan.io) for Arbitrum networks.
- [Optimistic Etherscan](https://optimistic.etherscan.io) for Optimism networks.
- [Polygonscan](https://polygonscan.com) for Polygon networks.
- [Polygonscan ZkEVM](https://zkevm.polygonscan.com) for Polygon ZkEVM networks.
- [Snowtrace](https://snowtrace.io) for Avalanche networks.
- [Basescan](https://basescan.org) for Base networks.
- [Bscscan](https://bscscan.com) for Binance-Smart-Chain networks.
- [Blastscan](https://blastscan.io) for Blast networks.

## Dependencies

- [python3](https://www.python.org/downloads) version 3.9 up to 3.12.

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

You can obtain an API key by registering with Etherscan and visiting [this page](https://etherscan.io/myapikey).

```bash
export ETHERSCAN_API_KEY=SAMPLE_KEY
export FTMSCAN_API_KEY=SAMPLE_KEY
export ARBISCAN_API_KEY=SAMPLE_KEY
export POLYGON_ZKEVM_ETHERSCAN_API_KEY=SAMPLE_KEY
export BASESCAN_API_KEY=SAMPLE_KEY
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

## Contract Verification

Use the `ape-etherscan` plugin to publish and verify your contracts.
Contract verification associates a contract type from Ape with an Ethereum address on Etherscan.
Learn more about Etherscan verification [here](https://info.etherscan.com/types-of-contract-verification/).

To verify contract in Ape, you can set the `publish` key to `True` when deploying:

```python
from ape import accounts, project

account = accounts.load("testnetacct")
account.deploy(project.MyContract, publish=True)
```

You can also use the explorer class directly to publish at a later time:

```python
from ape import networks

etherscan = networks.provider.network.explorer
etherscan.publish_contract("0x55a8a39bc9694714e2874c1ce77aa1e599461e18")
```

Not every network's explorer supports multi-file verification.
For those networks, the corresponding compiler plugin's `flatten` functionality is invoked, in order to verify the contract as a single file.

**NOTE**: You must set an Etherscan API key environment variable to use the publishing feature.

## Custom Networks

If you would like to use ape-etherscan with your [custom network configuration](https://docs.apeworx.io/ape/stable/userguides/networks.html#custom-network-connection), you can use the same network identifier you used to configure it.
For instance, with a custom Ethereum network called "apechain" your configuration might look something like this:

```yaml
networks:
  custom:
    - name: apechain
      chain_id: 31337

node:
  ethereum:
    apechain:
      uri: http://localhost:8545

etherscan:
  ethereum:
    rate_limit: 15
    apechain:
      uri: https://custom.scan
      api_uri: https://api.custom.scan/api
```

## Dependencies

You can use dependencies from Etherscan in your projects.
Configure them like this:

```yaml
dependencies:
  - name: Spork
    etherscan: "0xb624FdE1a972B1C89eC1dAD691442d5E8E891469"
    ecosystem: ethereum
    network: mainnet
```

Then, access contract types from the dependency in your code:

```python
from ape import project

spork_contract_type = project.dependencies["Spork"]["etherscan"].Spork
```
