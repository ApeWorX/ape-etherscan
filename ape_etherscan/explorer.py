import json
from json.decoder import JSONDecodeError
from typing import Optional

import requests
from ape.api import ExplorerAPI
from ape.types import ABI, ContractType

ETHERSCAN_URI = (
    lambda n: (f"https://{n}.etherscan.io/" if n != "mainnet" else "https://etherscan.io/")
    + "{0}/{1}/"
)


def get_etherscan_uri(network_name):
    return (
        f"https://api-{network_name}.etherscan.io/api"
        if network_name != "mainnet"
        else "https://api.etherscan.io/api"
    )


class Etherscan(ExplorerAPI):
    def get_address_url(self, address: str) -> str:
        return ETHERSCAN_URI(self.network.name).format("address", address)

    def get_transaction_url(self, transaction_hash: str) -> str:
        return ETHERSCAN_URI(self.network.name).format("tx", transaction_hash)

    def get_contract_type(self, address: str) -> Optional[ContractType]:
        response = requests.get(
            get_etherscan_uri(self.network.name),
            params={"module": "contract", "action": "getsourcecode", "address": address},
        )
        response.raise_for_status()
        result = response.json().get("result")
        if not result or len(result) != 1:
            return None
        abi_string = result[0].get("ABI")
        if not abi_string:
            return None
        try:
            abi_list = json.loads(abi_string)
        except JSONDecodeError:
            return None
        abi = [ABI.from_dict(item) for item in abi_list]
        contractName = result[0].get("ContractName", "unknown")
        return ContractType(abi=abi, contractName=contractName)  # type: ignore
