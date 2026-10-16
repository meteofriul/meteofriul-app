import unittest

from tools.set_ads_admin_claim import build_ads_admin_claims


class AdsAdminClaimToolTests(unittest.TestCase):
    def test_enable_preserves_unrelated_claims(self):
        self.assertEqual(
            build_ads_admin_claims({"moderator": True}, enabled=True),
            {"adsAdmin": True, "moderator": True},
        )

    def test_disable_removes_only_ads_admin(self):
        self.assertEqual(
            build_ads_admin_claims(
                {"adsAdmin": True, "moderator": True},
                enabled=False,
            ),
            {"moderator": True},
        )


if __name__ == "__main__":
    unittest.main()
