import pytest
from ape.exceptions import ProjectError
from ape.utils import create_tempdir

from ape_etherscan.dependency import EtherscanDependency


@pytest.mark.parametrize(
    "verification_type,contract_address,expected_name",
    [
        ("flattened", "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", "BoredApeYachtClub"),
        ("json", "0x000075Dc60EdE898f11b0d5C6cA31D7A6D050eeD", "LOVEYOU"),
    ],
)
def test_dependency(mock_backend, verification_type, expected_name, contract_address):
    ecosystem = "ethereum"
    network = "mainnet"
    mock_backend.set_network(ecosystem, network)
    mock_backend.setup_mock_get_contract_type_response(f"get_contract_response_{verification_type}")

    dependency = EtherscanDependency(
        name="Apes",
        etherscan=contract_address,
        ecosystem=ecosystem,
        network=network,
    )
    actual = dependency._get_manifest()
    assert dependency.version_id == f"{ecosystem}_{network}"
    assert f"{expected_name}.sol" in actual.sources
    assert actual.compilers[0].name == "Solidity"
    assert not actual.compilers[0].settings["optimizer"]["enabled"]
    assert actual.compilers[0].contractTypes == [expected_name]


def test_dependency_not_verified(mock_backend):
    mock_backend.set_network("ethereum", "mainnet")
    mock_backend.setup_mock_get_contract_type_response("get_contract_response_not_verified")
    dependency = EtherscanDependency(
        name="Apes",
        etherscan="0x5777d92f208679db4b9778590fa3cab3ac9e2168",
        ecosystem="ethereum",
        network="mainnet",
    )
    expected = "Etherscan dependency 'apes' not verified."
    with create_tempdir() as temp_dir:
        with pytest.raises(ProjectError, match=expected):
            dependency.fetch(temp_dir)
