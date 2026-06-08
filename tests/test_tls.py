"""TLS trust configuration tests."""

from __future__ import annotations

import ssl

from alberta_assisted_living.tls import verify_setting


def test_verify_setting_uses_explicit_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "ca.crt"
    bundle.write_text("dummy")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(bundle))
    assert verify_setting() == str(bundle)


def test_verify_setting_falls_back_to_context(monkeypatch):
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    setting = verify_setting()
    assert isinstance(setting, ssl.SSLContext)


def test_verify_setting_never_disables_verification(monkeypatch):
    """We only ever broaden trust, never turn verification off."""
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    ctx = verify_setting()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
