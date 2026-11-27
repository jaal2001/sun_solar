"""Test the pure calculation module without Home Assistant."""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "solar_calculation",
    Path(__file__).resolve().parents[1] / "custom_components/sun_solar/calculation.py",
)
calc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = calc
spec.loader.exec_module(calc)

NOW = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)


class TestCalculation(unittest.TestCase):
    def predict(self, **kwargs):
        params = dict(now=NOW, soc=80, rate=0.5,
                      sunset=NOW + timedelta(hours=3), daylight=True)
        params.update(kwargs)
        return calc.forecast(**params)

    def test_invalid_soc(self):
        for value in ("nan", "inf", "-1", "101", "unknown", None):
            self.assertIsNone(calc.valid_soc(value))
        self.assertEqual(calc.valid_soc("0"), 0)
        self.assertEqual(calc.valid_soc("100"), 100)

    def test_regression(self):
        self.assertAlmostEqual(calc.slope([(0, 50), (5, 55), (10, 60)]), 1)
        self.assertIsNone(calc.slope([(0, 50)]))

    def test_eta(self):
        self.assertEqual(self.predict().eta, NOW + timedelta(minutes=39))

    def test_night(self):
        self.assertEqual(self.predict(daylight=False).status, "not_charging")

    def test_sunset(self):
        self.assertEqual(self.predict(sunset=NOW + timedelta(minutes=10)).status,
                         "charging_past_sunset")

    def test_missing_sun(self):
        self.assertEqual(self.predict(sunset=None).status, "unavailable")

    def test_full_stable(self):
        earlier = NOW - timedelta(minutes=5)
        self.assertEqual(self.predict(soc=100, full_since=earlier).eta, earlier)

    def test_aggregate(self):
        first = self.predict()
        second = self.predict(soc=60)
        full = self.predict(soc=100)
        self.assertEqual(calc.aggregate([first, second]).eta, second.eta)
        self.assertEqual(calc.aggregate([full, second]).eta, second.eta)
        self.assertEqual(calc.aggregate([full, full]).status, "full")
        self.assertIsNone(calc.aggregate([first, self.predict(rate=0)]).eta)
        self.assertEqual(calc.aggregate([full, self.predict(soc=None)]).status,
                         "unavailable")
        self.assertEqual(calc.aggregate([]).status, "unavailable")
