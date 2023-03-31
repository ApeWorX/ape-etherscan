from ape.api.config import PluginConfig


class EcosystemConfig(PluginConfig):
    rate_limit: int = 5  # Requests per second


class EtherscanConfig(PluginConfig):
    ethereum: EcosystemConfig = EcosystemConfig()
    arbitrum: EcosystemConfig = EcosystemConfig()
    fantom: EcosystemConfig = EcosystemConfig()
    optimism: EcosystemConfig = EcosystemConfig()
    polygon: EcosystemConfig = EcosystemConfig()
    avalanche: EcosystemConfig = EcosystemConfig()
    bsc: EcosystemConfig = EcosystemConfig()
