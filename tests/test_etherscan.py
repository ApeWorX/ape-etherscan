import json
from pathlib import Path

import pytest
from ape import networks
from ape.api.explorers import ExplorerAPI
from requests import Response

from ape_etherscan import NETWORKS

ADDRESS = "https://etherscan.io/address/0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"
MOCK_RESPONSES_PATH = Path(__file__).parent / "mock_responses"

# A map of each mock response to its contract name for testing `get_contract_type()`.
EXPECTED_CONTRACT_NAME_MAP = {
    "get_contract_response.json": "BoredApeYachtClub",
    "get_proxy_contract_response.json": "Vyper_contract"
}


@pytest.fixture(params=([f.name for f in MOCK_RESPONSES_PATH.iterdir()]))
def etherscan_abi_response(request, mocker):
    response = mocker.MagicMock(spec=Response)
    test_data_path = MOCK_RESPONSES_PATH / request.param
    expected_name_map = {
        "get_contract_response.json": "BoredApeYachtClub",
        "get_proxy_contract_response.json": "Vyper_contract"
    }

    with open(test_data_path) as response_data_file:
        mock_response_dict = json.load(response_data_file)
        response.json.return_value = mock_response_dict
        response.text.return_value = json.dumps(mock_response_dict)
        response.file_name = request.param
        yield response


def get_explorer(network_name: str = "development") -> ExplorerAPI:
    return getattr(networks.ethereum, network_name).explorer


def setup_mock_get(mocker, etherscan_abi_response, expected_params):
    get_patch = mocker.patch("ape_etherscan.client.requests")

    def get_mock_response(method, base_uri, params=None, *args, **kwargs):
        # Request will fail if made with incorrect parameters.
        assert method == "GET"
        assert base_uri == "https://api.etherscan.io/api"
        assert params == expected_params
        return etherscan_abi_response

    get_patch.request.side_effect = get_mock_response
    return get_patch


@pytest.mark.parametrize(
    "network,expected_prefix,address",
    [(NETWORKS[0], "etherscan.io", ADDRESS), (NETWORKS[1], "ropsten.etherscan.io", ADDRESS)],
)
def test_get_address_url(network, expected_prefix, address):
    expected = f"https://{expected_prefix}/address/{ADDRESS}"
    explorer = get_explorer(network)
    actual = explorer.get_address_url(address)  # type: ignore
    assert actual == expected


@pytest.mark.parametrize(
    "network,expected_prefix,tx_hash",
    [
        (NETWORKS[0], "etherscan.io", TRANSACTION),
        (NETWORKS[1], "ropsten.etherscan.io", TRANSACTION),
    ],
)
def test_get_transaction_url(network, expected_prefix, tx_hash):
    expected = f"https://{expected_prefix}/tx/{tx_hash}"
    explorer = get_explorer(network)
    actual = explorer.get_transaction_url(tx_hash)
    assert actual == expected


def test_get_contract_type(mocker, etherscan_abi_response):
    expected_params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": ADDRESS,
    }
    setup_mock_get(mocker, etherscan_abi_response, expected_params)

    explorer = get_explorer("mainnet")
    actual = explorer.get_contract_type(ADDRESS)  # type: ignore

    actual = actual.contractName
    expected = EXPECTED_CONTRACT_NAME_MAP[etherscan_abi_response.file_name]
    assert actual == expected
