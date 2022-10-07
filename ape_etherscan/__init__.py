from ape import plugins

from .explorer import Etherscan

NETWORKS = {
    "ethereum": [
        "mainnet",
        "goerli",
    ],
    "fantom": [
        "opera",
        "testnet",
    ],
    "arbitrum": [
        "mainnet",
        "goerli",
    ],
    "optimism": [
        "mainnet",
        "goerli",
    ],
    "polygon": [
        "mainnet",
        "mumbai",
    ],
}


@plugins.register(plugins.ExplorerPlugin)
def explorers():
    for ecosystem_name in NETWORKS:
        for network_name in NETWORKS[ecosystem_name]:
            yield ecosystem_name, network_name, Etherscan
            yield ecosystem_name, f"{network_name}-fork", Etherscan
