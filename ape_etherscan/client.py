from typing import Dict, Optional

import requests
from ape.exceptions import ApeException
from ape.utils import USER_AGENT


def get_etherscan_uri(network_name):
    return (
        f"https://api-{network_name}.etherscan.io"
        if network_name != "mainnet"
        else "https://api.etherscan.io"
    )


def get_etherscan_api_uri(network_name):
    return f"{get_etherscan_uri(network_name)}/api"


class _BaseClient:
    def __init__(self, network_name: str, module_name: str):
        self._network_name = network_name
        self._module_name = module_name

    @property
    def base_uri(self) -> str:
        return get_etherscan_api_uri(self._network_name)

    @property
    def base_params(self) -> Dict:
        return {"module": self._module_name}

    def _get(self, params: Optional[Dict] = None) -> Dict:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(self.base_uri, params=params, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        result = response_data.get("result")
        if not result:
            raise ResponseError(response.text)

        return result


class ContractClient(_BaseClient):
    def __init__(self, network_name: str, address: str):
        self._address = address
        super().__init__(network_name, "contract")

    def get_source_code(self) -> Optional[Dict]:
        params = {**self.base_params, "action": "getsourcecode", "address": self._address}
        result = self._get(params=params)
        return result[0] if len(result) == 1 else None


class ResponseError(ApeException):
    """
    Raised when the response is not correct.
    """

    def __init__(self, response_text: str):
        super().__init__(f"Response is not expected:\n{response_text}")


class ClientFactory:
    def __init__(self, network_name: str):
        self._network_name = network_name

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._network_name, contract_address)
