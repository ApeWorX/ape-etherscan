import json

import pytest
from requests import Response


@pytest.fixture
def etherscan_abi_response(mocker):
    response = mocker.MagicMock(spec=Response)
    f = open("api.json")
    response.json.return_value = json.load(f)
    return response


def test(mocker):
    get_patch = mocker.patch("ape_etherscan.requests")
    get_patch.get.return_value = etherscan_abi_response
