# Public Merkle anchor

The contract stores only `merkleRoot`, numeric `batchId`, `metadataCommitment`, and the block timestamp. Do not place case numbers, FIR numbers, people, CIDs, storage paths, or evidence metadata in these values.

```bash
cd blockchain/public-anchor
npm install
npm test
npm run node
```

Use an active Node.js LTS release (Node 20 or 22). Hardhat may warn or behave unexpectedly on non-LTS releases.

In another terminal:

```bash
cd blockchain/public-anchor
npm run deploy:local
```

Copy the emitted contract address into `PUBLIC_ANCHOR_CONTRACT`, set `PUBLIC_CHAIN_MODE=hardhat`, and keep `PUBLIC_RPC_URL=http://127.0.0.1:8545`. The backend sends transactions from an unlocked local Hardhat account.

The deployment output labels this environment `LOCAL_DEVELOPMENT`; it is not proof of a public-chain deployment. Deployment completes only after the bytecode and configured authority are read back from the connected chain.

For Polygon Amoy, fund a dedicated testnet-only signer, set `PUBLIC_CHAIN_MODE=polygon_amoy`, `PUBLIC_RPC_URL`, `PUBLIC_ANCHOR_PRIVATE_KEY`, and `PUBLIC_ANCHOR_AUTHORITY`, then run `npm run deploy:amoy`. The deployment refuses a missing RPC or authority, validates chain ID `80002`, and prints `PUBLIC_TESTNET` rather than implying mainnet production. Copy the confirmed address into `PUBLIC_ANCHOR_CONTRACT`; do not reuse an address from another chain. Install Foundry's `cast` command for backend transaction signing. The FastAPI provider does not claim an anchor unless the RPC returns a real successful transaction receipt.

The contract rejects zero roots and metadata commitments, duplicate batch IDs, and unauthorized callers. Verification returns false for batches that were never anchored, including a zero-root query.
