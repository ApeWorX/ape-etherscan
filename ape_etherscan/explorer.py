import json
from json.decoder import JSONDecodeError
from typing import Optional, Iterator

from ape.api import ExplorerAPI, ReceiptAPI, TransactionStatusEnum
from ape.types import ABI, ContractType, AddressType

from ape_etherscan.client import ClientFactory, get_etherscan_uri
from ape_ethereum.ecosystem import Receipt


class Etherscan(ExplorerAPI):
    def get_address_url(self, address: str) -> str:
        return f"{get_etherscan_uri(self.network.name)}/address/{address}"

    def get_transaction_url(self, transaction_hash: str) -> str:
        return f"{get_etherscan_uri(self.network.name)}/tx/{transaction_hash}"

    @property
    def _client_factory(self):
        return ClientFactory(self.network.name)

    def get_contract_type(self, address: str) -> Optional[ContractType]:
        client = self._client_factory.get_contract_client(address)
        source_code = client.get_source_code() or {}
        abi_string = source_code.get("ABI")
        if not abi_string:
            return None

        try:
            abi_list = json.loads(abi_string)
        except JSONDecodeError:
            return None

        abi = [ABI.from_dict(item) for item in abi_list]
        contract_name = source_code.get("ContractName", "unknown")
        return ContractType(abi=abi, contractName=contract_name)  # type: ignore

    def get_account_transactions(self, address: AddressType) -> Iterator[ReceiptAPI]:
        client = self._client_factory.get_account_client(address)
        for page_of_transactions in client.get_all_normal_transactions():
            transactions = page_of_transactions
            for transaction in transactions:
                if "confirmations" in transaction:
                    transaction["required_confirmations"] = transaction.pop("confirmations")
                if "txreceipt_status" in transaction:
                    transaction["status"] = transaction.pop("txreceipt_status")

                yield Receipt.decode(transaction)
