from __future__ import annotations

import hashlib
import json
import os
import re
# The signer CLI is an explicit provider boundary and is always invoked without a shell.
import subprocess  # nosec B404
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ..config import get_settings


ANCHOR_SELECTOR = "92c2959a"  # keccak256(anchorMerkleRoot(bytes32,uint256,bytes32))[0:4]


class AnchorUnavailableError(RuntimeError):
    """Raised when a configured external anchor cannot accept or verify a root."""


class PublicAnchorProvider(Protocol):
    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict: ...
    def verify_root(self, *, root: str, transaction_hash: str) -> bool: ...


def _bytes32(value: str, field: str) -> str:
    normalized = value.removeprefix("0x").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ValueError(f"{field} must be a 32-byte hexadecimal value")
    return normalized


class LocalDevAnchorProvider:
    """Deterministic local checkpoint; never represented as a public transaction."""

    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict:
        root = _bytes32(root, "root")
        metadata_commitment = _bytes32(metadata_commitment, "metadata_commitment")
        payload = f"{root}:{batch_number}:{metadata_commitment}".encode()
        return {"transaction_hash": f"local-anchor-{root}-{hashlib.sha256(payload).hexdigest()[:16]}",
                "chain_type": "LOCAL_DEV", "chain_id": "nyayagraph-local", "contract_address": None,
                "block_number": None, "status": "VERIFIED_LOCAL"}

    def verify_root(self, *, root: str, transaction_hash: str) -> bool:
        try:
            root = _bytes32(root, "root")
        except ValueError:
            return False
        return transaction_hash.startswith(f"local-anchor-{root}-")


@dataclass(frozen=True)
class EvmAnchorConfig:
    rpc_url: str
    contract_address: str
    chain_id: str
    chain_type: str
    sender_address: str | None = None
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls, *, chain_type: str, default_chain_id: str) -> "EvmAnchorConfig":
        return cls(rpc_url=os.getenv("PUBLIC_RPC_URL", "http://127.0.0.1:8545"),
                   contract_address=os.getenv("PUBLIC_ANCHOR_CONTRACT", ""),
                   chain_id=os.getenv("PUBLIC_CHAIN_ID", default_chain_id), chain_type=chain_type,
                   sender_address=os.getenv("PUBLIC_ANCHOR_AUTHORITY"))


