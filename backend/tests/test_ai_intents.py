import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.ai import (
    infer_campaign_channel,
    mentions_high_value_audience,
    wants_campaign_creation,
    wants_campaign_launch,
)


class AIIntentTests(unittest.TestCase):
    def test_detects_high_value_whatsapp_campaign_creation(self):
        message = "Create a WhatsApp campaign for high-value customers"

        self.assertTrue(wants_campaign_creation(message))
        self.assertTrue(mentions_high_value_audience(message))
        self.assertEqual(infer_campaign_channel(message), "whatsapp")

    def test_detects_create_and_launch_high_value_campaign(self):
        message = "Create and launch a campaign for customers who spent over 5000"

        self.assertTrue(wants_campaign_creation(message))
        self.assertTrue(wants_campaign_launch(message))
        self.assertTrue(mentions_high_value_audience(message))

    def test_non_campaign_segment_preview_does_not_match_campaign_creation(self):
        message = "Show customers who spent more than 5000"

        self.assertFalse(wants_campaign_creation(message))
        self.assertTrue(mentions_high_value_audience(message))


if __name__ == "__main__":
    unittest.main()
