import json
from dataclasses import dataclass
from typing import Dict, List, Union

from ape.utils import cached_property

from ape_etherscan.exceptions import EtherscanResponseError, get_request_error


@dataclass
class SourceCodeResponse:
    abi: str = ""
    name: str = "unknown"


@dataclass
class ContractCreationResponse:
    contractAddress: str
    contractCreator: str
    txHash: str


ResponseValue = Union[List, Dict, str]


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
        if is_error and self.raise_on_exceptions:
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
