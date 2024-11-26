import os
from typing import TYPE_CHECKING, Any, Union

from ape.exceptions import ApeException
from requests import Response

from ape_etherscan.utils import ETHERSCAN_API_KEY_NAME

if TYPE_CHECKING:
    from ape_etherscan.types import EtherscanResponse, ResponseValue


class ApeEtherscanException(ApeException):
    """
    A base exception in the ape-etherscan plugin.
    """


class UnsupportedEcosystemError(ApeEtherscanException):
    """
    Raised when there is no Etherscan buildout for ecosystem.
    """

    def __init__(self, ecosystem: str):
        super().__init__(f"Unsupported Ecosystem: {ecosystem}")


class UnsupportedNetworkError(ApeEtherscanException):
    """
    Raised when there is no Etherscan buildout for ecosystem.
    """

    def __init__(self, ecosystem_name: str, network_name: str):
        super().__init__(f"Unsupported Network for Ecosystem '{ecosystem_name}': {network_name}")


class EtherscanResponseError(ApeEtherscanException):
    """
    Raised when the response is not correct.
    """

    def __init__(self, response: Union[Response, "EtherscanResponse"], message: str):
        if not isinstance(response, Response):
            response = response.response

        self.response = response
        super().__init__(f"Response indicated failure: {message}")


class ContractNotVerifiedError(EtherscanResponseError):
    """
    Raised when a contract is not verified on Etherscan.
    """

    def __init__(self, response: Union[Response, "EtherscanResponse"], address: str):
        super().__init__(response, f"Contract '{address}' not verified.")


class UnhandledResultError(EtherscanResponseError):
    """
    Raised in specific client module where the result from Etherscan
    has an unhandled form.
    """

    def __init__(self, response: Union[Response, "EtherscanResponse"], value: "ResponseValue"):
        message = f"Unhandled response format: {value}"
        super().__init__(response, message)


class EtherscanTooManyRequestsError(EtherscanResponseError):
    """
    Raised after being rate-limited by Etherscan.
    """

    def __init__(self, response: Union[Response, "EtherscanResponse"], ecosystem: str):
        message = "Etherscan API server rate limit exceeded."
        if not os.environ.get(ETHERSCAN_API_KEY_NAME):
            message = f"{message}. Try setting {ETHERSCAN_API_KEY_NAME}'."

        super().__init__(response, message)


class ContractVerificationError(ApeEtherscanException):
    """
    An error that occurs when unable to verify or publish a contract.
    """


class IncompatibleCompilerSettingsError(ApeEtherscanException):
    """
    An error that occurs when unable to verify or publish a contract because viaIR (or some other)
    is enabled and the compiler settings are not compatible with the API.
    """

    def __init__(self, compiler: str, setting: str, value: Any):
        super().__init__(f"Incompatible {compiler} setting: '{setting}={value}'.")


def get_request_error(response: Response, ecosystem: str) -> EtherscanResponseError:
    response_data = response.json()
    if "result" in response_data and response_data["result"]:
        message = response_data["result"]
    elif "message" in response_data:
        message = response_data["message"]
    else:
        message = response.text

    if "max rate limit reached" in response.text.lower():
        return EtherscanTooManyRequestsError(response, ecosystem)

    return EtherscanResponseError(response, message)
