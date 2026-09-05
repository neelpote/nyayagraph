# NyayaGraph Fabric provenance ledger

This directory contains minimal Go chaincode for provenance fingerprints. It never stores evidence files, case numbers, names, identities, storage locations, or document text.

## Operations

`RegisterCase`, `RegisterDocument`, `RegisterEvidence`, `CreateVersion`, `TransferCustody`, `GrantAccess`, `RevokeAccess`, `RecordAccess`, `RecordCheckpoint`, and `VerifyArtifact` are implemented in `chaincode/main.go`.

## Development network

Install the official Hyperledger Fabric 2.5 samples and binaries, then run from the repository root:

```bash
export FABRIC_SAMPLES_DIR=/absolute/path/to/fabric-samples
./blockchain/fabric/scripts/fabric-up.sh
./blockchain/fabric/scripts/fabric-deploy-chaincode.sh
```

The scripts intentionally reuse the stable official two-organization `test-network` for local adapter development. The target deployment has `PoliceMSP`, `FSLMSP`, `ProsecutionMSP`, and `CourtMSP` on one `justicechannel`; these scripts do not falsely present the local two-organization topology as that production target.

`fabric-up.sh` temporarily backs up the sample files it changes. `fabric-down.sh` restores those files after stopping the network, and a failed startup restores changes automatically. The deploy script reports success only after Fabric confirms that `nyayagraph` is committed on the channel.

To let FastAPI invoke the network, mount the Fabric `peer` binary and identity material, export the appropriate `CORE_PEER_*` variables, and set:

```ini
FABRIC_ENABLED=true
FABRIC_CHANNEL=justicechannel
FABRIC_CHAINCODE=nyayagraph
FABRIC_PEER_BINARY=peer
FABRIC_MSP_ID=PoliceMSP
FABRIC_ORDERER_ADDRESS=localhost:7050
FABRIC_ORDERER_TLS_CA=/absolute/path/to/orderer-ca.crt
```

If invocation fails, the backend creates an explicitly labelled `DATABASE_DEV` audit record with `synchronization_pending=true`; it never manufactures a Fabric transaction ID.

Chaincode authorizes each operation from the certificate MSP, ignores caller-supplied organization labels for provenance, validates 32-byte hexadecimal commitments, and hashes composite event payloads before storage. Custody transfers require an existing evidence artifact. These checks can reject payloads accepted by earlier development versions; redeploy the chaincode and retry pending records with valid commitments.

Stop the network with:

```bash
./blockchain/fabric/scripts/fabric-down.sh
```
