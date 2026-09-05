from starlette.requests import Request

from app.security.request_guard import RequestGuard


def test_ai_rate_limit_rejects_request_after_per_user_budget():
    guard = RequestGuard()
    scope = {
        "type": "http", "method": "POST", "path": "/api/v1/ai/case/demo/ask",
        "headers": [(b"authorization", b"Bearer isolated-test-token")],
        "client": ("127.0.0.1", 50000), "scheme": "http", "server": ("test", 80),
        "query_string": b"",
    }
    request = Request(scope)
    assert all(guard.allow(request) for _ in range(30))
    assert guard.allow(request) is False


def test_rotating_untrusted_authorization_header_does_not_reset_ip_budget():
    guard = RequestGuard()
    for index in range(30):
        scope = {
            "type": "http", "method": "POST", "path": "/api/v1/ai/case/demo/ask",
            "headers": [(b"authorization", f"Bearer bogus-{index}".encode())],
            "client": ("127.0.0.1", 50000), "scheme": "http", "server": ("test", 80),
            "query_string": b"",
        }
        assert guard.allow(Request(scope))
    assert guard.allow(Request(scope)) is False