class JsonRpcEvmAnchorProvider:
    """EVM adapter for a local node with an unlocked authority account."""

    def __init__(self, config: EvmAnchorConfig,
                 transport: Callable[[str, list[Any]], Any] | None = None) -> None:
        self.config = config
        self.transport = transport or self._rpc
        parsed_rpc = urlparse(config.rpc_url)
        if parsed_rpc.scheme not in {"http", "https"} or not parsed_rpc.hostname:
            raise AnchorUnavailableError("PUBLIC_RPC_URL must be an HTTP(S) endpoint")
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", config.contract_address):
            raise AnchorUnavailableError("PUBLIC_ANCHOR_CONTRACT is not configured")

    def _rpc(self, method: str, params: list[Any]) -> Any:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = urllib.request.Request(self.config.rpc_url, data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            # Constructor validation restricts this request to HTTP(S) RPC endpoints.
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:  # nosec B310
                result = json.loads(response.read())
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AnchorUnavailableError(f"Public-chain RPC unavailable: {exc}") from exc
        if result.get("error"):
            raise AnchorUnavailableError(f"Public-chain RPC error: {result['error'].get('message', 'unknown error')}")
        return result.get("result")

    @staticmethod
    def _calldata(root: str, batch_number: int, metadata_commitment: str) -> str:
        if batch_number < 0:
            raise ValueError("batch_number must be non-negative")
        return "0x" + ANCHOR_SELECTOR + _bytes32(root, "root") + f"{batch_number:064x}" + _bytes32(metadata_commitment, "metadata_commitment")

    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict:
        sender = self.config.sender_address
        if not sender:
            accounts = self.transport("eth_accounts", []) or []
            sender = accounts[0] if accounts else None
        if not sender:
            raise AnchorUnavailableError("No unlocked EVM authority account is available")
        tx_hash = self.transport("eth_sendTransaction", [{"from": sender, "to": self.config.contract_address,
                                                            "data": self._calldata(root, batch_number, metadata_commitment)}])
        if not isinstance(tx_hash, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
            raise AnchorUnavailableError("EVM node did not return a transaction hash")
        receipt = None
        for _ in range(10):
            receipt = self.transport("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                break
            time.sleep(0.2)
        if receipt and int(receipt.get("status", "0x0"), 16) != 1:
            raise AnchorUnavailableError("Public anchor transaction reverted")
        return {"transaction_hash": tx_hash, "chain_type": self.config.chain_type,
                "chain_id": self.config.chain_id, "contract_address": self.config.contract_address,
                "block_number": int(receipt["blockNumber"], 16) if receipt and receipt.get("blockNumber") else None,
                "status": "VERIFIED_PUBLIC" if receipt else "SUBMITTED"}

    def verify_root(self, *, root: str, transaction_hash: str) -> bool:
        try:
            root = _bytes32(root, "root")
            transaction = self.transport("eth_getTransactionByHash", [transaction_hash])
            receipt = self.transport("eth_getTransactionReceipt", [transaction_hash])
        except (ValueError, AnchorUnavailableError):
            return False
        if not transaction or not receipt or int(receipt.get("status", "0x0"), 16) != 1:
            return False
        target = str(transaction.get("to", "")).lower()
        data = str(transaction.get("input", "")).lower().removeprefix("0x")
        return target == self.config.contract_address.lower() and data.startswith(ANCHOR_SELECTOR + root)


class PolygonAmoyAnchorProvider:
    """Polygon Amoy writer using Foundry `cast` for local private-key signing."""

    def __init__(self, config: EvmAnchorConfig | None = None) -> None:
        self.config = config or EvmAnchorConfig.from_environment(chain_type="POLYGON_AMOY", default_chain_id="80002")
        self.verifier = JsonRpcEvmAnchorProvider(self.config)

    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict:
        root = _bytes32(root, "root")
        metadata_commitment = _bytes32(metadata_commitment, "metadata_commitment")
        private_key = os.getenv("PUBLIC_ANCHOR_PRIVATE_KEY")
        if not private_key:
            raise AnchorUnavailableError("PUBLIC_ANCHOR_PRIVATE_KEY is required for Polygon Amoy")
        environment = {**os.environ, "ETH_PRIVATE_KEY": private_key}
        command = [os.getenv("CAST_BINARY", "cast"), "send", "--rpc-url", self.config.rpc_url,
                   self.config.contract_address, "anchorMerkleRoot(bytes32,uint256,bytes32)",
                   "0x" + root, str(batch_number), "0x" + metadata_commitment, "--json"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False, env=environment)  # nosec B603
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AnchorUnavailableError(f"Polygon signer unavailable: {exc}") from exc
        if result.returncode != 0:
            raise AnchorUnavailableError(f"Polygon anchor failed: {(result.stderr or result.stdout).strip()[-500:]}")
        try:
            receipt = json.loads(result.stdout)
            tx_hash = receipt["transactionHash"]
            block_number = int(receipt["blockNumber"], 16) if isinstance(receipt.get("blockNumber"), str) else receipt.get("blockNumber")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AnchorUnavailableError("Polygon signer returned an invalid receipt") from exc
        return {"transaction_hash": tx_hash, "chain_type": self.config.chain_type,
                "chain_id": self.config.chain_id, "contract_address": self.config.contract_address,
                "block_number": block_number, "status": "VERIFIED_PUBLIC"}

    def verify_root(self, *, root: str, transaction_hash: str) -> bool:
        return self.verifier.verify_root(root=root, transaction_hash=transaction_hash)


class PendingAnchorProvider:
    """Preserves a checkpoint while honestly marking an unavailable external anchor."""

    def __init__(self, primary: PublicAnchorProvider, *, chain_type: str, chain_id: str,
                 contract_address: str | None) -> None:
        self.primary = primary
        self.chain_type = chain_type
        self.chain_id = chain_id
        self.contract_address = contract_address

    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict:
        try:
            return self.primary.anchor_root(root=root, batch_number=batch_number, metadata_commitment=metadata_commitment)
        except AnchorUnavailableError:
            commitment = hashlib.sha256(f"{root}:{batch_number}:{metadata_commitment}".encode()).hexdigest()
            return {"transaction_hash": "pending-anchor-" + commitment, "chain_type": self.chain_type,
                    "chain_id": self.chain_id, "contract_address": self.contract_address,
                    "block_number": None, "status": "PENDING_EXTERNAL"}

    def verify_root(self, *, root: str, transaction_hash: str) -> bool:
        if transaction_hash.startswith("pending-anchor-"):
            return False
        return self.primary.verify_root(root=root, transaction_hash=transaction_hash)


class UnavailableAnchorProvider:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def anchor_root(self, *, root: str, batch_number: int, metadata_commitment: str) -> dict:
        raise AnchorUnavailableError(self.reason)

    def verify_root(self, *, root: str, transaction_hash: str) -> bool:
        return False


def get_public_anchor_provider() -> PublicAnchorProvider:
    mode = get_settings().public_chain_mode.lower()
    if mode in {"local", "mock", "disabled"}:
        return LocalDevAnchorProvider()
    if mode in {"hardhat", "anvil"}:
        config = EvmAnchorConfig.from_environment(chain_type="LOCAL_EVM", default_chain_id="31337")
        try:
            primary: PublicAnchorProvider = JsonRpcEvmAnchorProvider(config)
        except AnchorUnavailableError as exc:
            primary = UnavailableAnchorProvider(str(exc))
        return PendingAnchorProvider(primary, chain_type=config.chain_type, chain_id=config.chain_id,
                                     contract_address=config.contract_address)
    if mode == "polygon_amoy":
        config = EvmAnchorConfig.from_environment(chain_type="POLYGON_AMOY", default_chain_id="80002")
        try:
            polygon: PublicAnchorProvider = PolygonAmoyAnchorProvider(config)
        except AnchorUnavailableError as exc:
            polygon = UnavailableAnchorProvider(str(exc))
        return PendingAnchorProvider(polygon, chain_type=config.chain_type, chain_id=config.chain_id,
                                     contract_address=config.contract_address)
    raise ValueError(f"Unsupported PUBLIC_CHAIN_MODE: {mode}")
