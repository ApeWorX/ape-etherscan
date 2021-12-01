from ape.api import ExplorerAPI
from ape.types import ABI, ContractType
from typing import List
import requests
import json

ETHERSCAN_URI = (
    lambda n: (f"https://{n}.etherscan.io/" if n != "mainnet" else "https://etherscan.io/")
    + "{0}/{1}/"
)

def get_etherscan_uri(network_name):
    return f"https://api-{n}.etherscan.io/api" if network_name != "mainnet" else "https://api.etherscan.io/api"


class Etherscan(ExplorerAPI):
    def get_address_url(self, address: str) -> str:
        return ETHERSCAN_URI(self.network.name).format("address", address)

    def get_transaction_url(self, transaction_hash: str) -> str:
        return ETHERSCAN_URI(self.network.name).format("tx", transaction_hash)

    def get_contract_type(self, address: str) -> List[ABI]:
        response = requests.get(
            get_etherscan_uri(self.network.name),
            params={"module": "contract", "action": "getsourcecode", "address": address},
        )
        abi_string = response.json()["result"][0]["ABI"]
        abi = [ABI.from_dict(item) for item in json.loads(abi_string)]
        contractName = response.json()["result"][0]["ContractName"]
        return ContractType(abi=abi, contractName=contractName)
