// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract CaseIntegrityAnchor {
    struct Anchor { bytes32 merkleRoot; bytes32 metadataCommitment; uint256 timestamp; }
    mapping(uint256 => Anchor) public anchors;
    address public immutable authority;
    event MerkleRootAnchored(uint256 indexed batchId, bytes32 merkleRoot, bytes32 metadataCommitment, uint256 timestamp);

    constructor(address _authority) {
        require(_authority != address(0), "ZERO_AUTHORITY");
        authority = _authority;
    }
    function anchorMerkleRoot(bytes32 root, uint256 batchId, bytes32 metadataCommitment) external {
        require(msg.sender == authority, "UNAUTHORIZED");
        require(anchors[batchId].timestamp == 0, "BATCH_EXISTS");
        require(root != bytes32(0), "ZERO_ROOT");
        require(metadataCommitment != bytes32(0), "ZERO_METADATA_COMMITMENT");
        anchors[batchId] = Anchor(root, metadataCommitment, block.timestamp);
        emit MerkleRootAnchored(batchId, root, metadataCommitment, block.timestamp);
    }
    function verifyAnchor(uint256 batchId, bytes32 root) external view returns (bool) {
        return anchors[batchId].timestamp != 0 && anchors[batchId].merkleRoot == root;
    }
}
