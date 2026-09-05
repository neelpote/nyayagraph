import "dotenv/config";
import { defineConfig } from "hardhat/config";
import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";

const amoyPrivateKey = process.env.PUBLIC_ANCHOR_PRIVATE_KEY;
if (amoyPrivateKey && !/^0x[0-9a-fA-F]{64}$/.test(amoyPrivateKey)) {
  throw new Error("PUBLIC_ANCHOR_PRIVATE_KEY must be a 0x-prefixed 32-byte hexadecimal key");
}

export default defineConfig({
  plugins: [hardhatEthers, hardhatMocha],
  solidity: {
    version: "0.8.24",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    hardhat: { type: "edr-simulated", chainId: 31337 },
    localhost: {
      type: "http",
      url: process.env.PUBLIC_RPC_URL ?? "http://127.0.0.1:8545",
      chainId: 31337,
    },
    polygonAmoy: {
      type: "http",
      url: process.env.PUBLIC_RPC_URL ?? "https://rpc-amoy.polygon.technology",
      chainId: 80002,
      accounts: amoyPrivateKey ? [amoyPrivateKey] : [],
    },
  },
});
