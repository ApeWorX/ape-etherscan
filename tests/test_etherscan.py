from collections.abc import Callable

import pytest
from ape.api.query import AccountTransactionQuery

from ape_etherscan.exceptions import EtherscanResponseError, EtherscanTooManyRequestsError

from ._utils import ecosystems_and_networks

# A map of each mock response to its contract name for testing `get_contract_type()`.
EXPECTED_CONTRACT_NAME_MAP = {
    "get_contract_response_flattened": "BoredApeYachtClub",
    "get_contract_response_json": "BoredApeYachtClub",
    "get_contract_response_not_verified": "",
    "get_proxy_contract_response": "MIM-UST-f",
    "get_vyper_contract_response": "yvDAI",
}
TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"
PUBLISH_GUID = "123"

base_url_test = pytest.mark.parametrize(
    "ecosystem,network,url",
    [
        ("ethereum", "mainnet", "etherscan.io"),
        ("ethereum", "mainnet-fork", "etherscan.io"),
        ("ethereum", "sepolia", "sepolia.etherscan.io"),
        ("ethereum", "sepolia-fork", "sepolia.etherscan.io"),
        ("ethereum", "holesky", "holesky.etherscan.io"),
        ("ethereum", "holesky-fork", "holesky.etherscan.io"),
        ("fantom", "opera", "ftmscan.com"),
        ("fantom", "opera-fork", "ftmscan.com"),
        ("fantom", "testnet", "testnet.ftmscan.com"),
        ("fantom", "testnet-fork", "testnet.ftmscan.com"),
        ("arbitrum", "mainnet", "arbiscan.io"),
        ("arbitrum", "mainnet-fork", "arbiscan.io"),
        ("arbitrum", "sepolia", "sepolia.arbiscan.io"),
        ("arbitrum", "sepolia-fork", "sepolia.arbiscan.io"),
        ("optimism", "mainnet", "optimistic.etherscan.io"),
        ("optimism", "mainnet-fork", "optimistic.etherscan.io"),
        ("optimism", "sepolia", "sepolia-optimism.etherscan.io"),
        ("optimism", "sepolia-fork", "sepolia-optimism.etherscan.io"),
        ("polygon", "mainnet", "polygonscan.com"),
        ("polygon", "mainnet-fork", "polygonscan.com"),
        ("polygon", "amoy", "amoy.polygonscan.com"),
        ("polygon", "amoy-fork", "amoy.polygonscan.com"),
        ("polygon-zkevm", "mainnet", "zkevm.polygonscan.com"),
        ("polygon-zkevm", "cardona", "cardona-zkevm.polygonscan.com"),
        ("base", "mainnet", "basescan.org"),
        ("base", "sepolia", "sepolia.basescan.org"),
        ("blast", "mainnet", "blastscan.io"),
        ("blast", "sepolia", "sepolia.blastscan.io"),
        ("avalanche", "mainnet", "snowtrace.io"),
        ("avalanche", "fuji", "testnet.snowtrace.io"),
        ("bsc", "mainnet", "bscscan.com"),
        ("bsc", "mainnet-fork", "bscscan.com"),
        ("bsc", "testnet", "testnet.bscscan.com"),
        ("bsc", "testnet-fork", "testnet.bscscan.com"),
        ("gnosis", "mainnet", "gnosisscan.io"),
        ("gnosis", "mainnet-fork", "gnosisscan.io"),
    ],
)


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
def setup_verification_test(
    mock_backend, verification_params, verification_tester_cls, contract_to_verify
):
    def setup(found_handler: Callable, threshold: int = 2):
        overrides = _acct_tx_overrides(contract_to_verify)
        mock_backend.setup_mock_account_transactions_response(
            address=contract_to_verify.address, **overrides
        )
        mock_backend.add_handler("POST", "contract", verification_params, return_value=PUBLISH_GUID)
        verification_tester = verification_tester_cls(found_handler, threshold=threshold)
        mock_backend.add_handler(
            "GET",
            "contract",
            {"guid": PUBLISH_GUID},
            side_effect=verification_tester.sim,
        )
        return verification_tester

    return setup


@pytest.fixture
def setup_verification_test_with_ctor_args(
    mock_backend,
    verification_params_with_ctor_args,
    verification_tester_cls,
    contract_to_verify_with_ctor_args,
    constructor_arguments,
):
    def setup(found_handler: Callable, threshold: int = 2):
        overrides = _acct_tx_overrides(
            contract_to_verify_with_ctor_args, args=constructor_arguments
        )
        mock_backend.setup_mock_account_transactions_with_ctor_args_response(
            address=contract_to_verify_with_ctor_args.address, **overrides
        )
        mock_backend.add_handler(
            "POST", "contract", verification_params_with_ctor_args, return_value=PUBLISH_GUID
        )
        verification_tester = verification_tester_cls(found_handler, threshold=threshold)
        mock_backend.add_handler(
            "GET",
            "contract",
            {"guid": PUBLISH_GUID},
            side_effect=verification_tester.sim,
        )
        return verification_tester

    return setup


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
    response = mock_backend.setup_mock_get_contract_type_response("get_contract_response_flattened")
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
def test_get_contract_type_additional_types(mock_backend, file_name, explorer, connection):
    # This test parametrizes getting edge-case contract types.
    # NOTE: Purposely not merged with test above to avoid adding a new dimension
    #  to the parametrization.
    _ = connection  # Needed for symbol lookup
    mock_backend.set_network("ethereum", "mainnet")
    response = mock_backend.setup_mock_get_contract_type_response(file_name)
    actual = explorer.get_contract_type(response.expected_address).name
    expected = EXPECTED_CONTRACT_NAME_MAP[response.file_name]
    assert actual == expected


def test_get_contract_type_with_rate_limiting(mock_backend, explorer, connection):
    """
    This test ensures the rate limiting logic in the Etherscan client works.
    """
    _ = connection  # Needed for calling symbol() on Vyper_contract
    file_name = "get_vyper_contract_response"
    setter_upper = mock_backend.setup_mock_get_contract_type_response_with_throttling
    throttler, response = setter_upper(file_name)

    # We still eventually get the response.
    actual = explorer.get_contract_type(response.expected_address).name
    expected = EXPECTED_CONTRACT_NAME_MAP[response.file_name]
    assert actual == expected
    assert throttler.counter == 2  # Prove that it actually throttled.


def test_get_account_transactions(mock_backend, account):
    mock_backend.setup_mock_account_transactions_response(account.address)
    query = AccountTransactionQuery(
        start_nonce=0, stop_nonce=0, columns=["txn_hash"], account=account.address
    )
    actual = next(account.query_manager.engines["etherscan"].perform_query(query)).txn_hash
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
    fake_connection,
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


def test_publish_contract_with_ctor_args(
    explorer,
    address_to_verify_with_ctor_args,
    setup_verification_test_with_ctor_args,
    expected_verification_log_with_ctor_args,
    caplog,
    fake_connection,
):
    setup_verification_test_with_ctor_args(lambda: "Pass - You made it!")
    explorer.publish_contract(address_to_verify_with_ctor_args)
    assert caplog.records[-1].message == expected_verification_log_with_ctor_args


def _acct_tx_overrides(contract, args=None):
    suffix = args or ""
    if suffix.startswith("0x"):
        suffix = suffix[2:]

    # Include construcor aguments!
    ct = contract.contract_type
    prefix = ct.deployment_bytecode.bytecode
    code = f"{prefix}{suffix}"
    return {"result": [{"input": code}]}
