import json
from typing import TYPE_CHECKING, Optional

from ape.api import ExplorerAPI, PluginConfig
from ape.contracts import ContractInstance
from ape.exceptions import ProviderNotConnectedError
from ape.types import AddressType, ContractType
from ethpm_types import Compiler, PackageManifest
from ethpm_types.source import Source

from ape_etherscan.client import (
    ClientFactory,
    SourceCodeResponse,
    get_etherscan_api_uri,
    get_etherscan_uri,
    get_supported_chains,
)
from ape_etherscan.exceptions import ContractNotVerifiedError
from ape_etherscan.types import EtherscanInstance
from ape_etherscan.verify import SourceVerifier

if TYPE_CHECKING:
    from ape.managers.project import ProjectManager


class Etherscan(ExplorerAPI):
    """
    The explorer API implementation for Etherscan.
    """

    @property
    def _config(self) -> PluginConfig:
        return self.config_manager.get_config("etherscan")

    @property
    def etherscan_uri(self):
        """
        The base URL of the explorer.
        """
        return get_etherscan_uri(
            self._config,
            self.network.ecosystem.name,
            self.network.name.replace("-fork", ""),
            self.network.chain_id,
        )

    @property
    def etherscan_api_uri(self):
        """
        The base URL for the API service.
        """
        return get_etherscan_api_uri(
            self._config,
            self.network.ecosystem.name,
            self.network.name.replace("-fork", ""),
            self.network.chain_id,
        )

    @classmethod
    def get_supported_chains(cls) -> list[dict]:
        """
        Get a list of chain data for all chains Etherscan supports.
        https://docs.etherscan.io/contract-verification/supported-chains

        Returns:
            list[dict]
        """
        return get_supported_chains()

    @classmethod
    def supports_chain(cls, chain_id: int) -> bool:
        chain_data = cls.get_supported_chains()
        chain_ids = [int(c["chainid"]) for c in chain_data if "chainid" in c]
        return chain_id in chain_ids

    def get_address_url(self, address: str) -> str:
        return f"{self.etherscan_uri}/address/{address}"

    def get_transaction_url(self, transaction_hash: str) -> str:
        return f"{self.etherscan_uri}/tx/{transaction_hash}"

    @property
    def _client_factory(self) -> ClientFactory:
        return ClientFactory(
            EtherscanInstance(
                ecosystem_name=self.network.ecosystem.name,
                network_name=self.network.name.replace("-fork", ""),
                uri=self.etherscan_uri,
                api_uri=self.etherscan_api_uri,
            )
        )

    def get_manifest(self, address: AddressType) -> Optional[PackageManifest]:
        """
        Get a package manifest.

        Args:
            address (AddressType): The address of a contract.

        Returns:
            ethpm_types.PackageManifest | None: None when the contract is not
            published.
        """
        try:
            response = self._get_source_code(address)
        except ContractNotVerifiedError:
            return None

        settings = {
            "optimizer": {
                "enabled": response.optimization_used,
                "runs": response.optimization_runs,
            },
        }

        code = response.source_code
        if code.startswith("{"):
            # JSON verified.
            data = json.loads(code)
            compiler = Compiler(
                name=data.get("language", "Solidity"),
                version=response.compiler_version,
                settings=data.get("settings", settings),
                contractTypes=[response.name],
            )
            source_data = data.get("sources", {})
            sources = {
                src_id: Source(content=cont.get("content", ""))
                for src_id, cont in source_data.items()
            }

        else:
            # A flattened source.
            source_id = f"{response.name}.sol"
            compiler = Compiler(
                name="Solidity",
                version=response.compiler_version,
                settings=settings,
                contractTypes=[response.name],
            )
            sources = {source_id: Source(content=response.source_code)}

        return PackageManifest(compilers=[compiler], sources=sources)

    def _get_source_code(self, address: AddressType) -> SourceCodeResponse:
        if not self.conversion_manager.is_type(address, AddressType):
            # Handle non-checksummed addresses
            address = self.conversion_manager.convert(str(address), AddressType)

        client = self._client_factory.get_contract_client(address)
        return client.get_source_code()

    def get_contract_type(self, address: AddressType) -> Optional[ContractType]:
        try:
            source_code = self._get_source_code(address)
        except ContractNotVerifiedError:
            return None

        contract_type = ContractType(abi=source_code.abi, contractName=source_code.name)
        if source_code.name == "Vyper_contract" and "symbol" in contract_type.view_methods:
            try:
                contract = ContractInstance(address, contract_type)
                contract_type.name = contract.symbol() or contract_type.name
            except ProviderNotConnectedError:
                pass

        return contract_type

    def publish_contract(self, address: AddressType):
        return self._publish_contract(address)

    def _publish_contract(self, address: AddressType, project: Optional["ProjectManager"] = None):
        verifier = SourceVerifier(address, self._client_factory, project=project)
        return verifier.attempt_verification()
