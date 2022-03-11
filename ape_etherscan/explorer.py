import json
from json.decoder import JSONDecodeError
from typing import Iterator, Optional

from ape.api import ExplorerAPI, ReceiptAPI
from ape.types import AddressType, ContractType

from ape_etherscan.client import ClientFactory, get_etherscan_uri


class Etherscan(ExplorerAPI):
    def get_address_url(self, address: str) -> str:
        return f"{get_etherscan_uri(self.network.name)}/address/{address}"

    def get_transaction_url(self, transaction_hash: str) -> str:
        return f"{get_etherscan_uri(self.network.name)}/tx/{transaction_hash}"

    @property
    def _client_factory(self) -> ClientFactory:
        return ClientFactory(self.network.name)

    def get_contract_type(self, address: str) -> Optional[ContractType]:
        client = self._client_factory.get_contract_client(address)
        source_code = client.get_source_code()
        abi_string = source_code.abi
        if not abi_string:
            return None

        try:
            abi = json.loads(abi_string)
        except JSONDecodeError:
            return None

        return ContractType.parse_obj({"abi": abi, "contractName": source_code.name})

    def get_account_transactions(self, address: AddressType) -> Iterator[ReceiptAPI]:
        client = self._client_factory.get_account_client(address)
        for receipt_data in client.get_all_normal_transactions():
            if "confirmations" in receipt_data:
                receipt_data["required_confirmations"] = receipt_data.pop("confirmations")
            if "txreceipt_status" in receipt_data:
                # NOTE: Ethrscan uses `""` for `0` in the receipt status.
                status = receipt_data.pop("txreceipt_status") or 0
                receipt_data["status"] = status

            yield self.network.ecosystem.decode_receipt(receipt_data)
