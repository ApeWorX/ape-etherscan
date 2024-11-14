from ape import plugins


@plugins.register(plugins.ExplorerPlugin)
def explorers():
    from ape_etherscan.explorer import Etherscan
    from ape_etherscan.utils import NETWORKS

    for ecosystem_name in NETWORKS:
        for network_name in NETWORKS[ecosystem_name]:
            yield ecosystem_name, network_name, Etherscan
            yield ecosystem_name, f"{network_name}-fork", Etherscan


@plugins.register(plugins.QueryPlugin)
def query_engines():
    from ape_etherscan.query import EtherscanQueryEngine

    yield EtherscanQueryEngine


@plugins.register(plugins.Config)
def config_class():
    from ape_etherscan.config import EtherscanConfig

    return EtherscanConfig


@plugins.register(plugins.DependencyPlugin)
def dependencies():
    from ape_etherscan.dependency import EtherscanDependency

    yield "etherscan", EtherscanDependency


def __getattr__(name: str):
    if name == "Etherscan":
        from ape_etherscan.explorer import Etherscan

        return Etherscan

    elif name == "EtherscanConfig":
        from ape_etherscan.config import EtherscanConfig

        return EtherscanConfig

    elif name == "EtherscanDependency":
        from ape_etherscan.dependency import EtherscanDependency

        return EtherscanDependency

    elif name == "EtherscanQueryEngine":
        from ape_etherscan.query import EtherscanQueryEngine

        return EtherscanQueryEngine

    elif name == "NETWORKS":
        from ape_etherscan.utils import NETWORKS

        return NETWORKS

    else:
        raise AttributeError(name)
