import pytest

from ape_etherscan.types import EtherscanResponse


class TestEtherscanResponse:
    @pytest.fixture
    def response(self, mocker):
        return mocker.MagicMock()

    @pytest.mark.parametrize("value", ([], [{"foo": "bar"}], None))
    def test_value(self, response, value):
        response.json.return_value = {"result": value}
        resp = EtherscanResponse(response, "my-ecosystem", raise_on_exceptions=False)
        assert resp.value == value
