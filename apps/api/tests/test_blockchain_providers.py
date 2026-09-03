from types import SimpleNamespace

import pytest

from app.blockchain.ledger import DatabaseDevLedger, FabricPeerConfig, FabricProvenanceLedger, LedgerUnavailableError, ResilientProvenanceLedger
from app.models import OutboxEvent
from app.blockchain.public_anchor import (
    ANCHOR_SELECTOR,
    AnchorUnavailableError,
    EvmAnchorConfig,
    JsonRpcEvmAnchorProvider,
    LocalDevAnchorProvider,
    PendingAnchorProvider,
    UnavailableAnchorProvider,
)


ROOT = "11" * 32
METADATA = "22" * 32
CONTRACT = "0x" + "33" * 20
TX_HASH = "0x" + "44" * 32


def test_local_anchor_is_bound_to_the_supplied_root():
    provider = LocalDevAnchorProvider()
    result = provider.anchor_root(root=ROOT, batch_number=7, metadata_commitment=METADATA)
    assert result["status"] == "VERIFIED_LOCAL"
    assert provider.verify_root(root=ROOT, transaction_hash=result["transaction_hash"])
    assert not provider.verify_root(root="55" * 32, transaction_hash=result["transaction_hash"])


def test_hardhat_provider_encodes_and_confirms_contract_call():
    calls = []

    def transport(method, params):
        calls.append((method, params))
        if method == "eth_accounts":
            return ["0x" + "66" * 20]
        if method == "eth_sendTransaction":
            return TX_HASH
        if method == "eth_getTransactionReceipt":
            return {"status": "0x1", "blockNumber": "0xa"}
        if method == "eth_getTransactionByHash":
            return {"to": CONTRACT, "input": "0x" + ANCHOR_SELECTOR + ROOT + f"{7:064x}" + METADATA}
        raise AssertionError(method)

    provider = JsonRpcEvmAnchorProvider(EvmAnchorConfig("http://rpc", CONTRACT, "31337", "LOCAL_EVM"), transport)
    result = provider.anchor_root(root=ROOT, batch_number=7, metadata_commitment=METADATA)
    assert result["status"] == "VERIFIED_PUBLIC"
    assert result["block_number"] == 10
    sent = next(params for method, params in calls if method == "eth_sendTransaction")[0]
    assert sent["data"] == "0x" + ANCHOR_SELECTOR + ROOT + f"{7:064x}" + METADATA
    assert provider.verify_root(root=ROOT, transaction_hash=TX_HASH)


def test_evm_provider_rejects_non_http_rpc_schemes():
    with pytest.raises(AnchorUnavailableError):
        JsonRpcEvmAnchorProvider(EvmAnchorConfig("file:///tmp/rpc", CONTRACT, "31337", "LOCAL_EVM"))


def test_pending_provider_never_claims_external_verification():
    provider = PendingAnchorProvider(UnavailableAnchorProvider("offline"), chain_type="POLYGON_AMOY",
                                     chain_id="80002", contract_address=CONTRACT)
    result = provider.anchor_root(root=ROOT, batch_number=7, metadata_commitment=METADATA)
    assert result["status"] == "PENDING_EXTERNAL"
    assert result["transaction_hash"].startswith("pending-anchor-")
    assert not provider.verify_root(root=ROOT, transaction_hash=result["transaction_hash"])


def test_fabric_adapter_uses_hashes_and_commitments(monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="txid [abcdef0123456789]")

    monkeypatch.setattr("app.blockchain.ledger.subprocess.run", run)
    config = FabricPeerConfig("peer", "justicechannel", "nyayagraph", None, None)
    ledger = FabricProvenanceLedger(config)
    tx_id = ledger.register_document(None, document_version_id="version-1", case_id="SECRET-CASE",
                                     hash_value=ROOT, actor_id="user-1")
    assert tx_id == "abcdef0123456789"
    invocation = captured["command"][captured["command"].index("-c") + 1]
    assert "SECRET-CASE" not in invocation
    assert ROOT in invocation


def test_fabric_adapter_requests_endorsements_from_configured_peers(monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="txid [abcdef0123456789]")

    monkeypatch.setattr("app.blockchain.ledger.subprocess.run", run)
    config = FabricPeerConfig("peer", "justicechannel", "nyayagraph", "orderer:7050", "orderer-ca.pem",
                              ("police-peer:7051", "fsl-peer:9051"), ("police-ca.pem", "fsl-ca.pem"))
    FabricProvenanceLedger(config).register_document(
        None, document_version_id="version-1", case_id="case-1", hash_value=ROOT, actor_id="user-1"
    )
    assert captured["command"][-8:] == [
        "--peerAddresses", "police-peer:7051", "--tlsRootCertFiles", "police-ca.pem",
        "--peerAddresses", "fsl-peer:9051", "--tlsRootCertFiles", "fsl-ca.pem",
    ]


def test_fabric_adapter_does_not_fabricate_transaction_id(monkeypatch):
    monkeypatch.setattr("app.blockchain.ledger.subprocess.run",
                        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="peer unavailable"))
    ledger = FabricProvenanceLedger(FabricPeerConfig("peer", "justicechannel", "nyayagraph", None, None))
    with pytest.raises(LedgerUnavailableError):
        ledger.register_document(None, document_version_id="version-1", case_id="case-1",
                                 hash_value=ROOT, actor_id="user-1")


def test_database_dev_ledger_marks_pending_sync():
    added = []
    db = SimpleNamespace(add=added.append)
    ledger = DatabaseDevLedger()
    tx_id = ledger.register_document(db, document_version_id="version-1", case_id="case-1",
                                     hash_value=ROOT, actor_id="user-1", synchronization_pending=True)
    assert tx_id.startswith("dev-ledger-")
    assert added[0].metadata_json["synchronization_pending"] is True


def test_failed_fabric_write_creates_durable_retry_record():
    class OfflineLedger:
        def register_document(self, db, **kwargs):
            raise LedgerUnavailableError("offline")

    added = []
    db = SimpleNamespace(add=added.append)
    ledger = ResilientProvenanceLedger(OfflineLedger(), DatabaseDevLedger())
    result = ledger.register_document(
        db, document_version_id="version-1", case_id="case-1",
        hash_value=ROOT, actor_id="user-1",
    )
    assert result.startswith("dev-ledger-")
    queued = next(item for item in added if isinstance(item, OutboxEvent))
    assert queued.topic == "fabric.register_document"
    assert queued.payload_json["document_version_id"] == "version-1"
