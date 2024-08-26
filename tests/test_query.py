import pytest
from ape.api.query import ContractCreationQuery
from ape.utils import ManagerAccessMixin


@pytest.fixture
def query_engine():
    return ManagerAccessMixin.query_manager.engines["etherscan"]


def test_contract_creation_receipt(query_engine, mock_backend):
    address = "0x388C818CA8B9251b393131C08a736A67ccB19297"
    creator = "0xDB65702A9b26f8a643a31a4c84b9392589e03D7c"

    # Setup backend.
    params = {"action": "getcontractcreation", "contractaddresses": [address]}
    return_value = [
        {
            "contractAddress": address,
            "contractCreator": creator.lower(),
            "txHash": "0xd72cf25e4a5fe3677b6f9b2ae13771e02ad66f8d2419f333bb8bde3147bd4294",
        }
    ]
    mock_backend.add_handler("GET", "contract", params, return_value=return_value)

    # Perform query.
    query = ContractCreationQuery(contract=address, columns=["*"])
    result = list(query_engine.perform_query(query))

    assert len(result) == 1
    assert result[0].deployer == creator
