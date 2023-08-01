import json
import os
from io import StringIO
from json import JSONDecodeError
from pathlib import Path
from tempfile import mkdtemp
from typing import IO, Any, Callable, Dict, Optional, Union
from unittest.mock import MagicMock

import _io  # type: ignore
import ape
import pytest
from ape.api import ExplorerAPI
from ape.exceptions import NetworkError
from ape.logging import logger
from ape.types import AddressType
from ape.utils import cached_property
from ape_solidity._utils import OUTPUT_SELECTION
from requests import Response

from ape_etherscan import Etherscan
from ape_etherscan.client import _APIClient
from ape_etherscan.types import EtherscanResponse

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
    "address": "0x1e59ce931B4CFea3fe4B875411e280e173cB7A9C",
    "endblock": None,
    "startblock": None,
    "offset": 100,
    "page": 1,
    "sort": "asc",
}
FOO_SOURCE_CODE = """
// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.20;

import "@bar/bar.sol";

library MyLib {
    function insert(uint value) public returns (bool) {
        return true;
    }
}

contract foo {
    function register(uint value) public {
        require(MyLib.insert(value));
    }
}

contract fooWithConstructor {
    uint public value;
    constructor(uint _value) {
        value = _value;
    }
}
"""
BAR_SOURCE_CODE = r"""
// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.20;

contract bar {
}
"""
APE_CONFIG_FILE = r"""
dependencies:
  - name: bar
    local: ./bar

solidity:
  import_remapping:
    - "@bar=bar"
"""
STANDARD_INPUT_JSON = {
    "language": "Solidity",
    "sources": {
        "foo.sol": {"content": FOO_SOURCE_CODE},
        ".cache/bar/local/bar.sol": {"content": BAR_SOURCE_CODE},
    },
    "settings": {
        "optimizer": {"enabled": True, "runs": 200},
        "outputSelection": {
            "subcontracts/foo.sol": {"*": OUTPUT_SELECTION, "": ["ast"]},
            ".cache/bar/local/bar.sol": {"*": OUTPUT_SELECTION, "": ["ast"]},
        },
        "remappings": ["@bar=.cache/bar/local"],
    },
    "libraryname1": "MyLib",
    "libraryaddress1": "0x274b028b03A250cA03644E6c578D81f019eE1323",
}


@pytest.fixture(autouse=True)
def connection(explorer):
    with ape.networks.ethereum.mainnet.use_provider("infura") as provider:
        yield provider


def make_source(base_dir: Path, name: str, content: str):
    source_file = base_dir / f"{name}.sol"
    source_file.touch()
    source_file.write_text(content)


@pytest.fixture(scope="session", autouse=True)
def project():
    base_dir = ape.config.PROJECT_FOLDER
    contracts_dir = base_dir / "contracts"
    dependency_contracts_dir = base_dir / "bar" / "contracts"
    sub_contracts_dir = contracts_dir / "subcontracts"
    sub_contracts_dir.mkdir(exist_ok=True, parents=True)
    dependency_contracts_dir.mkdir(exist_ok=True, parents=True)

    make_source(sub_contracts_dir, "foo", FOO_SOURCE_CODE)
    make_source(dependency_contracts_dir, "bar", BAR_SOURCE_CODE)

    config_file = base_dir / "ape-config.yaml"
    config_file.unlink(missing_ok=True)
    config_file.write_text(APE_CONFIG_FILE)

    with ape.config.using_project(base_dir) as project:
        yield project


@pytest.fixture(scope="session")
def address():
    return CONTRACT_ADDRESS


@pytest.fixture(scope="session")
def account():
    return ape.accounts.test_accounts[0]


@pytest.fixture(scope="session")
def fake_connection():
    with ape.networks.ethereum.local.use_provider("test"):
        yield


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
def get_explorer(mocker):
    def fn(
        ecosystem_name: str = "ethereum",
        network_name: str = "development",
    ) -> ExplorerAPI:
        try:
            ecosystem = ape.networks.get_ecosystem(ecosystem_name)
        except NetworkError:
            # Use mock
            logger.warning(
                f"Ecosystem 'ape-{ecosystem_name}' not installed; resorting to a mock ecosystem."
            )
            ecosystem = mocker.MagicMock()
            ecosystem.name = ecosystem_name
            network = mocker.MagicMock()
            network.name = network_name
            network.ecosystem = ecosystem
            etherscan = ape.networks.get_ecosystem("ethereum").get_network("mainnet")
            explorer = Etherscan.construct(name=etherscan.name, network=network)
            network.explorer = explorer
            explorer.network = network
        else:
            network = ecosystem.get_network(network_name)
            explorer = network.explorer
            assert explorer is not None

        return explorer

    return fn


