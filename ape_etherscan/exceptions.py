import os

from ape.exceptions import ApeException
from requests import Response

from ape_etherscan.utils import API_KEY_ENV_KEY_MAP


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


class EtherscanResponseError(ApeEtherscanException):
    """
    Raised when the response is not correct.
    """

    def __init__(self, response: Response, message: str):
        self.response = response
        super().__init__(f"Response indicated failure: {message}")


class EtherscanTooManyRequestsError(EtherscanResponseError):
    """
    Raised after being rate-limited by Etherscan.
    """

    def __init__(self, response: Response, ecosystem: str):
        message = "Etherscan API server rate limit exceeded."
        api_key_name = API_KEY_ENV_KEY_MAP[ecosystem]
        if not os.environ.get(api_key_name):
            message = f"{message}. Try setting {api_key_name}'."

        super().__init__(response, message)


class ContractVerificationError(ApeEtherscanException):
    """
    An error that occurs when unable to verify or publish a contract.
    """


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
