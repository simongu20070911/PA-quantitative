from __future__ import annotations

import unittest

import numpy as np

from pa_core.features.ema import (
    EMA_ALIGNMENT,
    EMA_FEATURE_KEY,
    compute_ema_values,
    build_ema_feature_spec,
    ema_warmup_bars,
    normalize_ema_lengths,
)


class EmaFeatureTests(unittest.TestCase):
    def test_compute_ema_values_matches_reference_recursion(self) -> None:
        close = np.array([10.0, 11.0, 13.0, 12.0], dtype=np.float64)

        values = compute_ema_values(close, length=3)

        np.testing.assert_allclose(
            values,
            np.array([10.0, 10.5, 11.75, 11.875], dtype=np.float64),
        )

    def test_normalize_ema_lengths_rejects_non_positive_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integers"):
            normalize_ema_lengths([8, 0, 21])

    def test_normalize_ema_lengths_deduplicates_while_preserving_order(self) -> None:
        self.assertEqual(normalize_ema_lengths([9, 20, 9, 50]), (9, 20, 50))

    def test_build_ema_feature_spec_uses_bar_alignment(self) -> None:
        spec = build_ema_feature_spec(data_version="es_test_v1", length=21)

        self.assertEqual(spec.feature_key, EMA_FEATURE_KEY)
        self.assertEqual(spec.alignment, EMA_ALIGNMENT)
        self.assertEqual(spec.input_ref, "es_test_v1")

    def test_ema_warmup_bars_scales_with_longest_length(self) -> None:
        self.assertEqual(ema_warmup_bars([9, 20, 50]), 250)


if __name__ == "__main__":
    unittest.main()
