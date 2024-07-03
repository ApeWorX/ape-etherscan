import json
import os
import shutil
from collections.abc import Callable
from contextlib import contextmanager
from io import StringIO
from json import JSONDecodeError
from pathlib import Path
from tempfile import mkdtemp
from typing import IO, Any, Optional, Union
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
from ape_etherscan.verify import LicenseType

DATA_FOLDER = Path(mkdtemp()).resolve()
ape.config.DATA_FOLDER = DATA_FOLDER

HERE = Path(__file__).parent
MOCK_RESPONSES_PATH = HERE / "mock_responses"
FOO_SOURCE_CODE = (HERE / "contracts" / "subcontracts" / "foo.sol").read_text()
BAR_SOURCE_CODE = (HERE / "dependency" / "contracts" / "bar.sol").read_text()


@pytest.fixture(scope="session", autouse=True)
def clean_datafolder():
    yield  # Run all collected tests.
    shutil.rmtree(DATA_FOLDER, ignore_errors=True)


@pytest.fixture(scope="session")
def standard_input_json(library):
    return {
        "language": "Solidity",
        "sources": {
            "tests/contracts/.cache/bar/local/contracts/bar.sol": {"content": BAR_SOURCE_CODE},
            "tests/contracts/subcontracts/foo.sol": {"content": FOO_SOURCE_CODE},
        },
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {
                "tests/contracts/.cache/bar/local/contracts/bar.sol": {
                    "": ["ast"],
                    "*": OUTPUT_SELECTION,
                },
                "tests/contracts/subcontracts/foo.sol": {"": ["ast"], "*": OUTPUT_SELECTION},
            },
            "remappings": [
                "@bar=tests/contracts/.cache/bar/local",
                "bar=tests/contracts/.cache/bar/local",
            ],
        },
        "libraryname1": "MyLib",
        "libraryaddress1": library.address,
    }


@pytest.fixture(autouse=True)
def connection(explorer):
    with ape.networks.ethereum.mainnet.use_provider("infura") as provider:
        # TODO: Figure out why this is still needed sometimes,
        #   even after https://github.com/ApeWorX/ape/pull/2022
        if not provider.is_connected:
            provider.connect()

        yield provider


@pytest.fixture
def mock_provider(mocker):
    @contextmanager
    def func(ecosystem_name="ethereum", network_name="mock"):
        mock_provider = mocker.MagicMock()
        mock_provider.network = mocker.MagicMock()
        mock_provider.network.name = network_name
        mock_provider.network.ecosystem = mocker.MagicMock()
        mock_provider.network.ecosystem.name = ecosystem_name
        ape.networks.active_provider = mock_provider

        yield mock_provider

        ape.networks.active_provider = None

    return func


def make_source(base_dir: Path, name: str, content: str):
    source_file = base_dir / f"{name}.sol"
    source_file.touch()
    source_file.write_text(content)


@pytest.fixture(scope="session")
def project():
    return ape.project


@pytest.fixture(scope="session")
def address(contract_to_verify):
    return contract_to_verify.address


@pytest.fixture(scope="session")
def contract_address_map(address):
    return {
        "get_contract_response_flattened": address,
        "get_contract_response_json": "0x000075Dc60EdE898f11b0d5C6cA31D7A6D050eeD",
        "get_contract_response_not_verified": "0x5777d92f208679DB4b9778590Fa3CAB3aC9e2168",
        "get_proxy_contract_response": "0x55A8a39bc9694714E2874c1ce77aa1E599461E18",
        "get_vyper_contract_response": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
    }


@pytest.fixture(scope="session")
def account():
    return ape.accounts.test_accounts[0]


@pytest.fixture
def get_expected_account_txns_params():
    def fn(addr):
        return {
            "module": "account",
            "action": "txlist",
            "address": addr,
            "endblock": None,
            "startblock": None,
            "offset": 100,
            "page": 1,
            "sort": "asc",
        }

    return fn


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
        ecosystem_name: str = "ethereum", network_name: str = "development", no_mock=False
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
            explorer = Etherscan.model_construct(name=etherscan.name, network=network)
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
def mock_backend(mocker, get_expected_account_txns_params, contract_address_map):
    session = mocker.MagicMock()
    backend = MockEtherscanBackend(
        mocker, session, get_expected_account_txns_params, contract_address_map
    )
    _APIClient.session = session
    return backend


