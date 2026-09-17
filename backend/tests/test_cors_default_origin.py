from otimizer_api.main import _cors_origins


def test_default_cors_allows_localhost_and_loopback_frontend() -> None:
    origins = _cors_origins()

    assert "http://localhost:8080" in origins
    assert "http://127.0.0.1:8080" in origins


def test_default_cors_allows_android_webview_asset_origin() -> None:
    origins = _cors_origins()

    assert "https://appassets.androidplatform.net" in origins
