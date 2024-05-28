from pathlib import Path

from ape.api.projects import DependencyAPI
from ape.exceptions import ProjectError
from ape.types import AddressType
from ethpm_types import PackageManifest
from hexbytes import HexBytes
from pydantic import field_validator

from .explorer import Etherscan


class EtherscanDependency(DependencyAPI):
    etherscan: str
    ecosystem: str = "ethereum"
    network: str = "mainnet"

    @field_validator("etherscan", mode="before")
    @classmethod
    def handle_int(cls, value):
        return value if isinstance(value, str) else HexBytes(value).hex()

    @property
    def version_id(self) -> str:
        return f"{self.ecosystem}_{self.network}"

    @property
    def address(self) -> AddressType:
        return self.network_manager.ethereum.decode_address(self.etherscan)

    @property
    def package_id(self) -> str:
        return self.address

    @property
    def uri(self) -> str:
        return f"{self.explorer.get_address_url(self.address)}#code"

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

    def fetch(self, destination: Path):
        manifest = self._get_manifest()
        manifest.unpack_sources(destination)

    def _get_manifest(self) -> PackageManifest:
        ecosystem = self.network_manager.get_ecosystem(self.ecosystem)
        network = ecosystem.get_network(self.network)

        ctx = None
        if self.network_manager.active_provider is None:
            ctx = network.use_default_provider()
            ctx.__enter__()

        try:
            manifest = self.explorer.get_manifest(self.address)
        finally:
            if ctx:
                ctx.__exit__(None)

        if not manifest:
            raise ProjectError(f"Etherscan dependency '{self.name}' not verified.")

        return manifest
