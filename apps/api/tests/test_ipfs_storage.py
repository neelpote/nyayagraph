import httpx

from app.storage import providers


def test_ipfs_stores_and_retrieves_encrypted_bytes(monkeypatch):
    encrypted = b"ciphertext-only"
    cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3ddy65pjyq76z36sohm2j3aaa"
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, request.url.params))
        if request.url.path.endswith("/add"):
            assert encrypted in request.read()
            return httpx.Response(200, json={"Hash": cid})
        if request.url.path.endswith("/cat"):
            return httpx.Response(200, content=encrypted)
        return httpx.Response(200, json={"Pins": [cid]})

    monkeypatch.setattr(providers, "get_settings", lambda: type("Settings", (), {
        "ipfs_enabled": True, "ipfs_api_url": "http://ipfs:5001",
    })())
    client = httpx.Client(transport=httpx.MockTransport(handler))
    storage = providers.IPFSStorageProvider(client=client)

    reference = storage.store("case/document/v1.bin", encrypted, "application/octet-stream")
    assert reference == f"ipfs://{cid}"
    assert storage.retrieve(reference) == encrypted
    storage.delete(reference)
    assert [path for path, _ in calls] == ["/api/v0/add", "/api/v0/cat", "/api/v0/pin/rm"]


def test_ipfs_rejects_invalid_cid(monkeypatch):
    monkeypatch.setattr(providers, "get_settings", lambda: type("Settings", (), {
        "ipfs_enabled": True, "ipfs_api_url": "http://ipfs:5001",
    })())
    storage = providers.IPFSStorageProvider(client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))))
    try:
        storage.retrieve("ipfs://../../secret")
    except ValueError as error:
        assert "Invalid IPFS" in str(error)
    else:
        raise AssertionError("Invalid CID was accepted")
