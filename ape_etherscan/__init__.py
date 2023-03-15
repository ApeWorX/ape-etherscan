from ape import plugins

from .explorer import Etherscan
from .query import EtherscanQueryEngine

NETWORKS = {
    "ethereum": [
        "mainnet",
        "goerli",
    ],
    "arbitrum": [
        "mainnet",
        "goerli",
    ],
    "fantom": [
        "opera",
        "testnet",
    ],
    "optimism": [
        "mainnet",
        "goerli",
    ],
    "polygon": [
        "mainnet",
        "mumbai",
    ],
    "avalanche": [
        "mainnet",
        "fuji",
    ],
    "bsc": [
        "mainnet",
        "testnet",
    ],
}


@plugins.register(plugins.ExplorerPlugin)
def explorers():
    for ecosystem_name in NETWORKS:
        for network_name in NETWORKS[ecosystem_name]:
            yield ecosystem_name, network_name, Etherscan
            yield ecosystem_name, f"{network_name}-fork", Etherscan


@plugins.register(plugins.QueryPlugin)
def query_engines():
    yield EtherscanQueryEngine
