import json
import time
from json.decoder import JSONDecodeError
from typing import Iterator, Optional

from ape.api import ExplorerAPI, ReceiptAPI
from ape.contracts import ContractInstance
from ape.exceptions import ProviderNotConnectedError
from ape.logging import logger
from ape.types import AddressType, ContractType

from ape_etherscan.client import ClientFactory, get_etherscan_uri
from ape_etherscan.exceptions import ContractVerificationError
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

        contract_type = ContractType.parse_obj({"abi": abi, "contractName": source_code.name})
        if source_code.name == "Vyper_contract" and "symbol" in contract_type.view_methods:
            try:
                checksummed_address = self.provider.network.ecosystem.decode_address(address)
                contract = ContractInstance(checksummed_address, contract_type)
                contract_type.name = contract.symbol() or contract_type.name
            except ProviderNotConnectedError:
                pass

        return contract_type

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

    def publish_contract(self, address: AddressType):
        verifier = SourceVerifier(address, self._client_factory)
        return verifier.attempt_verification()

    def _wait_for_verification(self, contract_client, guid: str):
        iterations = 0
        timeout = 100
        while iterations < 25:
            verification_update = contract_client.check_verify_status(guid)
            fail_key = "Fail - "
            if verification_update.startswith(fail_key):
                err_msg = verification_update.split(fail_key)[-1].strip()
                raise ContractVerificationError(err_msg)

            status_message = f"Contract verification status: {verification_update}"
            logger.info(status_message)

            time.sleep(2.5)
            iterations += 1
            if iterations == timeout:
                raise ContractVerificationError("Timed out waiting for contract verification.")
