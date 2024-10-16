import json
import os
import random
import time
from collections.abc import Iterator
from io import StringIO
from typing import Optional

from ape.api import PluginConfig
from ape.logging import logger
from ape.utils import USER_AGENT, ManagerAccessMixin
from requests import Session
from yarl import URL

from ape_etherscan.config import EtherscanConfig
from ape_etherscan.exceptions import (
    ContractNotVerifiedError,
    IncompatibleCompilerSettingsError,
    UnhandledResultError,
    UnsupportedEcosystemError,
)
from ape_etherscan.types import (
    ContractCreationResponse,
    EtherscanInstance,
    EtherscanResponse,
    SourceCodeResponse,
)
from ape_etherscan.utils import API_KEY_ENV_KEY_MAP


def get_network_config(
    etherscan_config: EtherscanConfig, ecosystem_name: str, network_name: str
) -> Optional[PluginConfig]:
    if ecosystem_name in etherscan_config:
        return etherscan_config[ecosystem_name].get(network_name)
    return None


def get_etherscan_uri(
    etherscan_config: EtherscanConfig, ecosystem_name: str, network_name: str
) -> str:
    # Look for explicitly configured Etherscan config
    network_conf = get_network_config(etherscan_config, ecosystem_name, network_name)
    if network_conf and hasattr(network_conf, "uri"):
        return str(network_conf.uri)

    if ecosystem_name == "arbitrum":
        return (
            "https://arbiscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.arbiscan.io"
        )

    elif ecosystem_name == "avalanche":
        # TODO: In 0.9, change this to `snowscan` since that is Etherscan's official.
        return (
            "https://snowtrace.io" if network_name == "mainnet" else "https://testnet.snowtrace.io"
        )

    elif ecosystem_name == "base":
        return (
            "https://basescan.org"
            if network_name == "mainnet"
            else f"https://{network_name}.basescan.org"
        )

    elif ecosystem_name == "blast":
        return (
            "https://blastscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.blastscan.io"
        )

    elif ecosystem_name == "bsc":
        return (
            "https://bscscan.com"
            if network_name == "mainnet"
            else f"https://{network_name}.bscscan.com"
        )

    elif ecosystem_name == "bttc":
        if network_name == "mainnet":
            return "https://bttcscan.com"
        elif network_name == "donau":
            return "https://testnet.bttcscan.com"
        else:
            # NOTE: At time of writing, no other networks would hit this;
            #   the intent is to be more future-proof.
            return f"https://{network_name}.bttcscan.com"

    elif ecosystem_name == "celo":
        return (
            "https://celoscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.celoscan.io"
        )

    elif ecosystem_name == "ethereum":
        return (
            "https://etherscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.etherscan.io"
        )

    elif ecosystem_name == "fantom":
        return (
            "https://ftmscan.com"
            if network_name == "opera"
            else f"https://{network_name}.ftmscan.com"
        )

    elif ecosystem_name == "fraxtal":
        return (
            "https://fraxscan.com"
            if network_name == "mainnet"
            else f"https://{network_name}.fraxscan.com"
        )

    elif ecosystem_name == "gnosis":
        return (
            "https://gnosisscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.gnosisscan.io"
        )

    elif ecosystem_name == "kroma":
        return (
            "https://kromascan.com"
            if network_name == "mainnet"
            else f"https://{network_name}.kromascan.com"
        )

    elif ecosystem_name == "moonbeam":
        return (
            "https://moonscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}.moonscan.io"
        )

    elif ecosystem_name == "optimism":
        return (
            "https://optimistic.etherscan.io"
            if network_name == "mainnet"
            else f"https://{network_name}-optimism.etherscan.io"
        )

    elif ecosystem_name == "polygon":
        return (
            "https://polygonscan.com"
            if network_name == "mainnet"
            else "https://amoy.polygonscan.com"
        )

    elif ecosystem_name == "polygon-zkevm":
        return (
            "https://zkevm.polygonscan.com"
            if network_name == "mainnet"
            else "https://cardona-zkevm.polygonscan.com"
        )

    elif ecosystem_name == "scroll":
        return (
            "https://scrollscan.com"
            if network_name == "mainnet"
            else f"https://{network_name}.scrollscan.com"
        )

    elif ecosystem_name == "unichain":
        return (
            "https://uniscan.xyz"
            if network_name == "mainnet"
            else f"https://{network_name}.uniscan.xyz"
        )

    raise UnsupportedEcosystemError(ecosystem_name)


