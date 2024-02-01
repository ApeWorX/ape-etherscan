from ape_etherscan.dependency import EtherscanDependency


def test_dependency(mock_backend):
    mock_backend.set_network("ethereum", "mainnet")
    mock_backend.setup_mock_get_contract_type_response("get_contract_response")

    dependency = EtherscanDependency(
        name="Apes",
        etherscan="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        ecosystem="ethereum",
        network="mainnet",
    )
    actual = dependency.extract_manifest()
    assert "BoredApeYachtClub.sol" in actual.sources
