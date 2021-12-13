import json

import pytest
from requests import Response


@pytest.fixture
def etherscan_abi_response(mocker):
    response = mocker.MagicMock(spec=Response)
    f = open("api.json")
    response.json.return_value = json.load(f)
    f.close()
    return response


def test_get_contract_type(mocker):
    get_patch = mocker.patch("ape_etherscan.explorer.requests")
    get_patch.get.return_value = etherscan_abi_response
