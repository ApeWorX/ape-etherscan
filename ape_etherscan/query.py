from collections.abc import Iterator
from typing import Optional

from ape.api import PluginConfig, QueryAPI, QueryType, ReceiptAPI
from ape.api.query import AccountTransactionQuery, ContractCreationQuery
from ape.exceptions import QueryEngineError
from ape.utils import singledispatchmethod

from ape_etherscan.client import ClientFactory, get_etherscan_api_uri, get_etherscan_uri
from ape_etherscan.types import EtherscanInstance
from ape_etherscan.utils import NETWORKS


class EtherscanQueryEngine(QueryAPI):
    @property
    def _client_factory(self) -> ClientFactory:
        return ClientFactory(
            EtherscanInstance(
                ecosystem_name=self.provider.network.ecosystem.name,
                network_name=self.provider.network.name.replace("-fork", ""),
                uri=self.etherscan_uri,
                api_uri=self.etherscan_api_uri,
            )
        )

    @property
    def _config(self) -> PluginConfig:
        return self.config_manager.get_config("etherscan")

    @property
    def etherscan_uri(self):
        return get_etherscan_uri(
            self._config,
            self.provider.network.ecosystem.name,
            self.provider.network.name.replace("-fork", ""),
        )

    @property
    def etherscan_api_uri(self):
        return get_etherscan_api_uri(
            self._config,
            self.provider.network.ecosystem.name,
            self.provider.network.name.replace("-fork", ""),
        )

    @singledispatchmethod
    def estimate_query(self, query: QueryType) -> Optional[int]:  # type: ignore[override]
        return None

    @property
    def rate_limit(self) -> int:
        config = self.config_manager.get_config("etherscan")
        return getattr(config, self.network_manager.ecosystem.name.lower()).rate_limit

    @estimate_query.register
    def estimate_account_transaction_query(self, query: AccountTransactionQuery) -> Optional[int]:
        if self.network_manager.active_provider:
            # Ignore unsupported networks.
            ecosystem = self.network_manager.provider.network.ecosystem.name
            network = self.network_manager.provider.network.name
            if network not in NETWORKS.get(ecosystem, {}):
                return None

        # About 15 ms per page of 100 transactions, with rate limit applied
        if query.stop_nonce - query.stop_nonce <= 100:
            return 15

        return (10000 // self.rate_limit) * (1 + query.stop_nonce - query.start_nonce) // 100

    @estimate_query.register
    def estimate_contract_creation_query(self, query: ContractCreationQuery) -> Optional[int]:
        if self.network_manager.active_provider:
            # Ignore unsupported networks.
            ecosystem = self.network_manager.provider.network.ecosystem.name
            network = self.network_manager.provider.network.name
            if network not in NETWORKS.get(ecosystem, {}):
                return None

        # About 300 ms per query
        return 300

    @singledispatchmethod
    def perform_query(self, query: QueryType) -> Iterator:  # type: ignore[override]
        raise QueryEngineError(
            f"{self.__class__.__name__} cannot handle {query.__class__.__name__} queries."
        )

    @perform_query.register
    def get_account_transactions(self, query: AccountTransactionQuery) -> Iterator[ReceiptAPI]:
        client = self._client_factory.get_account_client(query.account)
        chain_id = self.provider.chain_id  # TODO: Cache this somehow [APE-635]
        for receipt_data in client.get_all_normal_transactions():
            if "confirmations" in receipt_data:
                receipt_data["required_confirmations"] = receipt_data.pop("confirmations")
            if "txreceipt_status" in receipt_data:
                # NOTE: Etherscan uses `""` for `0` in the receipt status.
                status = receipt_data.pop("txreceipt_status") or 0
                receipt_data["status"] = status

            if receipt_data.get("nonce") == "":
                receipt_data["nonce"] = None

            receipt_data["from"] = self.provider.network.ecosystem.decode_address(
                receipt_data["from"]
            )
            receipt_data["chainId"] = chain_id

            receipt = self.provider.network.ecosystem.decode_receipt(receipt_data)

            # NOTE: Required for `elif` leg to function
            if receipt.sender != query.account:
                # Likely ``query.account`` is a contract.
                # Cache the receipts by their sender instead and skip them here.
                self.chain_manager.history.append(receipt)

            elif (
                receipt.transaction.nonce is not None  # Just for mypy
                # TODO: Take advantage of nonces somehow to remove this if statement
                and query.start_nonce <= receipt.transaction.nonce <= query.stop_nonce
            ):
                yield receipt

    @perform_query.register
    def get_contract_creation_receipt(self, query: ContractCreationQuery) -> Iterator[ReceiptAPI]:
        client = self._client_factory.get_contract_client(query.contract)
        creation_data = client.get_creation_data()
        if len(creation_data) == 0:
            return
        elif len(creation_data) != 1:
            raise ValueError("Expecting single creation data.")

        yield self.chain_manager.get_receipt(creation_data[0].txHash)