@pytest.fixture
def response(mocker):
    response = mocker.MagicMock(spec=Response)
    return EtherscanResponse(response, "ethereum", raise_on_exceptions=False)


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

    @cached_property
    def expected_uri_map(
        self,
    ) -> Dict[str, Dict[str, str]]:
        def get_url_f(testnet: bool = False, tld: str = "io"):
            f_str = f"https://api-{{}}.{{}}.{tld}/api" if testnet else f"https://api.{{}}.{tld}/api"
            return f_str.format

        url = get_url_f()
        testnet_url = get_url_f(testnet=True)
        com_url = get_url_f(tld="com")
        org_url = get_url_f(tld="org")
        com_testnet_url = get_url_f(testnet=True, tld="com")
        org_testnet_url = get_url_f(testnet=True, tld="org")

        return {
            "ethereum": {
                "mainnet": url("etherscan"),
                "goerli": testnet_url("goerli", "etherscan"),
                "sepolia": testnet_url("sepolia", "etherscan"),
            },
            "arbitrum": {
                "mainnet": url("arbiscan"),
                "goerli": testnet_url("goerli", "arbiscan"),
            },
            "fantom": {
                "opera": com_url("ftmscan"),
                "testnet": com_testnet_url("testnet", "ftmscan"),
            },
            "optimism": {
                "mainnet": testnet_url("optimistic", "etherscan"),
                "goerli": testnet_url("goerli-optimistic", "etherscan"),
            },
            "polygon": {
                "mainnet": com_url("polygonscan"),
                "mumbai": com_testnet_url("testnet", "polygonscan"),
            },
            "base": {
                "goerli": org_testnet_url("goerli", "basescan"),
                "mainnet": org_url("basescan"),
            },
            "polygon-zkevm": {
                "mainnet": com_testnet_url("zkevm", "polygonscan"),
                "goerli": com_testnet_url("testnet-zkevm", "polygonscan"),
            },
            "avalanche": {"mainnet": url("snowtrace"), "fuji": testnet_url("testnet", "snowtrace")},
            "bsc": {
                "mainnet": com_url("bscscan"),
                "testnet": com_testnet_url("testnet", "bscscan"),
            },
            "gnosis": {
                "mainnet": url("gnosisscan"),
            },
        }

    def set_network(self, ecosystem: str, network: str):
        self._expected_base_uri = self.expected_uri_map[ecosystem][network.replace("-fork", "")]

    def add_handler(
        self,
        method: str,
        module: str,
        expected_params: Dict,
        return_value: Optional[Any] = None,
        side_effect: Optional[Callable] = None,
    ):
        if isinstance(return_value, (str, dict)):
            return_value = self.get_mock_response(return_value)

        def handler(self, method, base_uri, params=None, data=None, headers=None):
            actual_params = params if method.lower() == "get" else data
            for key, val in expected_params.items():
                if key not in expected_params:
                    # Allow skipping certain assertions
                    continue

                # Handler StringIO objects
                if isinstance(val, StringIO):
                    assert isinstance(actual_params[key], StringIO)
                    text = actual_params[key].read()
                    if text:
                        try:
                            actual_json = json.loads(text)
                        except JSONDecodeError:
                            pytest.fail(f"Response text is not JSON: '{text}'.")
                            return
                    else:
                        # Empty.
                        actual_json = {}

                    val = val.read()
                    expected_json = json.loads(val) if val else {}
                    assert actual_json == expected_json

                else:
                    msg = f"expected={key}"
                    if params:
                        msg = f"{msg} module={params['module']} action={params['action']}"

                    assert actual_params[key] == val, msg

            if return_value:
                return return_value

            elif side_effect:
                result = side_effect()
                return result if isinstance(result, Response) else self.get_mock_response(result)

        self._handlers[method.lower()][module] = handler
        self._session.request.side_effect = self.handle_request

    def handle_request(self, method, base_uri, timeout, headers=None, params=None, data=None):
        if params and "apikey" in params:
            del params["apikey"]
        if data and "apiKey" in data:
            del data["apiKey"]

        assert base_uri == self._expected_base_uri

        if params:
            module = params.get("module")
        elif data:
            module = data.get("module")
        else:
            raise AssertionError("Expected either 'params' or 'data'.")

        handler = self._handlers[method.lower()][module]
        return handler(self, method, base_uri, headers=headers, params=params, data=data)

    def setup_mock_get_contract_type_response(self, file_name: str):
        response = self._get_contract_type_response(file_name)
        address = CONTRACT_ADDRESS_MAP[file_name]
        expected_params = self._expected_get_ct_params(address)
        self.add_handler("GET", "contract", expected_params, return_value=response)
        response.expected_address = address
        return response

    def setup_mock_get_contract_type_response_with_throttling(
        self, file_name: str, retries: int = 2
    ):
        response = self._get_contract_type_response(file_name)
        address = CONTRACT_ADDRESS_MAP[file_name]
        expected_params = self._expected_get_ct_params(address)
        throttled = self._mocker.MagicMock(spec=Response)
        throttled.status_code = 429

        class ThrottleMock:
            counter = 0

            def side_effect(self):
                if self.counter < retries:
                    self.counter += 1
                    return throttled

                return response

        throttler = ThrottleMock()
        self.add_handler("GET", "contract", expected_params, side_effect=throttler.side_effect)
        response.expected_address = address
        return throttler, response

    def _get_contract_type_response(self, file_name: str) -> Any:
        test_data_path = MOCK_RESPONSES_PATH / f"{file_name}.json"
        with open(test_data_path) as response_data_file:
            return self.get_mock_response(response_data_file, file_name=file_name)

    def _expected_get_ct_params(self, address: str) -> Dict:
        return {"module": "contract", "action": "getsourcecode", "address": address}

    def setup_mock_account_transactions_response(self, address: Optional[AddressType] = None):
        file_name = "get_account_transactions.json"
        test_data_path = MOCK_RESPONSES_PATH / file_name

        if address:
            params = EXPECTED_ACCOUNT_TXNS_PARAMS.copy()
            params["address"] = address
        else:
            params = EXPECTED_ACCOUNT_TXNS_PARAMS

        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(response_data_file, file_name=file_name)
            self.add_handler("GET", "account", params, return_value=response)
            self.set_network("ethereum", "mainnet")
            return response

    def setup_mock_account_transactions_with_ctor_args_response(
        self, address: Optional[AddressType] = None
    ):
        file_name = "get_account_transactions_with_ctor_args.json"
        test_data_path = MOCK_RESPONSES_PATH / file_name

        if address:
            params = EXPECTED_ACCOUNT_TXNS_PARAMS.copy()
            params["address"] = address
        else:
            params = EXPECTED_ACCOUNT_TXNS_PARAMS

        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(response_data_file, file_name=file_name)
            self.add_handler("GET", "account", params, return_value=response)
            self.set_network("ethereum", "mainnet")
            return response

    def get_mock_response(
        self, response_data: Optional[Union[IO, Dict, str, MagicMock]] = None, **kwargs
    ):
        if isinstance(response_data, str):
            return self.get_mock_response({"result": response_data})

        elif isinstance(response_data, _io.TextIOWrapper):
            return self.get_mock_response(json.load(response_data), **kwargs)

        elif isinstance(response_data, MagicMock):
            # Mock wasn't set.
            response_data = {}

        response = self._mocker.MagicMock(spec=Response)
        response.json.return_value = response_data
        response.text = json.dumps(response_data or {})

        response.status_code = 200

        for key, val in kwargs.items():
            setattr(response, key, val)

        return response


