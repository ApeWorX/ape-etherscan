from typing import Optional

from ape.api import ExplorerAPI, PluginConfig
from ape.contracts import ContractInstance
from ape.exceptions import ProviderNotConnectedError
from ape.types import AddressType, ContractType
from ethpm_types.source import Source

from ape_etherscan.client import (
    ClientFactory,
    SourceCodeResponse,
    get_etherscan_api_uri,
    get_etherscan_uri,
)
from ape_etherscan.types import EtherscanInstance
from ape_etherscan.verify import SourceVerifier


class Etherscan(ExplorerAPI):
    @property
    def _config(self) -> PluginConfig:
        return self.config_manager.get_config("etherscan")

    @property
    def etherscan_uri(self):
        return get_etherscan_uri(
            self._config, self.network.ecosystem.name, self.network.name.replace("-fork", "")
        )

    @property
    def etherscan_api_uri(self):
        return get_etherscan_api_uri(
            self._config, self.network.ecosystem.name, self.network.name.replace("-fork", "")
        )

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

    def get_source(self, address: AddressType) -> Source:
        code = self._get_source_code(address)
        return Source(content=code.source_code)

    def _get_source_code(self, address: AddressType) -> SourceCodeResponse:
        if not self.conversion_manager.is_type(address, AddressType):
            # Handle non-checksummed addresses
            address = self.conversion_manager.convert(str(address), AddressType)

        client = self._client_factory.get_contract_client(address)
        return client.get_source_code()

    def get_contract_type(self, address: AddressType) -> Optional[ContractType]:
        source_code = self._get_source_code(address)
        contract_type = ContractType(abi=source_code.abi, contractName=source_code.name)
        if source_code.name == "Vyper_contract" and "symbol" in contract_type.view_methods:
            try:
                contract = ContractInstance(address, contract_type)
                contract_type.name = contract.symbol() or contract_type.name
            except ProviderNotConnectedError:
                pass

        return contract_type

    def publish_contract(self, address: AddressType):
        verifier = SourceVerifier(address, self._client_factory)
        return verifier.attempt_verification()
