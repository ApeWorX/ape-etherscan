import time
from pathlib import Path
from typing import Optional

from ape.contracts import ContractInstance
from ape.logging import logger
from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from ethpm_types import ContractType
from semantic_version import Version  # type: ignore

from ape_etherscan.client import AccountClient, ClientFactory, ContractClient
from ape_etherscan.exceptions import ContractVerificationError


class SourceVerifier(ManagerAccessMixin):
    def __init__(self, address: AddressType, client_factory: ClientFactory):
        self.address = address
        self.client_factory = client_factory

    @cached_property
    def account_client(self) -> AccountClient:
        return self.client_factory.get_account_client(str(self.address))

    @cached_property
    def contract_client(self) -> ContractClient:
        return self.client_factory.get_contract_client(str(self.address))

    @cached_property
    def _contract(self) -> ContractInstance:
        return self.chain_manager.contracts.instance_at(self.address)

    @property
    def _contract_type(self) -> ContractType:
        return self._contract.contract_type

    @property
    def _base_path(self) -> Path:
        return self.project_manager.contracts_folder

    @property
    def _source_path(self) -> Path:
        return self._base_path / self._contract_type.source_id

    @property
    def _ext(self) -> str:
        return self._source_path.suffix

    @cached_property
    def constructor_arguments(self):
        # The first receipt of a contract is its deploy
        # TODO: Replace with chain.history.get_txn call
        call = self.account_client.get_all_normal_transactions
        contract_txns = [tx for tx in call()]

        timeout = 20
        checks_done = 0
        while checks_done <= timeout:
            # If was just deployed, it takes a few seconds to show up in API response
            contract_txns = [tx for tx in call()]
            if contract_txns:
                break

            logger.debug("Waiting for deploy receipt in Etherscan...")
            checks_done += 1
            time.sleep(2.5)

        if not contract_txns:
            raise ContractVerificationError(
                f"Failed to find to deploy receipt for '{self.address}'"
            )

        deploy_receipt = contract_txns[0]
        bytecode_len = len(self._contract_type.runtime_bytecode.bytecode)
        start_index = bytecode_len
        return deploy_receipt["input"][start_index:]

    @cached_property
    def license_code(self) -> Optional[int]:
        spdx_key = "SPDX-License-Identifier: "
        license_keyword_map = {
            "unlicense": 2,
            "mit": 3,
            "gpl-2.0": 4,
            "gpl-3.0": 5,
            "lgpl-2.1": 6,
            "lgpl-3.0": 7,
            "bsd-2-clause": 8,
            "bsd-3-clause": 9,
            "mpl-2.0": 10,
            "osl-3.0": 11,
            "apache 2.0": 12,
            "agpl-3.0-only": 13,
            "agpl-3.0-later": 13,
            "busl-1.1": 14,
        }
        license_type = 1

        # Determine license type from SPDX-ID
        first_line = self._source_path.read_text().split("\n")[0]
        if spdx_key not in first_line:
            return license_type

        license_id = first_line.split(spdx_key)[-1].strip().lower()
        license_type = license_keyword_map.get(license_id, 1)
        if license_type:
            return license_type

        logger.warning(f"Unsupported license type '{license_id}'.")
        return license_type

    def attempt_verification(self):
        compiler = self.compiler_manager.registered_compilers[self._ext]
        manifest = self.project_manager.extract_manifest()
        compiler_used = [
            c for c in manifest.compilers if self._contract_type.name in c.contractTypes
        ][0]
        optimizer = compiler_used.settings.get("optimizer", {})
        optimized = optimizer.get("enabled", False)
        runs = optimizer.get("runs", 200)
        source_name = self._contract_type.source_id
        sources = {source_name: {"content": manifest.sources[source_name].content}}
        all_settings = compiler.get_compiler_settings(
            [self._source_path], base_path=self._base_path
        )
        settings = all_settings[Version(compiler_used.version)]

        # TODO: Handle libraries, and metadata.
        source_code = {
            "language": compiler.name.capitalize(),
            "sources": sources,
            "settings": settings,
        }

        evm_version = compiler_used.settings.get("evmVersion")
        guid = self.contract_client.verify_source_code(
            source_code,
            compiler_used.version,
            contract_name=f"{self._contract_type.source_id}:{self._contract_type.name}",
            optimization_used=optimized,
            optimization_runs=runs,
            constructor_arguments=self.constructor_arguments,
            evm_version=evm_version,
            license_type=self.license_code,
        )
        self._wait_for_verification(guid)

    def _wait_for_verification(self, guid: str):
        iterations = 0
        timeout = 100
        while iterations < 25:
            verification_update = self.contract_client.check_verify_status(guid)
            fail_key = "Fail - "
            pass_key = "Pass - "
            if verification_update.startswith(fail_key):
                err_msg = verification_update.split(fail_key)[-1].strip()
                raise ContractVerificationError(err_msg)
            elif verification_update == "Already Verified" or verification_update.startswith(
                pass_key
            ):
                uri = self.provider.network.explorer.get_address_url(self.address)
                logger.success(f"Contract verification successful!\n{uri}#code")
                break

            status_message = f"Contract verification status: {verification_update}"
            logger.info(status_message)

            time.sleep(2.5)
            iterations += 1
            if iterations == timeout:
                raise ContractVerificationError("Timed out waiting for contract verification.")