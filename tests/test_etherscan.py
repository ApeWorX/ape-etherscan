import ape
import pytest

from ape_etherscan import NETWORKS
from ape_etherscan.exceptions import EtherscanTooManyRequestsError

# A map of each mock response to its contract name for testing `get_contract_type()`.
EXPECTED_CONTRACT_NAME_MAP = {
    "get_contract_response": "BoredApeYachtClub",
    "get_proxy_contract_response": "MIM-UST-f",
    "get_vyper_contract_response": "yvDAI",
}
ecosystems_and_networks = pytest.mark.parametrize(
    "ecosystem,network",
    [
        ("ethereum", "mainnet"),
        ("ethereum", "mainnet-fork"),
        ("fantom", "opera"),
        ("optimism", "mainnet"),
    ],
)
TRANSACTION = "0x0da22730986e96aaaf5cedd5082fea9fd82269e41b0ee020d966aa9de491d2e6"


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
    actual = [r for r in explorer.get_account_transactions(address)]
    expected_value_from_response = "GENESIS_ddbd2b932c763ba5b1b7ae3b362eac3e8d40121a"
    assert actual[0].txn_hash == expected_value_from_response


def test_too_many_requests_error(no_api_key):
    actual = str(EtherscanTooManyRequestsError(None, "ethereum"))
    assert "ETHERSCAN_API_KEY" in actual


def test_publish_contract(
    mock_backend,
    address,
    explorer,
    caplog,
):
    contract_type = ape.project.get_contract("foo").contract_type
    ape.chain.contracts._local_contract_types[address] = contract_type
    guid = "123"
    mock_backend.setup_mock_account_transactions_response()

    expected_verification_params = {
        "action": "verifysourcecode",
        "codeformat": "solidity-standard-json-input",
        "constructorArguements": b"",
        "contractaddress": "0xFe80e7afB7041c1592a2A5d8f617518c1591Aad4",
        "contractname": "foo.sol:foo",
        "evmversion": None,
        "licenseType": 1,
        "module": "contract",
        "optimizationUsed": 1,
        "runs": 200,
    }
    mock_backend.add_handler("POST", "contract", expected_verification_params, return_value=guid)

    class VerificationTester:
        counter = 0
        threshold = 5

        def sim(self):
            # Simulate the contract type waiting in the queue until successful verification
            if self.counter == self.threshold:
                return "Pass - You made it!"

            self.counter += 1
            return "Pending in the queue"

    verification_tester = VerificationTester()
    mock_backend.add_handler("GET", "contract", {"guid": 123}, side_effect=verification_tester.sim)
    explorer.publish_contract(address)
    assert caplog.records[-1].message == (
        "Contract verification successful!\n"
        "https://etherscan.io/address/0xFe80e7afB7041c1592a2A5d8f617518c1591Aad4#code"
    )
