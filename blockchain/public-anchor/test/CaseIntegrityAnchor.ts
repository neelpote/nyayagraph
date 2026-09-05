import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();

async function expectRevert(action: Promise<unknown>, reason: string) {
  try {
    await action;
    expect.fail(`Expected transaction to revert with ${reason}`);
  } catch (error) {
    expect(String(error)).to.include(reason);
  }
}

describe("CaseIntegrityAnchor", function () {
  async function deploy() {
    const [authority, outsider] = await ethers.getSigners();
    const factory = await ethers.getContractFactory("CaseIntegrityAnchor");
    const contract = await factory.deploy(authority.address);
    return { contract, authority, outsider };
  }

  it("anchors and verifies a root", async function () {
    const { contract } = await deploy();
    const root = ethers.keccak256(ethers.toUtf8Bytes("root"));
    const metadata = ethers.keccak256(ethers.toUtf8Bytes("schema:1"));
    await (await contract.anchorMerkleRoot(root, 17, metadata)).wait();
    expect(await contract.verifyAnchor(17, root)).to.equal(true);
    const anchor = await contract.anchors(17);
    expect(anchor.merkleRoot).to.equal(root);
    expect(anchor.metadataCommitment).to.equal(metadata);
  });

  it("rejects non-authority callers", async function () {
    const { contract, outsider } = await deploy();
    const root = ethers.keccak256(ethers.toUtf8Bytes("root"));
    await expectRevert(contract.connect(outsider).anchorMerkleRoot(root, 1, ethers.ZeroHash), "UNAUTHORIZED");
  });

  it("rejects duplicate batches and zero roots", async function () {
    const { contract } = await deploy();
    const root = ethers.keccak256(ethers.toUtf8Bytes("root"));
    const metadata = ethers.keccak256(ethers.toUtf8Bytes("metadata"));
    await expectRevert(contract.anchorMerkleRoot(ethers.ZeroHash, 1, ethers.ZeroHash), "ZERO_ROOT");
    await expectRevert(contract.anchorMerkleRoot(root, 1, ethers.ZeroHash), "ZERO_METADATA_COMMITMENT");
    await contract.anchorMerkleRoot(root, 1, metadata);
    await expectRevert(contract.anchorMerkleRoot(root, 1, metadata), "BATCH_EXISTS");
  });

  it("does not verify an absent batch against the zero root", async function () {
    const { contract } = await deploy();
    expect(await contract.verifyAnchor(404, ethers.ZeroHash)).to.equal(false);
  });

  it("rejects a zero deployment authority", async function () {
    const factory = await ethers.getContractFactory("CaseIntegrityAnchor");
    await expectRevert(factory.deploy(ethers.ZeroAddress), "ZERO_AUTHORITY");
  });
});
