import stat

from app.config import Settings


def test_generated_development_jwt_key_survives_settings_recreation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = Settings(_env_file=None, dev_mode=True, jwt_secret="").jwt_signing_key()
    second = Settings(_env_file=None, dev_mode=True, jwt_secret="").jwt_signing_key()

    key_path = tmp_path / "data/keys/dev-jwt-secret.txt"
    assert first == second
    assert len(first) >= 32
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
