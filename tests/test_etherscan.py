import json
from pathlib import Path

import pytest
from ape import networks
from requests import Response

CONTRACT_ADDRESS = "0x112233966B444443fe4b875411e2877777777AaA"


@pytest.fixture
def etherscan_abi_response(mocker):
    response = mocker.MagicMock(spec=Response)
    test_data_path = Path(__file__).parent / "get_contract_response.json"
    with open(test_data_path) as response_data_file:
        response.json.return_value = json.load(response_data_file)
        yield response


def setup_mock_get(mocker, etherscan_abi_response, expected_params):
    get_patch = mocker.patch("ape_etherscan.client.requests")

    def get(base_uri, params=None, *args, **kwargs):
        # Request will fail if made with incorrect parameters.
        assert base_uri == "https://api.etherscan.io/api"
        assert params == expected_params
        return etherscan_abi_response

    get_patch.get.side_effect = get
    return get_patch


def test_get_contract_type(mocker, etherscan_abi_response):
    expected_params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": CONTRACT_ADDRESS,
    }
    setup_mock_get(mocker, etherscan_abi_response, expected_params)

    actual = networks.ethereum.mainnet.explorer.get_contract_type(CONTRACT_ADDRESS)

    # Name comes from the 'get_contract_response.json' file
    expected = "BoredApeYachtClub"
    assert actual.contractName == expected
