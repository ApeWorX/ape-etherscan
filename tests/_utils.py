from ape_etherscan import NETWORKS

# Every supported ecosystem / network combo as `[("ecosystem", "network") ... ]`
ecosystems_and_networks = [
    p
    for plist in [
        [(e, n) for n in nets] + [(e, f"{n}-fork") for n in nets] for e, nets in NETWORKS.items()
    ]
    for p in plist
]
