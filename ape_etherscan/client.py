import json
import os
import random
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Union

import requests
from ape.utils import USER_AGENT

from ape_etherscan.exceptions import (
    EtherscanResponseError,
    UnsupportedEcosystemError,
    get_request_error,
)
from ape_etherscan.utils import API_KEY_ENV_KEY_MAP


def get_etherscan_uri(ecosystem_name: str, network_name: str):
    if ecosystem_name == "ethereum":
        return (
            f"https://{network_name}.etherscan.io"
            if network_name != "mainnet"
            else "https://etherscan.io"
        )

    elif ecosystem_name == "fantom":
        return (
            f"https://{network_name}.ftmscan.com"
            if network_name != "opera"
            else "https://ftmscan.com"
        )

    elif ecosystem_name == "arbitrum":
        return (
            f"https://{network_name}.arbiscan.io"
            if network_name != "mainnet"
            else "https://arbiscan.io"
        )
    elif ecosystem_name == "optimism":
        return (
            "https://optimistic.etherscan.io"
            if network_name == "mainnet"
            else "https://kovan-optimistic.etherscan.io"
        )

    raise UnsupportedEcosystemError(ecosystem_name)


def get_etherscan_api_uri(ecosystem_name: str, network_name: str):
    if ecosystem_name == "ethereum":
        return (
            f"https://api-{network_name}.etherscan.io/api"
            if network_name != "mainnet"
            else "https://api.etherscan.io/api"
        )

    elif ecosystem_name == "fantom":
        return (
            f"https://api-{network_name}.ftmscan.com"
            if network_name != "opera"
            else "https://api.ftmscan.com/api"
        )

    elif ecosystem_name == "arbitrum":
        return (
            f"https://api-{network_name}.arbiscan.io/api"
            if network_name != "mainnet"
            else "https://api.arbiscan.io/api"
        )
    elif ecosystem_name == "optimism":
        return (
            "https://api-optimistic.etherscan.io/api"
            if network_name == "mainnet"
            else "https://api-kovan-optimistic.etherscan.io/api"
        )
    raise UnsupportedEcosystemError(ecosystem_name)


@dataclass
class SourceCodeResponse:
    abi: str = ""
    name: str = "unknown"


class _APIClient:
    DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

    def __init__(self, ecosystem_name: str, network_name: str, module_name: str):
        self._ecosystem_name = ecosystem_name
        self._network_name = network_name
        self._module_name = module_name

    @property
    def base_uri(self) -> str:
        return get_etherscan_api_uri(self._ecosystem_name, self._network_name)

    @property
    def base_params(self) -> Dict:
        return {"module": self._module_name}

    def _get(self, params: Optional[Dict] = None) -> Union[List, Dict]:
        params = self.__authorize(params)
        return self._request("GET", params=params, headers=self.DEFAULT_HEADERS)

    def _post(self, json_dict: Optional[Dict] = None) -> Dict:
        json_dict = self.__authorize(json_dict)
        return self._request("POST", json=json_dict, headers=self.DEFAULT_HEADERS)  # type: ignore

    def _request(self, method: str, *args, **kwargs) -> Union[List, Dict]:
        response = requests.request(method.upper(), self.base_uri, *args, **kwargs)
        response.raise_for_status()

        try:
            response_data = response.json()
        except json.JSONDecodeError as err:
            # Etherscan may resond with HTML content.
            raise EtherscanResponseError(response, "Resource not found") from err

        if response_data.get("isError", 0) or response_data.get("message", "") == "NOTOK":
            raise get_request_error(response, self._network_name)

        result = response_data.get("result")
        if result and isinstance(result, str):
            # Sometimes, the response is a stringified JSON object or list
            result = json.loads(result)

        return result

    def __authorize(self, params_or_data: Optional[Dict] = None) -> Optional[Dict]:
        env_var_key = API_KEY_ENV_KEY_MAP.get(self._ecosystem_name)
        if not env_var_key:
            return params_or_data

        api_key = os.environ.get(env_var_key)
        if api_key and (not params_or_data or "apikey" not in params_or_data):
            params_or_data = params_or_data or {}
            api_key = random.choice(api_key.split(","))
            params_or_data["apikey"] = api_key.strip()

        return params_or_data


class ContractClient(_APIClient):
    def __init__(self, ecosystem_name: str, network_name: str, address: str):
        self._address = address
        super().__init__(ecosystem_name, network_name, "contract")

    def get_source_code(self) -> SourceCodeResponse:
        params = {**self.base_params, "action": "getsourcecode", "address": self._address}
        result = self._get(params=params) or []

        if len(result) != 1:
            return SourceCodeResponse()

        data = result[0]
        abi = data.get("ABI") or ""
        name = data.get("ContractName") or "unknown"
        return SourceCodeResponse(abi, name)


class AccountClient(_APIClient):
    def __init__(self, ecosystem_name: str, network_name: str, address: str):
        self._address = address
        super().__init__(ecosystem_name, network_name, "account")

    def get_all_normal_transactions(
        self,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        offset: int = 100,
        sort: str = "asc",
    ) -> Iterator[Dict]:
        page_num = 1
        last_page_results = offset  # Start at offset to trigger iteration
        while last_page_results == offset:
            page = self._get_page_of_normal_transactions(
                page_num, start_block, end_block, offset=offset, sort=sort
            )

            if len(page):
                yield from page

            last_page_results = len(page)
            page_num += 1

    def _get_page_of_normal_transactions(
        self,
        page: int,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        offset: int = 100,
        sort: str = "asc",
    ) -> List[Dict]:
        params = {
            **self.base_params,
            "action": "txlist",
            "address": self._address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
        }
        result = self._get(params=params)
        return result  # type: ignore


class ClientFactory:
    def __init__(self, ecosystem_name: str, network_name: str):
        self._ecosystem_name = ecosystem_name
        self._network_name = network_name

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._ecosystem_name, self._network_name, contract_address)

    def get_account_client(self, account_address: str) -> AccountClient:
        return AccountClient(self._ecosystem_name, self._network_name, account_address)
