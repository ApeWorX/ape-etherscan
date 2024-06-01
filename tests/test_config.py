import pytest

from ._utils import ecosystems_and_networks

network_ecosystems = pytest.mark.parametrize(
    "ecosystem,network",
    ecosystems_and_networks,
)


@network_ecosystems
def test_no_config(account, ecosystem, network, get_explorer, project):
    """Test default behavior"""
    with project.temp_config(name="ape-etherscan-test"):
        explorer = get_explorer(ecosystem, network)
        assert explorer.network.name == network
        assert explorer.network.ecosystem.name == ecosystem
        assert account.query_manager.engines["etherscan"].rate_limit == 5

        engine = account.query_manager.engines["etherscan"]
        client = engine._client_factory.get_account_client(account)
        assert client._retries == 5


def test_config_rate_limit(account, project):
    """Test that rate limit config is set"""
    with project.temp_config(etherscan={"ethereum": {"rate_limit": 123}}):
        engine = account.query_manager.engines["etherscan"]
        assert engine.rate_limit == 123


def test_config_retries(account, project):
    """Test that rate limit config is set"""
    with project.temp_config(etherscan={"ethereum": {"retries": 321}}):
        engine = account.query_manager.engines["etherscan"]
        assert engine.rate_limit == 5
        client = engine._client_factory.get_account_client(account)
        assert client._retries == 321


def test_config_uri(account, mock_provider, project):
    """
    Make sure URI parameter is used when configured
    """
    expected_uri = "https://monke.chain/"
    expected_api_uri = "https://api.monke.chain/api"
    custom_network_name = "monkechain"
    networks_conf = (
        {"custom": [{"name": custom_network_name, "chain_id": 31337, "ecosystem": "ethereum"}]},
    )

    explorer_confg = {
        "ethereum": {custom_network_name: {"uri": expected_uri, "api_uri": expected_api_uri}}
    }

    with project.temp_config(networks=networks_conf, etherscan=explorer_confg):
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
