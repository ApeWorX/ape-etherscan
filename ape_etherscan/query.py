from typing import Iterator, Optional

from ape.api import QueryAPI, QueryType, ReceiptAPI
from ape.api.query import AccountTransactionQuery
from ape.exceptions import QueryEngineError
from ape.utils import singledispatchmethod

from ape_etherscan.client import ClientFactory


class EtherscanQueryEngine(QueryAPI):
    @property
    def _client_factory(self) -> ClientFactory:
        return ClientFactory(
            self.provider.network.ecosystem.name,
            self.provider.network.name.replace("-fork", ""),
        )

    @singledispatchmethod
    def estimate_query(self, query: QueryType) -> Optional[int]:  # type: ignore[override]
        return None

    @estimate_query.register
    def estimate_account_transaction_query(self, query: AccountTransactionQuery) -> int:
        # About 15 ms per page of 100 transactions
        return 1500 * (1 + query.stop_nonce - query.start_nonce) // 100

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
                receipt.transaction.nonce
                # TODO: Take advantage of nonces somehow to remove this if statement
                and query.start_nonce <= receipt.transaction.nonce <= query.stop_nonce
            ):
                yield receipt
