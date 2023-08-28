import json
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from ape.contracts import ContractInstance
from ape.logging import LogLevel, logger
from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from ethpm_types import ContractType
from semantic_version import Version  # type: ignore

from ape_etherscan.client import AccountClient, ClientFactory, ContractClient
from ape_etherscan.exceptions import ContractVerificationError, EtherscanResponseError

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
    "agpl-3.0": 13,
    "agpl-3.0-only": 13,
    "agpl-3.0-later": 13,
    "busl-1.1": 14,
}
_SPDX_ID_KEY = "SPDX-License-Identifier: "

ECOSYSTEMS_VERIFY_USING_JSON = ("ethereum",)


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
        if runtime_bytecode:
            return extract_constructor_arguments(
                deploy_receipt["input"], runtime_bytecode.bytecode or ""
            )
        else:
            raise ContractVerificationError("Failed to find runtime bytecode.")

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

        manifest = self.project_manager.extract_manifest()
        compilers_used = [
            c for c in manifest.compilers if self._contract_type.name in c.contractTypes
        ]

        if not compilers_used:
            raise ContractVerificationError("Compiler data missing from project manifest.")

        versions = [Version(c.version) for c in compilers_used]
        if not versions:
            # Might be impossible to get here.
            raise ContractVerificationError("Unable to find compiler version used.")

        elif len(versions) > 1:
            # Might be impossible to get here.
            logger.warning("Source was compiled by multiple versions. Using max.")
            version = max(versions)

        else:
            version = versions[0]

        compiler_plugin = self.compiler_manager.registered_compilers[self._ext]
        all_settings = compiler_plugin.get_compiler_settings(
            [self._source_path], base_path=self._base_path
        )
        settings = all_settings[version]
        optimizer = settings.get("optimizer", {})
        optimized = optimizer.get("enabled", False)
        runs = optimizer.get("runs", 200)
        source_id = self._contract_type.source_id
        base_folder = self.project_manager.contracts_folder
        standard_input_json = self._get_standard_input_json(source_id, base_folder, **settings)

        evm_version = settings.get("evmVersion")
        license_code = self.license_code
        license_code_value = license_code.value if license_code else None

        if logger.level == LogLevel.DEBUG:
            logger.debug("Dumping standard JSON output:\n")
            standard_json = json.dumps(standard_input_json, indent=2)
            logger.debug(f"{standard_json}\n")

        # NOTE: Etherscan does not allow directory prefixes on the source ID.
        if self.provider.network.ecosystem.name in ECOSYSTEMS_VERIFY_USING_JSON:
            request_source_id = Path(source_id).name
            contract_name = f"{request_source_id}:{self._contract_type.name}"
        else:
            # When we have a flattened contract, we don't need to specify the file name
            # only the contract name
            contract_name = f"{self._contract_type.name}"

        try:
            guid = self._contract_client.verify_source_code(
                standard_input_json,
                str(version),
                contract_name=contract_name,
                optimization_used=optimized,
                optimization_runs=runs,
                constructor_arguments=self.constructor_arguments,
                evm_version=evm_version,
                license_type=license_code_value,
            )
        except EtherscanResponseError as err:
            if "source code already verified" in str(err):
                logger.warning(str(err))
                return

            else:
                raise  # this error

        self._wait_for_verification(guid)

    def _get_standard_input_json(
        self, source_id: str, base_folder: Optional[Path] = None, **settings
    ) -> Dict:
        base_dir = base_folder or self.project_manager.contracts_folder
        source_path = base_dir / source_id
        compiler = self.compiler_manager.registered_compilers[source_path.suffix]
        sources = {self._source_path.name: {"content": source_path.read_text()}}

        def build_map(_source_id: str):
            _source_path = base_dir / _source_id
            source_imports = compiler.get_imports([_source_path]).get(_source_id, [])
            for imported_source_id in source_imports:
                sources[imported_source_id] = {
                    "content": (base_dir / imported_source_id).read_text()
                }
                build_map(imported_source_id)

        def flatten_source(_source_id: str) -> str:
            _source_path = base_dir / _source_id
            flattened_source = str(compiler.flatten_contract(_source_path))
            return flattened_source

        build_map(source_id)

        # "libraries" field not allows in `settings` dict.
        if "libraries" in settings:
            # libraries are handled below.
            settings.pop("libraries")

        if self.provider.network.ecosystem.name in ECOSYSTEMS_VERIFY_USING_JSON:
            # Use standard input json format
            data = {
                "language": compiler.name.capitalize(),
                "sources": sources,
                "settings": settings,
            }
        else:
            # Use flattened source, single-file approach
            data = {
                "language": compiler.name.capitalize(),
                "sourceCode": flatten_source(source_id),
                "settings": settings,
            }

        if hasattr(compiler, "libraries") and compiler.libraries:
            libraries = compiler.libraries
            index = 1
            max_libraries = 10
            for _, library in libraries.items():
                for name, address in library.items():
                    if index > max_libraries:
                        raise ContractVerificationError(
                            f"Can only include up to {max_libraries} libraries."
                        )

                    data[f"libraryname{index}"] = name
                    data[f"libraryaddress{index}"] = address
                    index += 1

        return data

    def _wait_for_verification(self, guid: str):
        explorer = self.provider.network.explorer
        if not explorer:
            raise ContractVerificationError(
                f"Etherscan plugin missing for network {self.provider.network.name}"
            )

        guid_did_exist = False
        fail_key = "Fail - "
        pass_key = "Pass - "

        for iteration in range(100):
            try:
                verification_update = self._contract_client.check_verify_status(guid)
                guid_did_exist = True
            except EtherscanResponseError as err:
                if "Resource not found" in str(err) and guid_did_exist:
                    # Sometimes, the GUID resource is gone before receiving a passing verification
                    verification_update = f"{pass_key}Complete"

                elif "source code already verified" in str(err):
                    # Consider this a pass.
                    verification_update = "Already Verified"

                else:
                    raise  # Original error

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


def extract_constructor_arguments(deployment_bytecode: str, runtime_bytecode: str) -> str:
    # Ensure the bytecodes are stripped of the "0x" prefix
    deployment_bytecode = (
        deployment_bytecode[2:] if deployment_bytecode.startswith("0x") else deployment_bytecode
    )
    runtime_bytecode = (
        runtime_bytecode[2:] if runtime_bytecode.startswith("0x") else runtime_bytecode
    )

    if deployment_bytecode.endswith(runtime_bytecode):
        # If the runtime bytecode is at the end of the deployment bytecode,
        # there are no constructor arguments
        return ""

    # Find the start of the runtime bytecode within the deployment bytecode
    start_index = deployment_bytecode.find(runtime_bytecode)

    # If the runtime bytecode is not found within the deployment bytecode,
    # return an error message
    if start_index == -1:
        raise ContractVerificationError("Runtime bytecode not found within deployment bytecode")

    # Cut the deployment bytecode at the start of the runtime bytecode
    # The remaining part is the constructor arguments
    constructor_args_start_index = start_index + len(runtime_bytecode)
    constructor_arguments = deployment_bytecode[constructor_args_start_index:]

    return constructor_arguments
