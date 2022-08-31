import json
import os
from pathlib import Path
from tempfile import mkdtemp

import ape
import pytest
from ape.api import ExplorerAPI
from requests import Response

from ape_etherscan.client import _APIClient

ape.config.DATA_FOLDER = Path(mkdtemp()).resolve()
ape.config.PROJECT_FOLDER = Path(mkdtemp()).resolve()

MOCK_RESPONSES_PATH = Path(__file__).parent / "mock_responses"
CONTRACT_ADDRESS = "0xFe80e7afB7041c1592a2A5d8f617518c1591Aad4"
CONTRACT_ADDRESS_MAP = {
    "get_contract_response": CONTRACT_ADDRESS,
    "get_proxy_contract_response": "0x55A8a39bc9694714E2874c1ce77aa1E599461E18",
    "get_vyper_contract_response": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
}
EXPECTED_ACCOUNT_TXNS_PARAMS = {
    "module": "account",
    "action": "txlist",
    "address": CONTRACT_ADDRESS,
    "endblock": None,
    "startblock": None,
    "offset": 100,
    "page": 1,
    "sort": "asc",
}
SOURCE_CODE = """
pragma solidity =0.8.16;
contract foo {
}
"""


@pytest.fixture(autouse=True)
def connection():
    with ape.networks.parse_network_choice("ethereum:mainnet:infura") as provider:
        yield provider


@pytest.fixture(autouse=True)
def with_source_file():
    contracts_dir = ape.config.PROJECT_FOLDER / "contracts"
    ape.config.contracts_folder = contracts_dir
    contracts_dir.mkdir(exist_ok=True)
    source_file = contracts_dir / "foo.sol"
    source_file.touch()
    source_file.write_text(SOURCE_CODE)


@pytest.fixture
def address():
    return CONTRACT_ADDRESS


@pytest.fixture
def no_api_key():
    key = os.environ.pop("ETHERSCAN_API_KEY", None)
    yield
    if key:
        os.environ["ETHERSCAN_API_KEY"] = key


@pytest.fixture
def explorer(get_explorer):
    return get_explorer("ethereum", "mainnet")


@pytest.fixture
def get_explorer():
    def fn(
        ecosystem_name: str = "ethereum",
        network_name: str = "development",
    ) -> ExplorerAPI:
        ecosystem = ape.networks.get_ecosystem(ecosystem_name)
        explorer = ecosystem.get_network(network_name).explorer
        assert explorer is not None
        return explorer

    return fn


@pytest.fixture
def mock_backend(mocker):
    session = mocker.MagicMock()
    backend = MockEtherscanBackend(mocker, session)
    _APIClient.session = session
    return backend


class MockEtherscanBackend:
    def __init__(self, mocker, session):
        self._mocker = mocker
        self._session = session
        self._expected_base_uri = "https://api.etherscan.io/api"  # Default
        self._handlers = {"get": {}, "post": {}}

    def set_ecosystem(self, ecosystem):
        expected_uri_map = {
            "ethereum": "https://api.etherscan.io/api",
            "fantom": "https://api.ftmscan.com/api",
            "optimism": "https://api-optimistic.etherscan.io/api",
        }
        self._expected_base_uri = expected_uri_map[ecosystem]

    def add_handler(self, method, module, expected_params, return_value=None, side_effect=None):
        def handler(self, method, base_uri, params=None, *args, **kwargs):
            assert params == expected_params

            if return_value:
                return return_value

            elif side_effect:
                return side_effect()

        self._handlers[method.lower()][module] = handler
        self._session.request.side_effect = self.handle_request

    def handle_request(self, method, base_uri, headers=None, params=None, data=None):
        if params and "apikey" in params:
            del params["apikey"]
        if data and "apiKey" in data:
            del data["apiKey"]

        assert base_uri == self._expected_base_uri

        module = params.get("module") or data.get("module")
        handler = self._handlers[method.lower()][module]
        options = dict(headers=headers, params=params, json=json, data=data)
        return handler(self, method, base_uri, **options)

    def setup_mock_get_contract_type_response(self, file_name: str):
        expected_address = CONTRACT_ADDRESS_MAP[file_name]
        expected_params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": expected_address,
        }

        test_data_path = MOCK_RESPONSES_PATH / f"{file_name}.json"
        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(file_name, response_data_file)

        self.add_handler("GET", "contract", expected_params, return_value=response)
        response.expected_address = expected_address
        return response

    def setup_mock_account_transactions_response(self):
        file_name = "get_account_transactions.json"
        test_data_path = MOCK_RESPONSES_PATH / file_name
        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(file_name, response_data_file)
            self.add_handler("GET", "account", EXPECTED_ACCOUNT_TXNS_PARAMS, return_value=response)
            self.set_ecosystem("ethereum")
            return response

    def get_mock_response(self, file_name: str, response_data_file):
        response = self._mocker.MagicMock(spec=Response)
        mock_response_dict = json.load(response_data_file)
        response.json.return_value = mock_response_dict
        response.text = json.dumps(mock_response_dict)
        response.file_name = file_name
        return response
