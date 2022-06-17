import json
from pathlib import Path

import pytest
from ape import networks
from ape.api.explorers import ExplorerAPI
from requests import Response

from ape_etherscan import NETWORKS

TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"
MOCK_RESPONSES_PATH = Path(__file__).parent / "mock_responses"

# A map of each mock response to its contract name for testing `get_contract_type()`.
EXPECTED_CONTRACT_NAME_MAP = {
    "get_contract_response.json": "BoredApeYachtClub",
    "get_proxy_contract_response.json": "MIM-UST-f",
    "get_vyper_contract_response.json": "yvDAI",
}
CONTRACT_ADDRESS_MAP = {
    "get_contract_response.json": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
    "get_proxy_contract_response.json": "0x55A8a39bc9694714E2874c1ce77aa1E599461E18",
    "get_vyper_contract_response.json": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
}


@pytest.fixture
def address():
    return [k for k in CONTRACT_ADDRESS_MAP.keys()][0]


@pytest.fixture(
    params=(
        "get_contract_response.json",
        "get_proxy_contract_response.json",
        "get_vyper_contract_response.json",
    )
)
def mock_abi_response(request, mocker):
    test_data_path = MOCK_RESPONSES_PATH / request.param

    with open(test_data_path) as response_data_file:
        yield _mock_response(mocker, request.param, response_data_file)


@pytest.fixture
def mock_vyper_response(mocker):
    response_name = "get_vyper_contract_response.json"
    test_data_path = MOCK_RESPONSES_PATH / response_name

    with open(test_data_path) as response_data_file:
        yield _mock_response(mocker, response_name, response_data_file)


def _mock_response(mocker, file_name: str, response_data_file):
    response = mocker.MagicMock(spec=Response)
    mock_response_dict = json.load(response_data_file)
    response.json.return_value = mock_response_dict
    response.text.return_value = json.dumps(mock_response_dict)
    response.file_name = file_name
    return response


@pytest.fixture
def mock_account_transactions_response(mocker):
    file_name = "get_account_transactions.json"
    test_data_path = MOCK_RESPONSES_PATH / file_name
    with open(test_data_path) as response_data_file:
        return _mock_response(mocker, file_name, response_data_file)


@pytest.fixture
def infura_connection():
    with networks.parse_network_choice("ethereum:mainnet:infura") as provider:
        yield provider


def get_explorer(
    ecosystem_name: str = "ethereum",
    network_name: str = "development",
) -> ExplorerAPI:
    ecosystem = networks.get_ecosystem(ecosystem_name)
    explorer = ecosystem.get_network(network_name).explorer
    assert explorer is not None
    return explorer


def setup_mock_get(mocker, etherscan_abi_response, expected_params):
    get_patch = mocker.patch("ape_etherscan.client.requests")

    def get_mock_response(method, base_uri, params=None, *args, **kwargs):
        # Request will fail if made with incorrect parameters.
        assert method == "GET"
        assert base_uri == "https://api.etherscan.io/api"

        # Ignore API key in tests for now
        if params and "apikey" in params:
            del params["apikey"]

        assert params == expected_params, "Was not called with the expected request parameters."
        return etherscan_abi_response

    get_patch.request.side_effect = get_mock_response
    return get_patch


@pytest.mark.parametrize(
    "ecosystem,network,expected_prefix",
    [
        ("ethereum", NETWORKS["ethereum"][0], "etherscan.io"),
        ("ethereum", f"{NETWORKS['ethereum'][0]}-fork", "etherscan.io"),
        ("ethereum", NETWORKS["ethereum"][1], "ropsten.etherscan.io"),
        ("fantom", NETWORKS["fantom"][0], "ftmscan.com"),
        ("fantom", NETWORKS["fantom"][1], "testnet.ftmscan.com"),
    ],
)
def test_get_address_url(ecosystem, network, expected_prefix, address):
    expected = f"https://{expected_prefix}/address/{address}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_address_url(address)  # type: ignore
    assert actual == expected


@pytest.mark.parametrize(
    "ecosystem,network,expected_prefix",
    [
        ("ethereum", NETWORKS["ethereum"][0], "etherscan.io"),
        ("ethereum", f"{NETWORKS['ethereum'][0]}-fork", "etherscan.io"),
        ("ethereum", NETWORKS["ethereum"][1], "ropsten.etherscan.io"),
        ("fantom", NETWORKS["fantom"][0], "ftmscan.com"),
        ("fantom", NETWORKS["fantom"][1], "testnet.ftmscan.com"),
    ],
)
def test_get_transaction_url(ecosystem, network, expected_prefix):
    expected = f"https://{expected_prefix}/tx/{TRANSACTION}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_transaction_url(TRANSACTION)
    assert actual == expected


def etherscan_abi_response(request, mocker):
    response = mocker.MagicMock(spec=Response)
    test_data_path = MOCK_RESPONSES_PATH / request.param

    with open(test_data_path) as response_data_file:
        mock_response_dict = json.load(response_data_file)
        response.json.return_value = mock_response_dict
        response.text.return_value = json.dumps(mock_response_dict)
        response.file_name = request.param
        yield response


@pytest.mark.parametrize("network", ("mainnet", "mainnet-fork"))
def test_get_contract_type(mocker, mock_abi_response, network, infura_connection):
    expected_address = CONTRACT_ADDRESS_MAP[mock_abi_response.file_name]
    expected_params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": expected_address,
    }
    setup_mock_get(mocker, mock_abi_response, expected_params)

    explorer = get_explorer("ethereum", network)
    actual = explorer.get_contract_type(expected_address)  # type: ignore
    assert actual is not None

    actual = actual.name
    expected = EXPECTED_CONTRACT_NAME_MAP[mock_abi_response.file_name]
    assert actual == expected


def test_get_account_transactions(mocker, mock_account_transactions_response, address):
    expected_params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "endblock": None,
        "startblock": None,
        "offset": 100,
        "page": 1,
        "sort": "asc",
    }
    setup_mock_get(mocker, mock_account_transactions_response, expected_params)

    explorer = get_explorer("ethereum", "mainnet")
    actual = [r for r in explorer.get_account_transactions(address)]  # type: ignore

    # From `get_account_transactions.json` response.
    assert actual[0].txn_hash == "GENESIS_ddbd2b932c763ba5b1b7ae3b362eac3e8d40121a"