def get_etherscan_api_uri(
    etherscan_config: EtherscanConfig, ecosystem_name: str, network_name: str
) -> str:
    # Look for explicitly configured Etherscan config
    network_conf = get_network_config(etherscan_config, ecosystem_name, network_name)
    if network_conf and hasattr(network_conf, "api_uri"):
        return str(network_conf.api_uri)

    if ecosystem_name == "arbitrum":
        return (
            "https://api.arbiscan.io/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.arbiscan.io/api"
        )

    elif ecosystem_name == "avalanche":
        return (
            "https://api.snowtrace.io/api"
            if network_name == "mainnet"
            else "https://api-testnet.snowtrace.io/api"
        )

    elif ecosystem_name == "base":
        return (
            "https://api.basescan.org/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.basescan.org/api"
        )

    elif ecosystem_name == "blast":
        return (
            "https://api.blastscan.io/api"
            if network_name == "mainnet"
            else "https://api-sepolia.blastscan.io/api"
        )

    elif ecosystem_name == "bsc":
        return (
            "https://api.bscscan.com/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.bscscan.com/api"
        )

    elif ecosystem_name == "bttc":
        if network_name == "mainnet":
            return "https://api.bttcscan.com/api"
        elif network_name == "donau":
            return "https://api-testnet.bttcscan.com/api"
        else:
            # NOTE: At time of writing, no other networks would hit this;
            #   the intent is to be more future-proof.
            return f"https://api-{network_name}.bttcscan.com/api"

    elif ecosystem_name == "celo":
        return (
            "https://api.celoscan.com/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.celoscan.com/api"
        )

    elif ecosystem_name == "ethereum":
        return (
            "https://api.etherscan.io/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.etherscan.io/api"
        )

    elif ecosystem_name == "fantom":
        return (
            "https://api.ftmscan.com/api"
            if network_name == "opera"
            else f"https://api-{network_name}.ftmscan.com/api"
        )

    elif ecosystem_name == "fraxtal":
        return (
            "https://api.fraxscan.com/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.fraxscan.com/api"
        )

    elif ecosystem_name == "gnosis":
        return (
            "https://api.gnosisscan.io/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.gnosisscan.io/api"
        )

    elif ecosystem_name == "kroma":
        return (
            "https://api.kromascan.com/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.kromascan.com/api"
        )

    elif ecosystem_name == "moonbeam":
        return (
            "https://api.moonscan.io/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.moonscan.io/api"
        )

    elif ecosystem_name == "optimism":
        return (
            "https://api-optimistic.etherscan.io/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}-optimistic.etherscan.io/api"
        )

    elif ecosystem_name == "polygon":
        return (
            "https://api.polygonscan.com/api"
            if network_name == "mainnet"
            else "https://api-amoy.polygonscan.com/api"
        )

    elif ecosystem_name == "polygon-zkevm":
        return (
            "https://api-zkevm.polygonscan.com/api"
            if network_name == "mainnet"
            else "https://api-cardona-zkevm.polygonscan.com/api"
        )

    elif ecosystem_name == "scroll":
        return (
            "https://api.scrollscan.com/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.scrollscan.com/api"
        )

    elif ecosystem_name == "unichain":
        return (
            "https://api.uniscan.xyz/api"
            if network_name == "mainnet"
            else f"https://api-{network_name}.uniscan.xyz/api"
        )

    raise UnsupportedEcosystemError(ecosystem_name)


