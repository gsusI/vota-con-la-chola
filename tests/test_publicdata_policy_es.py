from __future__ import annotations

import unittest

from etl.politicos_es import government_org as vota_government_org
from etl.politicos_es import indicator_backfill as vota_indicator_backfill
from etl.politicos_es import policy_events as vota_policy_events
from publicdata_policy_es import government_org, indicator_backfill, policy_events


class TestPublicdataPolicyEs(unittest.TestCase):
    def test_vota_wrappers_reexport_policy_modules(self) -> None:
        self.assertIs(vota_policy_events.backfill_boe_policy_events, policy_events.backfill_boe_policy_events)
        self.assertIs(vota_policy_events.backfill_moncloa_policy_events, policy_events.backfill_moncloa_policy_events)
        self.assertIs(vota_policy_events.backfill_money_policy_events, policy_events.backfill_money_policy_events)
        self.assertIs(vota_government_org.backfill_government_org_units, government_org.backfill_government_org_units)
        self.assertIs(
            vota_indicator_backfill.backfill_indicator_harmonization,
            indicator_backfill.backfill_indicator_harmonization,
        )


if __name__ == "__main__":
    unittest.main()