@pytest.fixture
def verification_params(address_to_verify):
    ctor_args = ""  # noqa: E501

    return {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": ctor_args,
        "contractaddress": address_to_verify,
        "contractname": "foo.sol:foo",
        "evmversion": None,
        "licenseType": 1,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
        "sourceCode": StringIO(json.dumps(STANDARD_INPUT_JSON)),
    }


@pytest.fixture
def verification_params_with_ctor_args(address_to_verify_with_ctor_args):
    # abi-encoded representation of uint256 value 42
    ctor_args = "000000000000000000000000000000000000000000000000000000000000002a"  # noqa: E501

    json_data = STANDARD_INPUT_JSON.copy()
    json_data["libraryaddress1"] = "0xF2Df0b975c0C9eFa2f8CA0491C2d1685104d2488"

    return {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": ctor_args,
        "contractaddress": address_to_verify_with_ctor_args,
        "contractname": "foo.sol:fooWithConstructor",
        "evmversion": None,
        "licenseType": 1,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
        "sourceCode": StringIO(json.dumps(json_data)),
    }


@pytest.fixture(scope="session")
def address_to_verify(fake_connection, project, account):
    # Deploy the library first.
    library = account.deploy(project.MyLib)
    ape.chain.contracts._local_contract_types[library.address] = library.contract_type

    # Add the library to recompile contract `foo`.
    solidity = project.compiler_manager.solidity
    solidity.add_library(library)

    foo = project.foo.deploy(sender=account)
    ape.chain.contracts._local_contract_types[address] = foo.contract_type
    return foo.address


@pytest.fixture(scope="session")
def address_to_verify_with_ctor_args(fake_connection, project, account):
    # Deploy the library first.
    library = account.deploy(project.MyLib)
    ape.chain.contracts._local_contract_types[library.address] = library.contract_type

    # Add the library to recompile contract `foo`.
    solidity = project.compiler_manager.solidity
    solidity.add_library(library)

    foo = project.fooWithConstructor.deploy(42, sender=account)
    ape.chain.contracts._local_contract_types[address] = foo.contract_type
    return foo.address


@pytest.fixture(scope="session")
def expected_verification_log(address_to_verify):
    return (
        "Contract verification successful!\n"
        f"https://etherscan.io/address/{address_to_verify}#code"
    )


@pytest.fixture(scope="session")
def expected_verification_log_with_ctor_args(address_to_verify_with_ctor_args):
    return (
        "Contract verification successful!\n"
        f"https://etherscan.io/address/{address_to_verify_with_ctor_args}#code"
    )