class MockEtherscanBackend:
    def __init__(self, mocker, session, get_expected_account_txns_params, contract_address_map):
        self.mocker = mocker
        self.session = session
        self.expected_base_uri = "https://api.etherscan.io/api"  # Default
        self.handlers = {"get": {}, "post": {}}
        self.get_expected_account_txns_params = get_expected_account_txns_params
        self.contract_address_map = contract_address_map

    @cached_property
    def expected_uri_map(
        self,
    ) -> dict[str, dict[str, str]]:
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
                "holesky": testnet_url("holesky", "etherscan"),
                "sepolia": testnet_url("sepolia", "etherscan"),
            },
            "arbitrum": {
                "mainnet": url("arbiscan"),
                "sepolia": testnet_url("sepolia", "arbiscan"),
            },
            "fantom": {
                "opera": com_url("ftmscan"),
                "testnet": com_testnet_url("testnet", "ftmscan"),
            },
            "optimism": {
                "mainnet": testnet_url("optimistic", "etherscan"),
                "sepolia": testnet_url("sepolia-optimistic", "etherscan"),
            },
            "polygon": {
                "mainnet": com_url("polygonscan"),
                "amoy": com_testnet_url("testnet", "polygonscan"),
            },
            "base": {
                "sepolia": org_testnet_url("sepolia", "basescan"),
                "mainnet": org_url("basescan"),
            },
            "blast": {
                "sepolia": testnet_url("sepolia", "blastscan"),
                "mainnet": url("blastscan"),
            },
            "polygon-zkevm": {
                "mainnet": com_testnet_url("zkevm", "polygonscan"),
                "cardona": com_testnet_url("cardona-zkevm", "polygonscan"),
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
        self.expected_base_uri = self.expected_uri_map[ecosystem][network.replace("-fork", "")]

    def add_handler(
        self,
        method: str,
        module: str,
        expected_params: dict,
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

        self.handlers[method.lower()][module] = handler
        self.session.request.side_effect = self.handle_request

    def handle_request(self, method, base_uri, timeout, headers=None, params=None, data=None):
        if params and "apikey" in params:
            del params["apikey"]
        if data and "apiKey" in data:
            del data["apiKey"]

        assert base_uri == self.expected_base_uri

        if params:
            module = params.get("module")
        elif data:
            module = data.get("module")
        else:
            raise AssertionError("Expected either 'params' or 'data'.")

        handler = self.handlers[method.lower()][module]
        return handler(self, method, base_uri, headers=headers, params=params, data=data)

    def setup_mock_get_contract_type_response(self, file_name: str):
        response = self._get_contract_type_response(file_name)
        address = self.contract_address_map[file_name]
        expected_params = self._expected_get_ct_params(address)
        self.add_handler("GET", "contract", expected_params, return_value=response)
        response.expected_address = address
        return response

    def setup_mock_get_contract_type_response_with_throttling(
        self, file_name: str, retries: int = 2
    ):
        response = self._get_contract_type_response(file_name)
        address = self.contract_address_map[file_name]
        expected_params = self._expected_get_ct_params(address)
        throttled = self.mocker.MagicMock(spec=Response)
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
        assert test_data_path.is_file(), f"Setup failed - missing test data {file_name}"
        if "flattened" in file_name:
            with open(test_data_path) as response_data_file:
                return self.get_mock_response(response_data_file, file_name=file_name)

        else:
            # NOTE: Since the JSON is messed up for these, we can' load the mocks
            # even without a weird hack.
            content = (
                MOCK_RESPONSES_PATH / "get_contract_response_json_source_code.json"
            ).read_text()
            data = json.loads(test_data_path.read_text())
            data["SourceCode"] = content
            return self.get_mock_response(data, file_name=file_name)

    def _expected_get_ct_params(self, address: str) -> dict:
        return {"module": "contract", "action": "getsourcecode", "address": address}

    def setup_mock_account_transactions_response(self, address: AddressType, **overrides):
        file_name = "get_account_transactions.json"
        test_data_path = MOCK_RESPONSES_PATH / file_name
        params = self.get_expected_account_txns_params(address)
        params["address"] = address

        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(
                response_data_file, file_name=file_name, response_overrides=overrides
            )

        return self._setup_account_response(params, response)

    def setup_mock_account_transactions_with_ctor_args_response(
        self, address: AddressType, **overrides
    ):
        file_name = "get_account_transactions_with_ctor_args.json"
        test_data_path = MOCK_RESPONSES_PATH / file_name
        params = self.get_expected_account_txns_params(address)
        params["address"] = address

        with open(test_data_path) as response_data_file:
            response = self.get_mock_response(
                response_data_file, file_name=file_name, response_overrides=overrides
            )

        return self._setup_account_response(params, response)

    def _setup_account_response(self, params, response):
        self.add_handler("GET", "account", params, return_value=response)
        self.set_network("ethereum", "mainnet")
        return response

    def get_mock_response(
        self, response_data: Optional[Union[IO, dict, str, MagicMock]] = None, **kwargs
    ):
        if isinstance(response_data, str):
            return self.get_mock_response({"result": response_data, **kwargs})

        elif isinstance(response_data, _io.TextIOWrapper):
            return self.get_mock_response(json.load(response_data), **kwargs)

        elif isinstance(response_data, MagicMock):
            # Mock wasn't set.
            response_data = {**kwargs}

        assert isinstance(response_data, dict)
        return self._get_mock_response(response_data=response_data, **kwargs)

    def _get_mock_response(
        self,
        response_data: Optional[dict] = None,
        response_text: Optional[str] = None,
        *args,
        **kwargs,
    ):
        response = self.mocker.MagicMock(spec=Response)
        if response_data:
            assert isinstance(response_data, dict)  # For mypy
            overrides: dict = kwargs.get("response_overrides", {})
            response.json.return_value = {**response_data, **overrides}
            if not response_text:
                response_text = json.dumps(response_data or {})

        if response_text:
            response.text = response_text

        response.status_code = 200
        for key, val in kwargs.items():
            setattr(response, key, val)

        return response


@pytest.fixture
def verification_params(address_to_verify, standard_input_json):
    ctor_args = ""  # noqa: E501

    return {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": ctor_args,
        "contractaddress": address_to_verify,
        "contractname": "tests/contracts/subcontracts/foo.sol:foo",
        "evmversion": None,
        "licenseType": LicenseType.AGLP_3.value,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
        "sourceCode": StringIO(json.dumps(standard_input_json)),
    }


@pytest.fixture(scope="session")
def constructor_arguments():
    # abi-encoded representation of uint256 value 42
    return "000000000000000000000000000000000000000000000000000000000000002a"  # noqa: E501


@pytest.fixture(scope="session")
def verification_params_with_ctor_args(
    address_to_verify_with_ctor_args, library, standard_input_json, constructor_arguments
):
    json_data = standard_input_json.copy()
    json_data["libraryaddress1"] = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"

    return {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": constructor_arguments,
        "contractaddress": address_to_verify_with_ctor_args,
        "contractname": "tests/contracts/subcontracts/foo.sol:fooWithConstructor",
        "evmversion": None,
        "licenseType": LicenseType.AGLP_3.value,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
        "sourceCode": StringIO(json.dumps(json_data)),
    }


@pytest.fixture(scope="session")
def chain():
    return ape.chain


@pytest.fixture(scope="session")
def solidity(project):
    return project.compiler_manager.solidity


@pytest.fixture(scope="session")
def library(account, project, chain, solidity):
    lib = account.deploy(project.MyLib)
    chain.contracts._local_contract_types[lib.address] = lib.contract_type
    solidity.add_library(lib)
    return lib


@pytest.fixture(scope="session")
def contract_to_verify(fake_connection, library, project, account):
    _ = library  # Ensure library is deployed first.
    return project.foo.deploy(sender=account)


@pytest.fixture(scope="session")
def address_to_verify(contract_to_verify):
    return contract_to_verify


@pytest.fixture(scope="session")
def contract_to_verify_with_ctor_args(fake_connection, project, account):
    # Deploy the library first.
    library = account.deploy(project.MyLib)
    ape.chain.contracts._local_contract_types[library.address] = library.contract_type

    # Add the library to recompile contract `foo`.
    solidity = project.compiler_manager.solidity
    solidity.add_library(library)

    foo = project.fooWithConstructor.deploy(42, sender=account)
    ape.chain.contracts._local_contract_types[address] = foo.contract_type
    return foo


@pytest.fixture(scope="session")
def address_to_verify_with_ctor_args(contract_to_verify_with_ctor_args):
    return contract_to_verify_with_ctor_args.address


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
