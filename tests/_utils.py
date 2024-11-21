from ape_etherscan.client import get_supported_chains

# Every supported ecosystem / network combo as `[("ecosystem", "network") ... ]`
chain_ids = [c["chainid"] for c in get_supported_chains()]
