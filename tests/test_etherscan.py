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

# Every supported ecosystem / network combo as `[("ecosystem", "network") ... ]`
ecosystems_and_networks = [
    p
    for plist in [
        [(e, n) for n in nets] + [(e, f"{n}-fork") for n in nets] for e, nets in NETWORKS.items()
    ]
    for p in plist
]
base_url_test = pytest.mark.parametrize(
    "ecosystem,network,url",
    [
        ("ethereum", "mainnet", "etherscan.io"),
        ("ethereum", "mainnet-fork", "etherscan.io"),
        ("ethereum", "goerli", "goerli.etherscan.io"),
        ("ethereum", "goerli-fork", "goerli.etherscan.io"),
        ("fantom", "opera", "ftmscan.com"),
        ("fantom", "opera-fork", "ftmscan.com"),
        ("fantom", "testnet", "testnet.ftmscan.com"),
        ("fantom", "testnet-fork", "testnet.ftmscan.com"),
        ("arbitrum", "mainnet", "arbiscan.io"),
        ("arbitrum", "mainnet-fork", "arbiscan.io"),
        ("arbitrum", "goerli", "goerli.arbiscan.io"),
        ("arbitrum", "goerli-fork", "goerli.arbiscan.io"),
        ("optimism", "mainnet", "optimistic.etherscan.io"),
        ("optimism", "mainnet-fork", "optimistic.etherscan.io"),
        ("optimism", "goerli", "goerli-optimistic.etherscan.io"),
        ("optimism", "goerli-fork", "goerli-optimistic.etherscan.io"),
        ("polygon", "mainnet", "polygonscan.com"),
        ("polygon", "mainnet-fork", "polygonscan.com"),
        ("polygon", "mumbai", "mumbai.polygonscan.com"),
        ("polygon", "mumbai-fork", "mumbai.polygonscan.com"),
        ("avalanche", "mainnet", "snowtrace.io"),
        ("bsc", "mainnet", "bscscan.com"),
        ("bsc", "mainnet-fork", "bscscan.com"),
        ("bsc", "testnet", "testnet.bscscan.com"),
        ("bsc", "testnet-fork", "testnet.bscscan.com"),
    ],
)


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


@base_url_test
def test_get_address_url(ecosystem, network, url, address, get_explorer):
    expected = f"https://{url}/address/{address}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_address_url(address)
    assert actual == expected


@base_url_test
def test_get_transaction_url(ecosystem, network, url, get_explorer):
    expected = f"https://{url}/tx/{TRANSACTION}"
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_transaction_url(TRANSACTION)
    assert actual == expected


@pytest.mark.parametrize("ecosystem,network", ecosystems_and_networks)
def test_get_contract_type_ecosystems_and_networks(
    mock_backend,
    ecosystem,
    network,
    get_explorer,
):
    # This test parametrizes getting contract types across ecosystem / network combos
    mock_backend.set_network(ecosystem, network)
    response = mock_backend.setup_mock_get_contract_type_response("get_contract_response")
    explorer = get_explorer(ecosystem, network)
    actual = explorer.get_contract_type(response.expected_address)
    contract_type_from_lowered_address = explorer.get_contract_type(
        response.expected_address.lower()
    )
    assert actual is not None
    assert actual == contract_type_from_lowered_address

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
