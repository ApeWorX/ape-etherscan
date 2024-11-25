import json
import re
from dataclasses import dataclass
from typing import Optional, Union

from ape.utils import cached_property
from ethpm_types import BaseModel
from pydantic import Field, field_validator

from ape_etherscan.exceptions import EtherscanResponseError, get_request_error


@dataclass
class EtherscanInstance:
    """Used to pass around Etherscan instance information"""

    ecosystem_name: str
    network_name: str  # normalized (e.g. no -fork)
    uri: str
    api_uri: str


class SourceCodeResponse(BaseModel):
    abi: list = Field(default=[], alias="ABI")
    name: str = Field(default="unknown", alias="ContractName")
    source_code: str = Field(default="", alias="SourceCode")
    compiler_version: str = Field(default="", alias="CompilerVersion")
    optimization_used: bool = Field(default=True, alias="OptimizationUsed")
    optimization_runs: int = Field(default=200, alias="Runs")
    evm_version: str = Field(default="Default", alias="EVMVersion")
    library: str = Field(default="", alias="Library")
    license_type: str = Field(default="", alias="LicenseType")
    proxy: bool = Field(default=False, alias="Proxy")
    implementation: str = Field(default="", alias="Implementation")
    swarm_source: str = Field(default="", alias="SwarmSource")

    @field_validator("optimization_used", "proxy", mode="before")
    @classmethod
    def validate_bools(cls, value):
        return bool(int(value))

    @field_validator("abi", mode="before")
    @classmethod
    def validate_abi(cls, value):
        return json.loads(value)

    @field_validator("source_code", mode="before")
    @classmethod
    def validate_source_code(cls, value):
        if value.startswith("{"):
            # NOTE: Have to deal with very poor JSON
            # response from Etherscan.
            fixed = re.sub(r"\r\n\s*", "", value)
            fixed = re.sub(r"\r\n\s*", "", fixed)
            if fixed.startswith("{{"):
                fixed = fixed[1:-1]

            return fixed

        return value


class ContractCreationResponse(BaseModel):
    contractAddress: str
    contractCreator: str
    txHash: str

    # Only appears on some networks for some reason.
    blockNumber: Optional[int] = None
    timestamp: Optional[int] = None
    contractFactory: Optional[str] = None
    creationBytecode: Optional[str] = None


ResponseValue = Union[list, dict, str]


class EtherscanResponse:
    def __init__(self, response, ecosystem: str, raise_on_exceptions: bool):
        self.response = response
        self.ecosystem = ecosystem
        self.raise_on_exceptions = raise_on_exceptions

    @cached_property
    def value(self) -> ResponseValue:
        try:
            response_data = self.response.json()
        except json.JSONDecodeError as err:
            # Etherscan may respond with HTML content.
            raise EtherscanResponseError(self.response, "Resource not found") from err

        message = response_data.get("message", "")
        is_error = response_data.get("isError", 0) or message == "NOTOK"
        if is_error is True and self.raise_on_exceptions:
            raise get_request_error(self.response, self.ecosystem)

        result = response_data.get("result", message)
        if not result or not isinstance(result, str):
            return result

        # Some errors come back as strings
        if result.startswith("Error!"):
            err_msg = result.split("Error!")[-1].strip()
            if self.raise_on_exceptions:
                raise EtherscanResponseError(self.response, err_msg)

            return err_msg

        try:
            # Sometimes, the response is a stringified JSON object or list
            return json.loads(result)
        except json.JSONDecodeError:
            return result
