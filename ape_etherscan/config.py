from ape.api.config import PluginConfig


class EcosystemConfig(PluginConfig):
    rate_limit: int = 5  # Requests per second
    retries: int = 5  # Number of retries before giving up


class EtherscanConfig(PluginConfig):
    ethereum: EcosystemConfig = EcosystemConfig()
    arbitrum: EcosystemConfig = EcosystemConfig()
    fantom: EcosystemConfig = EcosystemConfig()
    optimism: EcosystemConfig = EcosystemConfig()
    base: EcosystemConfig = EcosystemConfig()
    polygon_zkevm: EcosystemConfig = EcosystemConfig()
    polygon: EcosystemConfig = EcosystemConfig()
    avalanche: EcosystemConfig = EcosystemConfig()
    bsc: EcosystemConfig = EcosystemConfig()
    gnosis: EcosystemConfig = EcosystemConfig()
