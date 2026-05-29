import json

import pytest

from ape.utils import ManagerAccessMixin
from ape_etherscan.client import AccountClient, ContractClient
from ape_etherscan.types import EtherscanInstance
from ape_etherscan.verify import extract_constructor_arguments_from_creation


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


class TestContractClient(ManagerAccessMixin):
    @pytest.fixture
    def instance(self) -> EtherscanInstance:
        return EtherscanInstance(
            ecosystem_name="ethereum",
            network_name="my-network",
            uri="https://explorer.example.com",
            api_uri="https://explorer.example.com/api",
        )

    @pytest.fixture
    def contract_client(self, instance):
        return ContractClient(instance, "0x274b028b03A250cA03644E6c578D81f019eE1323")

    def _capture_verify(self, mocker, contract_client, std_json, **kwargs):
        captured: dict = {}
        resp = mocker.MagicMock()
        resp.value = "guid123"

        def fake_post(json_dict=None, headers=None):
            captured.update(json_dict)
            return resp

        contract_client._post = fake_post
        guid = contract_client.verify_source_code(std_json, "0.4.3", **kwargs)
        assert guid == "guid123"
        return captured

    def test_verify_source_code_vyper(self, mocker, contract_client):
        std_json = {
            "language": "Vyper",
            "sources": {"contracts/AZPay.vy": {"content": "# code"}},
            "settings": {"optimize": "gas"},
        }
        captured = self._capture_verify(
            mocker,
            contract_client,
            std_json,
            contract_name="contracts/AZPay.vy:AZPay",
            language="vyper",
        )
        assert captured["codeformat"] == "vyper-json"
        assert captured["compilerversion"] == "vyper:0.4.3"
        assert json.loads(captured["sourceCode"].read()) == std_json

    def test_verify_source_code_vyper_already_prefixed(self, mocker, contract_client):
        # When the version already carries the ``vyper:`` prefix, don't double it.
        std_json = {"language": "Vyper", "sources": {}, "settings": {}}
        contract_client._post = lambda json_dict=None, headers=None: type(
            "R", (), {"value": "guid123"}
        )()
        guid = contract_client.verify_source_code(
            std_json, "vyper:0.4.3", contract_name="c.vy:C", language="vyper"
        )
        assert guid == "guid123"

    def test_verify_source_code_solidity_standard_json(self, mocker, contract_client):
        std_json = {"language": "Solidity", "sources": {}, "settings": {}}
        captured = self._capture_verify(mocker, contract_client, std_json, contract_name="C.sol:C")
        assert captured["codeformat"] == "solidity-standard-json-input"
        assert captured["compilerversion"] == "v0.4.3"


def test_extract_constructor_arguments_from_creation():
    creation = "0x6080604052"
    args = "00" * 32
    # Clean prefix => returns the trailing args.
    assert extract_constructor_arguments_from_creation(creation + args, creation) == args
    # No trailing bytes => empty string (not None).
    assert extract_constructor_arguments_from_creation(creation, creation) == ""
    # Not a prefix (e.g. unlinked library placeholders) => None to allow fallback.
    assert extract_constructor_arguments_from_creation("0xabcd", "0xffff") is None
