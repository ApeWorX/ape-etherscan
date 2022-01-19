import os

from ape.exceptions import ApeException
from requests import Response

from ape_etherscan.utils import API_KEY_ENV_VAR_NAME


class ApeEtherscanException(ApeException):
    """
    A base exception in the ape-etherscan plugin.
    """


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

    def __init__(self, response: Response):
        message = "Etherscan API server rate limit exceeded."
        if not os.environ.get(API_KEY_ENV_VAR_NAME):
            message = f"{message}. Try setting environment variable '{API_KEY_ENV_VAR_NAME}'."

        super().__init__(response, message)


def get_request_error(response: Response) -> EtherscanResponseError:
    response_data = response.json()
    if "result" in response_data and response_data["result"]:
        message = response_data["result"]
    elif "message" in response_data:
        message = response_data["message"]
    else:
        message = response.text

    if "max rate limit reached" in response.text.lower():
        return EtherscanTooManyRequestsError(response)

    return EtherscanResponseError(response, message)
