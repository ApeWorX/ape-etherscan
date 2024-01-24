import pytest

from ._utils import ecosystems_and_networks

network_ecosystems = pytest.mark.parametrize(
    "ecosystem,network",
    ecosystems_and_networks,
)

DEFAULT_CONFIG = {"name": "ape-etherscan-test"}


@network_ecosystems
def test_no_config(account, ecosystem, network, get_explorer, temp_config):
    """Test default behavior"""
    conf = DEFAULT_CONFIG
    with temp_config(conf):
        explorer = get_explorer(ecosystem, network)
        assert explorer.network.name == network
        assert explorer.network.ecosystem.name == ecosystem
        assert account.query_manager.engines["etherscan"].rate_limit == 5

        client = account.query_manager.engines["etherscan"]._client_factory.get_account_client(
            account
        )
        assert client._retries == 5


def test_config_rate_limit(account, get_explorer, temp_config):
    """Test that rate limit config is set"""
    conf = {**DEFAULT_CONFIG, **{"etherscan": {"ethereum": {"rate_limit": 123}}}}
    with temp_config(conf):
        assert account.query_manager.engines["etherscan"].rate_limit == 123


def test_config_retries(account, get_explorer, temp_config):
    """Test that rate limit config is set"""
    conf = {**DEFAULT_CONFIG, **{"etherscan": {"ethereum": {"retries": 321}}}}
    with temp_config(conf):
        assert account.query_manager.engines["etherscan"].rate_limit == 5
        client = account.query_manager.engines["etherscan"]._client_factory.get_account_client(
            account
        )
        assert client._retries == 321


def test_config_uri(account, get_explorer, mock_provider, temp_config):
    """
    Make sure URI parameter is used when configured
    """
    expected_uri = "https://monke.chain/"
    expected_api_uri = "https://api.monke.chain/api"
    custon_network_name = "monkechain"
    conf = {
        **DEFAULT_CONFIG,
        **{
            "networks": {
                "custom": [
                    {"name": custon_network_name, "chain_id": 31337, "ecosystem": "ethereum"}
                ]
            },
            "etherscan": {
                "ethereum": {
                    custon_network_name: {"uri": expected_uri, "api_uri": expected_api_uri}
                }
            },
        },
    }

    with temp_config(conf):
        with mock_provider("ethereum", "monkechain"):
            assert account.query_manager.engines["etherscan"].etherscan_uri == expected_uri
            assert account.query_manager.engines["etherscan"].etherscan_api_uri == expected_api_uri
            account_client = account.query_manager.engines[
                "etherscan"
            ]._client_factory.get_account_client(account)
            assert account_client.base_uri == expected_api_uri
            contract_client = account.query_manager.engines[
                "etherscan"
            ]._client_factory.get_contract_client(account)
            assert contract_client.base_uri == expected_api_uri
