import json
from json.decoder import JSONDecodeError
from typing import Optional

from ape.api import ExplorerAPI
from ape.contracts import ContractInstance
from ape.exceptions import ProviderNotConnectedError
from ape.logging import logger
from ape.types import AddressType, ContractType

from ape_etherscan.client import ClientFactory, get_etherscan_uri
from ape_etherscan.utils import UNISWAP_V3_POOL_ABI, UNISWAP_V3_POSITIONS_NFT
from ape_etherscan.verify import SourceVerifier


class Etherscan(ExplorerAPI):
    def get_address_url(self, address: str) -> str:
        etherscan_uri = get_etherscan_uri(
            self.network.ecosystem.name, self.network.name.replace("-fork", "")
        )
        return f"{etherscan_uri}/address/{address}"

    def get_transaction_url(self, transaction_hash: str) -> str:
        etherscan_uri = get_etherscan_uri(
            self.network.ecosystem.name, self.network.name.replace("-fork", "")
        )
        return f"{etherscan_uri}/tx/{transaction_hash}"

    @property
    def _client_factory(self) -> ClientFactory:
        return ClientFactory(self.network.ecosystem.name, self.network.name.replace("-fork", ""))

    def get_contract_type(self, address: AddressType) -> Optional[ContractType]:
        if not self.conversion_manager.is_type(address, AddressType):
            # Handle non-checksummed addresses
            address = self.conversion_manager.convert(str(address), AddressType)

        contract_client = self._client_factory.get_contract_client(address)
        source_code = contract_client.get_source_code()
        if not (abi_string := source_code.abi):
            return None

        try:
            abi = json.loads(abi_string)
        except JSONDecodeError as err:
            contract_creation = contract_client.get_creation_data()
            if not contract_creation:
                return None

            if not hasattr(contract_creation[0], "txHash"):
                return None

            tx_hash = contract_creation[0].txHash
            if not tx_hash:
                return None

            proxy_client = self._client_factory.get_proxy_client(tx_hash)
            transaction_by_hash = proxy_client.get_transaction_by_hash()
            if not (to_address := transaction_by_hash.toAddress):
                return None

            if not self.conversion_manager.is_type(to_address, AddressType):
                to_address = self.conversion_manager.convert(str(to_address), AddressType)

            if to_address == UNISWAP_V3_POSITIONS_NFT:
                abi = UNISWAP_V3_POOL_ABI

            else:
                logger.error(f"Error with contract ABI: {err}")
                return None

        contract_type = ContractType(abi=abi, contractName=source_code.name)
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
