import pytest
from ape.utils import ManagerAccessMixin

from ape_etherscan.client import AccountClient
from ape_etherscan.types import EtherscanInstance


class TestAccountClient(ManagerAccessMixin):
    @pytest.fixture
    def instance(self) -> EtherscanInstance:
        return EtherscanInstance(
            ecosystem_name="mye-cosystem",
            network_name="my-network",
            uri="https://explorer.example.com",
            api_uri="https://explorer.example.com/api",
        )

    @pytest.fixture
    def address(self):
        return self.account_manager.test_accounts[0]

    @pytest.fixture
    def mock_session(self, mocker):
        return mocker.MagicMock()

    @pytest.fixture
    def account_client(self, mock_session, instance, address):
        client = AccountClient(instance, address)
        client.session = mock_session
        return client

    def test_get_all_normal_transactions(self, mocker, account_client):
        start_block = 6
        end_block = 8
        end_page = 3

        # Setup session.
        def get_txns(*args, **kwargs):
            # Make it page a bit.
            page = kwargs.get("params").get("page")
            result = [] if page == end_page else [{"page": page}]
            resp = mocker.MagicMock()
            resp.json.return_value = {"result": result}
            return resp

        account_client.session.request.side_effect = get_txns

        fn = account_client.get_all_normal_transactions
        iterator = fn(start_block=start_block, end_block=end_block, offset=1, sort="desc")
        actual = [x for x in iterator]
        expected = [{"page": 1}, {"page": 2}]
        assert actual == expected