class _APIClient(ManagerAccessMixin):
    DEFAULT_HEADERS = {"User-Agent": USER_AGENT}
    session = Session()

    def __init__(self, instance: EtherscanInstance, module_name: str):
        self._instance = instance
        self._module_name = module_name
        self._last_call = 0.0

    @property
    def base_uri(self) -> str:
        return self._instance.api_uri

    @property
    def base_params(self) -> dict:
        return {"module": self._module_name}

    @property
    def _rate_limit(self) -> int:
        config = self.config_manager.get_config("etherscan")
        return getattr(config, self.network_manager.ecosystem.name.lower()).rate_limit

    @property
    def _retries(self) -> int:
        config = self.config_manager.get_config("etherscan")
        return getattr(config, self.network_manager.ecosystem.name.lower()).retries

    @property
    def _min_time_between_calls(self) -> float:
        return 1 / self._rate_limit  # seconds / calls per second

    @property
    def _clean_uri(self) -> str:
        url = URL(self.base_uri).with_user(None).with_password(None)
        return f"{url.with_path('')}/[hidden]" if url.path else f"{url}"

    def _get(
        self,
        params: Optional[dict] = None,
        headers: Optional[dict[str, str]] = None,
        raise_on_exceptions: bool = True,
    ) -> EtherscanResponse:
        params = self.__authorize(params)

        # Rate limit
        if time.time() - self._last_call < self._min_time_between_calls:
            time_to_sleep = self._min_time_between_calls - (time.time() - self._last_call)
            logger.debug(f"Sleeping {time_to_sleep} seconds to avoid rate limit")
            # NOTE: Sleep time is in seconds (float for subseconds)
            time.sleep(time_to_sleep)

        self._last_call = time.time()

        return self._request(
            "GET",
            params=params,
            headers=headers,
            raise_on_exceptions=raise_on_exceptions,
        )

    def _post(
        self, json_dict: Optional[dict] = None, headers: Optional[dict[str, str]] = None
    ) -> EtherscanResponse:
        data = self.__authorize(json_dict)
        return self._request("POST", data=data, headers=headers)

    def _request(
        self,
        method: str,
        raise_on_exceptions: bool = True,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> EtherscanResponse:
        headers = headers or self.DEFAULT_HEADERS
        for i in range(self._retries):
            logger.debug(f"Request sent to {self._clean_uri}.")
            response = self.session.request(
                method.upper(),
                self.base_uri,
                headers=headers,
                params=params,
                data=data,
                timeout=1024,
            )
            if response.status_code == 429:
                time_to_sleep = 2**i
                logger.debug(f"Request was throttled. Retrying in {time_to_sleep} seconds.")
                time.sleep(time_to_sleep)
                continue

            # Recieved a real response unrelated to rate limiting.
            if raise_on_exceptions:
                response.raise_for_status()
            elif not 200 <= response.status_code < 300:
                logger.error(f"Response was not successful: {response.text}")

            break

        return EtherscanResponse(response, self._instance.ecosystem_name, raise_on_exceptions)

    def __authorize(self, params_or_data: Optional[dict] = None) -> Optional[dict]:
        env_var_key = API_KEY_ENV_KEY_MAP.get(self._instance.ecosystem_name)
        if not env_var_key:
            return params_or_data

        api_key = os.environ.get(env_var_key)
        if api_key and (not params_or_data or "apikey" not in params_or_data):
            params_or_data = params_or_data or {}
            api_key = random.choice(api_key.split(","))
            params_or_data["apikey"] = api_key.strip()

        return params_or_data


class ContractClient(_APIClient):
    def __init__(self, instance: EtherscanInstance, address: str):
        self._address = address
        super().__init__(instance, "contract")

    def get_source_code(self) -> SourceCodeResponse:
        params = {
            **self.base_params,
            "action": "getsourcecode",
            "address": self._address,
        }
        result = self._get(params=params)

        if not (result_list := result.value):
            return SourceCodeResponse()

        elif len(result_list) > 1:
            raise UnhandledResultError(result, result_list)

        data = result_list[0]
        if not isinstance(data, dict):
            raise UnhandledResultError(result, data)

        if data.get("ABI") == "Contract source code not verified":
            raise ContractNotVerifiedError(result, self._address)

        return SourceCodeResponse.model_validate(data)

    def verify_source_code(
        self,
        standard_json_output: dict,
        compiler_version: str,
        contract_name: Optional[str] = None,
        optimization_used: bool = False,
        optimization_runs: Optional[int] = 200,
        constructor_arguments: Optional[str] = None,
        evm_version: Optional[str] = None,
        license_type: Optional[int] = None,
        libraries: Optional[dict[str, str]] = None,
        via_ir: bool = False,
    ) -> str:
        libraries = libraries or {}
        if len(libraries) > 10:
            raise ValueError(f"Can only have up to 10 libraries (received {len(libraries)}).")

        if not compiler_version.startswith("v"):
            compiler_version = f"v{compiler_version}"

        if "sourceCode" in standard_json_output:
            source_code = standard_json_output["sourceCode"]
            code_format = "solidity-single-file"
        else:
            source_code = StringIO(json.dumps(standard_json_output))
            code_format = "solidity-standard-json-input"

        json_dict = {
            **self.base_params,
            "action": "verifysourcecode",
            "codeformat": code_format,
            "compilerversion": compiler_version,
            "constructorArguements": constructor_arguments,
            "contractaddress": self._address,
            "contractname": contract_name,
            "evmversion": evm_version,
            "licenseType": license_type,
            "optimizationUsed": int(optimization_used),
            "runs": optimization_runs,
            "sourceCode": source_code,
        }
        iterator = 1
        for lib_address, lib_name in libraries.items():
            json_dict[f"libraryname{iterator}"] = lib_name
            json_dict[f"libraryaddress{iterator}"] = lib_address
            iterator += 1

        if code_format == "solidity-single-file" and via_ir:
            raise IncompatibleCompilerSettingsError("Solidity", "via_ir", via_ir)

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return str(self._post(json_dict=json_dict, headers=headers).value)

    def check_verify_status(self, guid: str) -> str:
        json_dict = {**self.base_params, "action": "checkverifystatus", "guid": guid}
        response = self._get(params=json_dict, raise_on_exceptions=False)
        return str(response.value)

    def get_creation_data(self) -> list[ContractCreationResponse]:
        params = {
            **self.base_params,
            "action": "getcontractcreation",
            "contractaddresses": [self._address],
        }
        result = self._get(params=params)
        items = result.value or []
        if not isinstance(items, list):
            raise ValueError("Expecting list.")

        return [ContractCreationResponse(**item) for item in items]


class AccountClient(_APIClient):
    def __init__(self, instance: EtherscanInstance, address: str):
        self._address = address
        super().__init__(instance, "account")

    def get_all_normal_transactions(
        self,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        offset: int = 100,
        sort: str = "asc",
    ) -> Iterator[dict]:
        page_num = 1
        last_page_results = offset  # Start at offset to trigger iteration
        while last_page_results == offset:
            page = self._get_page_of_normal_transactions(
                page_num, start_block, end_block, offset=offset, sort=sort
            )
            new_items = len(page)
            if new_items:
                yield from page

            last_page_results = new_items
            page_num += 1
            if new_items <= 0:
                # No more items. Break now to avoid 500 errors.
                break

    def _get_page_of_normal_transactions(
        self,
        page: int,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        offset: int = 100,
        sort: str = "asc",
    ) -> list[dict]:
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

        value = result.value or []
        if not isinstance(value, list):
            raise UnhandledResultError(result, value)

        return value


class ClientFactory:
    def __init__(self, instance: EtherscanInstance):
        self._instance = instance

    def get_contract_client(self, contract_address: str) -> ContractClient:
        return ContractClient(self._instance, contract_address)

    def get_account_client(self, account_address: str) -> AccountClient:
        return AccountClient(self._instance, account_address)
