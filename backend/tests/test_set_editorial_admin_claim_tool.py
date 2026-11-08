from __future__ import annotations

from tools.set_editorial_admin_claim import build_editorial_admin_claims


def test_editorial_claim_preserves_other_existing_roles():
    original = {"adsAdmin": True, "webcamAdmin": True, "moderator": True}
    enabled = build_editorial_admin_claims(original, enabled=True)
    assert original == {"adsAdmin": True, "webcamAdmin": True, "moderator": True}
    assert enabled == {**original, "editorialAdmin": True}
    assert build_editorial_admin_claims(enabled, enabled=False) == original
