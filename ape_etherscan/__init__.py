from ape import plugins

from .config import EtherscanConfig
from .dependency import EtherscanDependency
from .explorer import Etherscan
from .query import EtherscanQueryEngine
from .utils import NETWORKS


@plugins.register(plugins.ExplorerPlugin)
def explorers():
    for ecosystem_name in NETWORKS:
        for network_name in NETWORKS[ecosystem_name]:
            yield ecosystem_name, network_name, Etherscan
            yield ecosystem_name, f"{network_name}-fork", Etherscan


@plugins.register(plugins.QueryPlugin)
def query_engines():
    yield EtherscanQueryEngine


@plugins.register(plugins.Config)
def config_class():
    return EtherscanConfig


@plugins.register(plugins.DependencyPlugin)
def dependencies():
    yield "etherscan", EtherscanDependency
