from typing import Callable

import ape
import pytest

from ape_etherscan import NETWORKS
from ape_etherscan.exceptions import EtherscanResponseError, EtherscanTooManyRequestsError

# A map of each mock response to its contract name for testing `get_contract_type()`.
EXPECTED_CONTRACT_NAME_MAP = {
    "get_contract_response": "BoredApeYachtClub",
    "get_proxy_contract_response": "MIM-UST-f",
    "get_vyper_contract_response": "yvDAI",
}
TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"
PUBLISH_GUID = "123"
ecosystems_and_networks = pytest.mark.parametrize(
    "ecosystem,network",
    [
        ("ethereum", "mainnet"),
        ("ethereum", "mainnet-fork"),
        ("fantom", "opera"),
        ("optimism", "mainnet"),
        ("polygon", "mainnet"),
    ],
)


@pytest.fixture
def verification_params(address):
    ctor_args = "0000000000000005000000000000000000000000000000000000000000000000000000000000000500000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000120000000000000000000000000000000000000000000000000000000000000002a73333362346563316232316330313364393230366536333836653231383935356635616630656533636200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002833623465633162323163303133643932303665363338366532313839353566356166306565336362000000000000000000000000000000000000000000000000"  # noqa: E501
    return {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": ctor_args,
        "contractaddress": address,
        "contractname": "foo.sol:foo",
        "evmversion": None,
        "licenseType": 1,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
    }


@pytest.fixture
def address_to_verify(address):
    contract_type = ape.project.get_contract("foo").contract_type
    ape.chain.contracts._local_contract_types[address] = contract_type
    return address


@pytest.fixture
def verification_tester_cls():
    class VerificationTester:
        counter = 0

        def __init__(self, action_when_found: Callable, threshold: int = 2):
            self.action_when_found = action_when_found
            self.threshold = threshold

        def sim(self):
            # Simulate the contract type waiting in the queue until successful verification
            if self.counter == self.threshold:
                return self.action_when_found()

            self.counter += 1
            return "Pending in the queue"

    return VerificationTester


@pytest.fixture
def setup_verification_test(mock_backend, verification_params, verification_tester_cls):
    def setup(found_handler: Callable, threshold: int = 2):
        mock_backend.setup_mock_account_transactions_response()
        mock_backend.add_handler("POST", "contract", verification_params, return_value=PUBLISH_GUID)
        verification_tester = verification_tester_cls(found_handler, threshold=threshold)
        mock_backend.add_handler(
            "GET", "contract", {"guid": PUBLISH_GUID}, side_effect=verification_tester.sim
        )
        return verification_tester

    return setup


@pytest.fixture
def expected_verification_log(address_to_verify):
    return (
        "Contract verification successful!\n"
        f"https://etherscan.io/address/{address_to_verify}#code"
    )


@pytest.mark.parametrize(
    "ecosystem,network,expected_prefix",
    [
        ("ethereum", NETWORKS["ethereum"][0], "etherscan.io"),
        ("ethereum", f"{NETWORKS['ethereum'][0]}-fork", "etherscan.io"),
        ("ethereum", NETWORKS["ethereum"][1], "ropsten.etherscan.io"),
        ("fantom", NETWORKS["fantom"][0], "ftmscan.com"),
        ("fantom", NETWORKS["fantom"][1], "testnet.ftmscan.com"),
        ("optimism", NETWORKS["optimism"][0], "optimistic.etherscan.io"),
        ("optimism", NETWORKS["optimism"][1], "kovan-optimistic.etherscan.io"),
        ("polygon", NETWORKS["polygon"][0], "polygonscan.com"),
        ("polygon", NETWORKS["polygon"][1], "mumbai.polygonscan.com"),
    ],
)
def test_get_address_url(ecosystem, network, expected_prefix, address, get_explorer):
    expected = f"https://{expected_prefix}/address/{address}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_address_url(address)
    assert actual == expected


@pytest.mark.parametrize(
    "ecosystem,network,expected_prefix",
    [
        ("ethereum", NETWORKS["ethereum"][0], "etherscan.io"),
        ("ethereum", f"{NETWORKS['ethereum'][0]}-fork", "etherscan.io"),
        ("ethereum", NETWORKS["ethereum"][1], "ropsten.etherscan.io"),
        ("fantom", NETWORKS["fantom"][0], "ftmscan.com"),
        ("fantom", NETWORKS["fantom"][1], "testnet.ftmscan.com"),
        ("optimism", NETWORKS["optimism"][0], "optimistic.etherscan.io"),
        ("optimism", NETWORKS["optimism"][1], "kovan-optimistic.etherscan.io"),
        ("polygon", NETWORKS["polygon"][0], "polygonscan.com"),
        ("polygon", NETWORKS["polygon"][1], "mumbai.polygonscan.com"),
    ],
)
def test_get_transaction_url(ecosystem, network, expected_prefix, get_explorer):
    expected = f"https://{expected_prefix}/tx/{TRANSACTION}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_transaction_url(TRANSACTION)
    assert actual == expected


@ecosystems_and_networks
def test_get_contract_type_ecosystems_and_networks(
    mock_backend,
    ecosystem,
    network,
    get_explorer,
):
    # This test parametrizes getting contract types across ecosystem / network combos
    mock_backend.set_ecosystem(ecosystem)
    response = mock_backend.setup_mock_get_contract_type_response("get_contract_response")
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_contract_type(response.expected_address)
    assert actual is not None

    actual = actual.name
    expected = EXPECTED_CONTRACT_NAME_MAP[response.file_name]
    assert actual == expected


@pytest.mark.parametrize(
    "file_name", ("get_proxy_contract_response", ("get_vyper_contract_response"))
)
def test_get_contract_type_additional_types(mock_backend, file_name, explorer):
    # This test parametrizes getting edge-case contract types.
    # NOTE: Purposely not merged with test above to avoid adding a new dimension
    #  to the parametrization.
    response = mock_backend.setup_mock_get_contract_type_response(file_name)
    actual = explorer.get_contract_type(response.expected_address).name
    expected = EXPECTED_CONTRACT_NAME_MAP[response.file_name]
    assert actual == expected


def test_get_account_transactions(mock_backend, explorer, address):
    mock_backend.setup_mock_account_transactions_response()
    actual = [r for r in explorer.get_account_transactions(address)][0].txn_hash
    expected = "0x5780b43d819035ed1fa079171bdce7f0bbeaa6b01f201f8985d279a66cfc6844"
    assert actual == expected


def test_too_many_requests_error(no_api_key, response):
    actual = str(EtherscanTooManyRequestsError(response, "ethereum"))
    assert "ETHERSCAN_API_KEY" in actual


def test_publish_contract(
    explorer,
    address_to_verify,
    setup_verification_test,
    expected_verification_log,
    caplog,
):
    setup_verification_test(lambda: "Pass - You made it!")
    explorer.publish_contract(address_to_verify)
    assert caplog.records[-1].message == expected_verification_log


def test_publish_contract_when_guid_not_found_at_end(
    mocker,
    explorer,
    address_to_verify,
    setup_verification_test,
    expected_verification_log,
    caplog,
):
    def raise_err():
        raise EtherscanResponseError(mocker.MagicMock(), "Resource not found")

    setup_verification_test(raise_err, threshold=1)
    explorer.publish_contract(address_to_verify)
    assert caplog.records[-1].message == expected_verification_log
