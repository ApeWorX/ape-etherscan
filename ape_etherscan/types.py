import json
import re
from dataclasses import dataclass
from typing import Union

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
    abi: list = Field([], alias="ABI")
    name: str = Field("unknown", alias="ContractName")
    source_code: str = Field("", alias="SourceCode")
    compiler_version: str = Field("", alias="CompilerVersion")
    optimization_used: bool = Field(True, alias="OptimizationUsed")
    optimization_runs: int = Field(200, alias="Runs")
    evm_version: str = Field("Default", alias="EVMVersion")
    library: str = Field("", alias="Library")
    license_type: str = Field("", alias="LicenseType")
    proxy: bool = Field(False, alias="Proxy")
    implementation: str = Field("", alias="Implementation")
    swarm_source: str = Field("", alias="SwarmSource")

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


@dataclass
class ContractCreationResponse:
    contractAddress: str
    contractCreator: str
    txHash: str


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
