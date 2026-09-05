from app.services.merkle_service import build_levels, proof_for, sha256_hex, verify_proof


def test_merkle_proof_verifies_for_each_leaf():
    leaves = [sha256_hex(f"event-{index}".encode()) for index in range(5)]
    root = build_levels(leaves)[-1][0]
    for index, leaf in enumerate(leaves):
        assert verify_proof(leaf, proof_for(leaves, index), root)


def test_corrupted_merkle_proof_fails():
    leaves = [sha256_hex(b"one"), sha256_hex(b"two"), sha256_hex(b"three")]
    proof = proof_for(leaves, 1)
    proof[0] = {**proof[0], "hash": sha256_hex(b"corrupted")}
    assert not verify_proof(leaves[1], proof, build_levels(leaves)[-1][0])
