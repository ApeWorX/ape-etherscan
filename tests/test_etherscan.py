import json
from pathlib import Path

import pytest
from ape import networks
from requests import Response

ADDRESS = "0xab5801a7d398351b8be11c439e05c5b3259aec9b"
TRANSACITON = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"


@pytest.fixture
def explorer():
    return networks.ethereum.mainnet.explorer


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


def test_get_address_url(explorer):
    expected = f"https://etherscan.io/address/{ADDRESS}"
    actual = explorer.get_address_url(ADDRESS)
    assert actual == expected


def test_get_transaction_url(explorer):
    expected = f"https://etherscan.io/tx/{TRANSACITON}"
    actual = explorer.get_transaction_url(TRANSACITON)
    assert actual == expected


def test_get_contract_type(mocker, etherscan_abi_response, exlporer):
    expected_params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": ADDRESS,
    }
    setup_mock_get(mocker, etherscan_abi_response, expected_params)

    actual = explorer.get_contract_type(ADDRESS)

    # Name comes from the 'get_contract_response.json' file
    expected = "BoredApeYachtClub"
    assert actual.contractName == expected
