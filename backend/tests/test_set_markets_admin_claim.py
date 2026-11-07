import unittest

from tools.set_markets_admin_claim import build_markets_admin_claims


class MarketsClaimTests(unittest.TestCase):
    def test_enable_and_disable_preserve_other_panel_permissions(self):
        original = {"adsAdmin": True, "webcamAdmin": True, "other": "keep"}
        enabled = build_markets_admin_claims(original, enabled=True)
        self.assertEqual(original, {"adsAdmin": True, "webcamAdmin": True, "other": "keep"})
        self.assertEqual(enabled, {**original, "marketsAdmin": True})
        self.assertEqual(build_markets_admin_claims(enabled, enabled=False), original)


if __name__ == "__main__":
    unittest.main()
