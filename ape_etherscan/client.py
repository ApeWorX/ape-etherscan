import json
import os
from typing import Dict, List, Optional, Union

import requests
from ape.utils import USER_AGENT

from ape_etherscan.exceptions import get_request_error
from ape_etherscan.utils import API_KEY_ENV_VAR_NAME


def get_etherscan_uri(network_name: str):
    return (
        f"https://{network_name}.etherscan.io"
        if network_name != "mainnet"
        else "https://etherscan.io"
    )


def get_etherscan_api_uri(network_name: str):
    return (
        f"https://api-{network_name}.etherscan.io/api"
        if network_name != "mainnet"
        else "https://api.etherscan.io/api"
    )


class _APIClient:
    DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

    def __init__(self, network_name: str, module_name: str):
        self._network_name = network_name
        self._module_name = module_name

    @property
    def base_uri(self) -> str:
        return get_etherscan_api_uri(self._network_name)

    @property
    def base_params(self) -> Dict:
        return {"module": self._module_name}

    def _get(self, params: Optional[Dict] = None) -> Union[List, Dict]:
        params = self.__authorize(params)
        return self._request("GET", params=params)

    def _post(self, json_dict: Optional[Dict] = None) -> Dict:
        json_dict = self.__authorize(json_dict)
        return self._request("POST", json=json_dict)

    def _request(self, method: str, *args, **kwargs) -> Union[List, Dict]:
        uri = f"{self.base_uri}"
        response = requests.request(method.upper(), self.base_uri, *args, **kwargs)
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("isError", 0) or response_data.get("message", "") == "NOTOK":
            raise get_request_error(response)

        result = response_data.get("result")
        if not result:
            raise get_request_error(response)

        if isinstance(result, str):
            # Sometimes, the response is a stringified JSON object or list
            result = json.loads(result)

        return result

    def __authorize(self, params_or_data: Optional[Dict] = None) -> Optional[Dict]:
        api_key = os.environ.get(API_KEY_ENV_VAR_NAME)
        if api_key and "apikey" not in params_or_data:
            params_or_data = params_or_data or {}
            params_or_data["apikey"] = api_key

        return params_or_data


class ContractClient(_APIClient):
    def __init__(self, network_name: str, address: str):
        self._address = address
        super().__init__(network_name, "contract")

    def get_source_code(self) -> Optional[Dict]:
        params = {**self.base_params, "action": "getsourcecode", "address": self._address}
        result = self._get(params=params)
        return result[0] if len(result) == 1 else None


class ClientFactory:
    def __init__(self, network_name: str):
        self._network_name = network_name

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._network_name, contract_address)
