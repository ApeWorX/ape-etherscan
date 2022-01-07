from typing import Dict, List, Optional, Iterator

import requests
from ape.exceptions import ApeException
from ape.utils import USER_AGENT
from requests import Response


def get_etherscan_uri(network_name: str):
    return (
        f"https://{network_name}.etherscan.io"
        if network_name != "mainnet"
        else "https://etherscan.io"
    )


def get_etherscan_api_uri(network_name: str, is_api=True):
    return (
        f"https://api-{network_name}.etherscan.io/api"
        if network_name != "mainnet"
        else "https://api.etherscan.io/api"
    )


class _APIClient:
    def __init__(self, network_name: str, module_name: str):
        self._network_name = network_name
        self._module_name = module_name

    @property
    def base_uri(self) -> str:
        return get_etherscan_api_uri(self._network_name)

    @property
    def base_params(self) -> Dict:
        return {"module": self._module_name}

    def _get(self, params: Optional[Dict] = None) -> List:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(self.base_uri, params=params, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("isError", 0) or response_data.get("message", "") == "NOTOK":
            raise ResponseError(response)

        result = response_data.get("result")
        if not result:
            raise ResponseError(response.text)

        return result


class ContractClient(_APIClient):
    def __init__(self, network_name: str, address: str):
        self._address = address
        super().__init__(network_name, "contract")

    def get_source_code(self) -> Optional[Dict]:
        params = {**self.base_params, "action": "getsourcecode", "address": self._address}
        result = self._get(params=params)
        return result[0] if len(result) == 1 else None


class AccountClient(_APIClient):
    def __init__(self, network_name: str, address: str):
        self._address = address
        super().__init__(network_name, "account")

    def get_all_normal_transactions(
        self,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        offset: int = 10,
        sort: str = "asc",
    ) -> Iterator[List[Dict]]:
        page_num = 1
        last_page_results = offset  # Start at offset to trigger iteration
        while last_page_results == offset:
            page = self._get_page_of_normal_transactions(
                page_num, start_block, end_block, offset=offset, sort=sort
            )

            if len(page):
                yield page

            last_page_results = len(page)
            page_num += 1

    def _get_page_of_normal_transactions(
        self, page: int, start_block: int, end_block: int, offset: int = 10, sort: str = "asc"
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
        return result


class ClientFactory:
    def __init__(self, network_name: str):
        self._network_name = network_name

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._network_name, contract_address)

    def get_account_client(self, account_address: str) -> AccountClient:
        return AccountClient(self._network_name, account_address)


class ResponseError(ApeException):
    """
    Raised when the response is not correct.
    """

    def __init__(self, response: Response):
        self.response = response
        response_data = response.json()
        if "result" in response_data:
            message = response_data["result"]
        elif "message" in response_data:
            message = response_data["message"]
        else:
            message = response.text

        super().__init__(f"Response indicated failure: {message}")
