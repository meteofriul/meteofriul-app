import unittest

from tools.set_webcam_admin_claim import build_webcam_admin_claims


class WebcamAdminClaimToolTests(unittest.TestCase):
    def test_enable_preserves_unrelated_claims(self):
        self.assertEqual(
            build_webcam_admin_claims(
                {"adsAdmin": True, "moderator": True},
                enabled=True,
            ),
            {
                "adsAdmin": True,
                "moderator": True,
                "webcamAdmin": True,
            },
        )

    def test_disable_removes_only_webcam_admin(self):
        self.assertEqual(
            build_webcam_admin_claims(
                {
                    "adsAdmin": True,
                    "moderator": True,
                    "webcamAdmin": True,
                },
                enabled=False,
            ),
            {"adsAdmin": True, "moderator": True},
        )


if __name__ == "__main__":
    unittest.main()
