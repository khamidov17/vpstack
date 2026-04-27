"""Unit tests for vp_get_component_info."""


def test_known_component_returns_info():
    from vpstack_mcp.tools.get_component_info import handle
    r = handle("hubert")
    assert r["ok"] is True
    assert "tradeoffs" in r["result"]
    assert r["result"]["license"] == "Apache 2.0 (facebook/hubert-base-ls960)"


def test_unknown_component_lists_known():
    from vpstack_mcp.tools.get_component_info import handle
    r = handle("nonexistent-component-xyz")
    assert r["ok"] is False
    assert r["error"]["code"] == "UNKNOWN_COMPONENT"
    # Hint should list known components so the user can recover
    assert "hubert" in r["error"]["hint"]


def test_case_insensitive_lookup():
    from vpstack_mcp.tools.get_component_info import handle
    assert handle("HuBERT")["ok"] is True
    assert handle("Hubert")["ok"] is True
    assert handle("hifi-gan")["ok"] is True
    assert handle("hifi_gan")["ok"] is True  # underscore normalization
