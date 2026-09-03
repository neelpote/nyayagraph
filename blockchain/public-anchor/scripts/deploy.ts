import { network } from "hardhat";

async function main() {
  const { ethers, networkName } = await network.create();
  const [deployer] = await ethers.getSigners();
  if (!deployer) throw new Error("No deployment signer configured");

  const developmentNetwork = networkName === "hardhat" || networkName === "localhost";
  const configuredAuthority = process.env.PUBLIC_ANCHOR_AUTHORITY;
  if (!developmentNetwork && !configuredAuthority) {
    throw new Error("PUBLIC_ANCHOR_AUTHORITY is required outside local development");
  }
  if (!developmentNetwork && !process.env.PUBLIC_RPC_URL) {
    throw new Error("PUBLIC_RPC_URL is required outside local development");
  }
  if (configuredAuthority && !ethers.isAddress(configuredAuthority)) {
    throw new Error("PUBLIC_ANCHOR_AUTHORITY must be a valid EVM address");
  }
  const authority = ethers.getAddress(configuredAuthority ?? deployer.address);
  const providerNetwork = await ethers.provider.getNetwork();
  const expectedChainId = networkName === "polygonAmoy" ? 80002n : networkName === "localhost" ? 31337n : undefined;
  if (expectedChainId !== undefined && providerNetwork.chainId !== expectedChainId) {
    throw new Error(`Connected chain ID ${providerNetwork.chainId} does not match ${networkName} (${expectedChainId})`);
  }
  const factory = await ethers.getContractFactory("CaseIntegrityAnchor");
  const contract = await factory.deploy(authority);
  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();
  if ((await contract.authority()) !== authority || (await ethers.provider.getCode(contractAddress)) === "0x") {
    throw new Error("Deployment verification failed");
  }

  const deployment = {
    network: networkName,
    environment: developmentNetwork ? "LOCAL_DEVELOPMENT" : "PUBLIC_TESTNET",
    deploymentStatus: "CONFIRMED",
    chainId: providerNetwork.chainId.toString(),
    contractAddress,
    authority,
    deployer: deployer.address,
  };
  console.log(JSON.stringify(deployment, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
