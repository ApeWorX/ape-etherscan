# TODO: Remove in 0.9 and make this a calculated property.
API_KEY_ENV_KEY_MAP = {
    "arbitrum": "ARBISCAN_API_KEY",
    "avalanche": "SNOWTRACE_API_KEY",
    "base": "BASESCAN_API_KEY",
    "blast": "BLASTSCAN_API_KEY",
    "bsc": "BSCSCAN_API_KEY",
    "bttc": "BTTCSCAN_API_KEY",
    "celo": "CELOSCAN_API_KEY",
    "ethereum": "ETHERSCAN_API_KEY",
    "fantom": "FTMSCAN_API_KEY",
    "fraxtal": "FRAXSCAN_API_KEY",
    "gnosis": "GNOSISSCAN_API_KEY",
    "kroma": "KROMASCAN_API_KEY",
    "moonbeam": "MOONSCAN_API_KEY",
    "optimism": "OPTIMISTIC_ETHERSCAN_API_KEY",
    "polygon": "POLYGONSCAN_API_KEY",
    "polygon-zkevm": "POLYGON_ZKEVM_ETHERSCAN_API_KEY",
    "scroll": "SCROLLSCAN_API_KEY",
    "unichain": "UNISCAN_API_KEY",
}
NETWORKS = {
    "arbitrum": [
        "mainnet",
        "sepolia",
        "nova",
    ],
    "avalanche": [
        "mainnet",
        "fuji",
    ],
    "base": [
        "mainnet",
        "sepolia",
    ],
    "blast": [
        "mainnet",
        "sepolia",
    ],
    "bsc": [
        "mainnet",
        "testnet",
        "opbnb",
        "opbnb-testnet",
    ],
    "bttc": [
        "mainnet",
        "donau",
    ],
    "celo": [
        "mainnet",
        "alfajores",
    ],
    "ethereum": [
        "mainnet",
        "holesky",
        "sepolia",
    ],
    "fantom": [
        "opera",
        "testnet",
    ],
    "fraxtal": [
        "mainnet",
        "holesky",
    ],
    "gnosis": [
        "mainnet",
    ],
    "kroma": [
        "mainnet",
        "sepolia",
    ],
    "moonbeam": [
        "mainnet",
        "moonbase",
        "moonriver",
    ],
    "optimism": [
        "mainnet",
        "sepolia",
    ],
    "polygon": [
        "mainnet",
        "amoy",
    ],
    "polygon-zkevm": [
        "mainnet",
        "cardona",
    ],
    "scroll": [
        "mainnet",
        "sepolia",
        "testnet",
    ],
    "unichain": [
        "mainnet",
        "sepolia",
    ],
}
