import tempfile
from pathlib import Path

import yaml
from ape.api.projects import DependencyAPI
from ape.types import AddressType
from ethpm_types import PackageManifest
from pydantic import AnyUrl, HttpUrl

from .explorer import Etherscan


class EtherscanDependency(DependencyAPI):
    etherscan: str
    ecosystem: str = "ethereum"
    network: str = "mainnet"

    @property
    def version_id(self) -> str:
        return "etherscan"  # Only 1 version

    @property
    def address(self) -> AddressType:
        return self.network_manager.ethereum.decode_address(self.etherscan)

    @property
    def uri(self) -> AnyUrl:
        return HttpUrl(f"{self.explorer.get_address_url(self.address)}#code")

    @property
    def explorer(self) -> Etherscan:
        if self.network_manager.active_provider:
            explorer = self.provider.network.explorer
            if isinstance(explorer, Etherscan):
                # Could be using a different network.
                return explorer
            else:
                return self.network_manager.ethereum.mainnet.explorer

        # Assume Ethereum
        return self.network_manager.ethereum.mainnet.explorer

    def extract_manifest(self, use_cache: bool = True) -> PackageManifest:
        ecosystem = self.network_manager.get_ecosystem(self.ecosystem)
        network = ecosystem.get_network(self.network)

        ctx = None
        if self.network_manager.active_provider is None:
            ctx = network.use_default_provider()
            ctx.__enter__()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                project_path = Path(temp_dir).resolve()
                contracts_folder = project_path / "contracts"
                contracts_folder.mkdir()

                response = self.explorer._get_source_code(self.address)

                # Ensure compiler settings match.
                if response.evm_version and response.evm_version != "Default":
                    data = {"solidity": {"evm_version": response.evm_version}}
                    config_file = project_path / "ape-config.yaml"
                    with open(config_file, "w") as file:
                        yaml.safe_dump(data, file)

                new_path = contracts_folder / f"{response.name}.sol"
                new_path.write_text(response.source_code)
                return self._extract_local_manifest(project_path, use_cache=use_cache)

        finally:
            if ctx:
                ctx.__exit__(None)
