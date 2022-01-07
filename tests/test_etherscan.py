import json
from pathlib import Path

import pytest
from ape import convert, networks
from ape.api.explorers import ExplorerAPI
from ape.types import AddressType
from requests import Response

from ape_etherscan import NETWORKS

ADDRESS = "https://etherscan.io/address/0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"


@pytest.fixture
def etherscan_abi_response(mocker):
    response = mocker.MagicMock(spec=Response)
    test_data_path = Path(__file__).parent / "get_contract_response.json"
    with open(test_data_path) as response_data_file:
        response.json.return_value = json.load(response_data_file)
        yield response


def get_explorer(network_name: str) -> ExplorerAPI:
    return getattr(networks.ethereum, network_name).explorer


def setup_mock_get(mocker, etherscan_abi_response, expected_params):
    get_patch = mocker.patch("ape_etherscan.client.requests")

    def get(base_uri, params=None, *args, **kwargs):
        # Request will fail if made with incorrect parameters.
        assert base_uri == "https://api.etherscan.io/api"
        assert params == expected_params
        return etherscan_abi_response

    get_patch.get.side_effect = get
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
    [(NETWORKS[0], "etherscan.io", TRANSACTION), (NETWORKS[1], "ropsten.etherscan.io", TRANSACTION)],
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

    # Name comes from the 'get_contract_response.json' file
    expected = "BoredApeYachtClub"
    assert actual.contractName == expected
