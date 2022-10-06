import time
from enum import Enum
from pathlib import Path

from ape.contracts import ContractInstance
from ape.logging import logger
from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from ethpm_types import ContractType
from semantic_version import Version  # type: ignore

from ape_etherscan.client import AccountClient, ClientFactory, ContractClient
from ape_etherscan.exceptions import ContractVerificationError

_SPDX_ID_TO_API_CODE = {
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
_SPDX_ID_KEY = "SPDX-License-Identifier: "


class LicenseType(Enum):
    """
    https://etherscan.io/contract-license-types
    """

    NO_LICENSE = 1
    """
    Nobody else can copy, distribute, or modify your work without being at risk of
    take-downs, shake-downs, or litigation.
    """

    UNLICENSED = 2
    """
    A license with no conditions whatsoever which dedicates works to the public domain.
    """

    MIT = 3
    """
    Licensed works, modifications, and larger works may be distributed under different
    terms and without source code.
    """

    GPL_2 = 4
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/gpl-2.0.txt
    """

    GPL_3 = 5
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/gpl-3.0.txt
    """

    LGLP_2_1 = 6
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/lgpl-3.0.txt
    """

    LGLP_3 = 7
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/lgpl-3.0.txt
    """

    BSD_2_CLAUSE = 8
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/bsd-2-clause.txt
    """

    BSD_3_CLAUSE = 9
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/bsd-3-clause.txt
    """

    MPL_2 = 10
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/mpl-2.0.txt
    """

    OSL_3 = 11
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/osl-3.0.txt
    """

    APACHE = 2
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/apache-2.0.txt
    """

    AGLP_3 = 13
    """
    https://github.com/github/choosealicense.com/blob/gh-pages/_licenses/agpl-3.0.txt
    """

    BUSL_1_1 = 14
    """
    The BSL is structured to allow free and open usage for many use cases, and only requires
    a commercial license by those who make production use of the software, which is typically
    indicative of an environment that is delivering significant value to a business.
    """

    @classmethod
    def from_spdx_id(cls, spdx_id: str) -> "LicenseType":
        """
        Create an instance using the SPDX Identifier.

        Args:
            spdx_id (str): e.g. ``"// SPDX-License-Identifier: MIT"``

        Returns:
            ``LicenseType``
        """

        if _SPDX_ID_KEY not in spdx_id:
            return cls.NO_LICENSE

        license_id = spdx_id.split(_SPDX_ID_KEY)[-1].strip().lower()
        if license_id in _SPDX_ID_TO_API_CODE:
            return cls(_SPDX_ID_TO_API_CODE[license_id])

        logger.warning(f"Unsupported license type '{license_id}'.")
        return cls.NO_LICENSE


class SourceVerifier(ManagerAccessMixin):
    def __init__(self, address: AddressType, client_factory: ClientFactory):
        self.address = address
        self.client_factory = client_factory

    @cached_property
    def _account_client(self) -> AccountClient:
        return self.client_factory.get_account_client(str(self.address))

    @cached_property
    def _contract_client(self) -> ContractClient:
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
        return self._base_path / (self._contract_type.source_id or "")

    @property
    def _ext(self) -> str:
        return self._source_path.suffix

    @cached_property
    def constructor_arguments(self) -> str:
        """
        The arguments used when deploying the contract.
        """

        timeout = 20
        checks_done = 0
        deploy_receipt = None
        while checks_done <= timeout:
            # If was just deployed, it takes a few seconds to show up in API response

            try:
                deploy_receipt = next(self._account_client.get_all_normal_transactions())
            except StopIteration:
                continue

            logger.debug("Waiting for deploy receipt in Etherscan...")
            checks_done += 1
            time.sleep(2.5)

        if not deploy_receipt:
            raise ContractVerificationError(
                f"Failed to find to deploy receipt for '{self.address}'"
            )

        runtime_bytecode = self._contract_type.runtime_bytecode
        bytecode_len = 0
        if runtime_bytecode:
            bytecode_len = len(runtime_bytecode.bytecode or "")

        start_index = bytecode_len
        return deploy_receipt["input"][start_index:]

    @cached_property
    def license_code(self) -> LicenseType:
        """
        The license type used in the code.
        """

        spdx_id = self._source_path.read_text().split("\n")[0]
        return LicenseType.from_spdx_id(spdx_id)

    def attempt_verification(self):
        """
        Attempt to verify the source code.
        If the bytecode is already verified, Etherscan will use the existing bytecode
        and this method will still succeed.

        Raises:
            :class:`~ape_etherscan.exceptions.ContractVerificationError`: - When fails
              to validate the contract.
        """

        compiler = self.compiler_manager.registered_compilers[self._ext]
        manifest = self.project_manager.extract_manifest()
        compilers_used = [
            c for c in manifest.compilers if self._contract_type.name in c.contractTypes
        ]

        if not compilers_used:
            raise ContractVerificationError("Compiler data missing from project manifest.")

        compiler_used = compilers_used[0]
        optimizer = compiler_used.settings.get("optimizer", {})
        optimized = optimizer.get("enabled", False)
        runs = optimizer.get("runs", 200)
        source_name = self._contract_type.source_id
        sources = {source_name: {"content": manifest.sources[source_name].content}}
        all_settings = compiler.get_compiler_settings(
            [self._source_path], base_path=self._base_path
        )
        settings = all_settings[Version(compiler_used.version)]

        # TODO: Handle libraries
        source_code = {
            "language": compiler.name.capitalize(),
            "sources": sources,
            "settings": settings,
        }

        evm_version = compiler_used.settings.get("evmVersion")
        license_code = self.license_code
        license_code_value = None if not license_code else license_code.value
        guid = self._contract_client.verify_source_code(
            source_code,
            compiler_used.version,
            contract_name=f"{self._contract_type.source_id}:{self._contract_type.name}",
            optimization_used=optimized,
            optimization_runs=runs,
            constructor_arguments=self.constructor_arguments,
            evm_version=evm_version,
            license_type=license_code_value,
        )
        self._wait_for_verification(guid)

    def _wait_for_verification(self, guid: str):
        explorer = self.provider.network.explorer
        if not explorer:
            raise ContractVerificationError(
                f"Etherscan plugin missing for network {self.provider.network.name}"
            )

        for iteration in range(100):
            verification_update = self._contract_client.check_verify_status(guid)
            fail_key = "Fail - "
            pass_key = "Pass - "
            if verification_update.startswith(fail_key):
                err_msg = verification_update.split(fail_key)[-1].strip()
                raise ContractVerificationError(err_msg)
            elif verification_update == "Already Verified" or verification_update.startswith(
                pass_key
            ):
                uri = explorer.get_address_url(self.address)
                logger.success(f"Contract verification successful!\n{uri}#code")
                break

            status_message = f"Contract verification status: {verification_update}"
            logger.info(status_message)
            time.sleep(3)

        else:
            raise ContractVerificationError("Timed out waiting for contract verification.")
