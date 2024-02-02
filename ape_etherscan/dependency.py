from ape.api.projects import DependencyAPI
from ape.exceptions import ProjectError
from ape.types import AddressType
from ethpm_types import PackageManifest
from hexbytes import HexBytes
from pydantic import AnyUrl, HttpUrl, field_validator

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
            manifest = self.explorer.get_manifest(self.address)
        finally:
            if ctx:
                ctx.__exit__(None)

        if not manifest:
            raise ProjectError(f"Etherscan dependency '{self.name}' not verified.")

        return manifest
