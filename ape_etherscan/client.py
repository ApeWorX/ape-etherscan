import io
import json
import os
import random
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Union

from ape.utils import USER_AGENT, cached_property
from requests import Session

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


class EtherscanResponse:
    def __init__(self, response, ecosystem: str, raise_on_exceptions: bool):
        self.response = response
        self.ecosystem = ecosystem
        self.raise_on_exceptions = raise_on_exceptions

    @cached_property
    def value(self) -> Union[List, Dict, str]:
        try:
            response_data = self.response.json()
        except json.JSONDecodeError as err:
            # Etherscan may resond with HTML content.
            raise EtherscanResponseError(self.response, "Resource not found") from err

        message = response_data.get("message", "")
        is_error = response_data.get("isError", 0) or message == "NOTOK"
        if is_error and self.raise_on_exceptions:
            raise get_request_error(self.response, self.ecosystem)

        result = response_data.get("result", message)
        if not result or not isinstance(result, str):
            return result

        # Some errors come back as strings
        if result.startswith("Error!"):
            err_msg = result.split("Error!")[-1].strip()
            if self.raise_on_exceptions:
                raise EtherscanResponseError(self.response, err_msg)

            return err_msg

        try:
            # Sometimes, the response is a stringified JSON object or list
            return json.loads(result)
        except json.JSONDecodeError:
            return result


class _APIClient:
    DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

    session = Session()

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

    def _get(
        self,
        params: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        raise_on_exceptions: bool = True,
    ) -> EtherscanResponse:
        params = self.__authorize(params)
        return self._request(
            "GET", params=params, headers=headers, raise_on_exceptions=raise_on_exceptions
        )

    def _post(
        self, json_dict: Optional[Dict] = None, headers: Optional[Dict[str, str]] = None
    ) -> EtherscanResponse:
        data = self.__authorize(json_dict)
        return self._request("POST", data=data, headers=headers)

    def _request(
        self,
        method: str,
        raise_on_exceptions: bool = True,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> EtherscanResponse:
        headers = headers or self.DEFAULT_HEADERS
        response = self.session.request(
            method.upper(), self.base_uri, headers=headers, params=params, data=data
        )

        if raise_on_exceptions:
            response.raise_for_status()

        return EtherscanResponse(response, self._ecosystem_name, raise_on_exceptions)

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
        response = self._get(params=params)
        result = response.value or []

        if len(result) != 1:
            return SourceCodeResponse()

        data = result[0]
        abi = data.get("ABI") or ""
        name = data.get("ContractName") or "unknown"
        return SourceCodeResponse(abi, name)

    def verify_source_code(
        self,
        standard_json_output: Dict,
        compiler_version: str,
        contract_name: Optional[str] = None,
        optimization_used: bool = False,
        optimization_runs: Optional[int] = 200,
        constructor_arguments: Optional[str] = None,
        evm_version: Optional[str] = None,
        license_type: Optional[int] = None,
        libraries: Optional[Dict[str, str]] = None,
    ) -> str:
        libraries = libraries or {}
        if len(libraries) > 10:
            raise ValueError(f"Can only have up to 10 libraries (received {len(libraries)}).")

        if not compiler_version.startswith("v"):
            compiler_version = f"v{compiler_version}"

        json_dict = {
            **self.base_params,
            "action": "verifysourcecode",
            "codeformat": "solidity-standard-json-input",
            "compilerversion": compiler_version,
            "constructorArguements": constructor_arguments,
            "contractaddress": self._address,
            "contractname": contract_name,
            "evmversion": evm_version,
            "licenseType": license_type,
            "optimizationUsed": int(optimization_used),
            "runs": optimization_runs,
            "sourceCode": io.StringIO(json.dumps(standard_json_output)),
        }

        iterator = 1
        for lib_address, lib_name in libraries.items():
            json_dict[f"libraryname{iterator}"] = lib_name
            json_dict[f"libraryaddress{iterator}"] = lib_address
            iterator += 1

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return self._post(json_dict=json_dict, headers=headers).value

    def check_verify_status(self, guid: str) -> str:
        json_dict = {**self.base_params, "action": "checkverifystatus", "guid": guid}
        response = self._get(params=json_dict, raise_on_exceptions=False)
        return str(response.value)


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
        result = self._get(params=params).value

        if not isinstance(result, list):
            # For mypy
            raise ValueError(f"Unexpected result '{result}'")

        return result


class ClientFactory:
    def __init__(self, ecosystem_name: str, network_name: str):
        self._ecosystem_name = ecosystem_name
        self._network_name = network_name

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._ecosystem_name, self._network_name, contract_address)

    def get_account_client(self, account_address: str) -> AccountClient:
        return AccountClient(self._ecosystem_name, self._network_name, account_address)
