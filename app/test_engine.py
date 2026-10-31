import json
from pathlib import Path
import engine as e

REF = json.loads((Path(__file__).resolve().parent.parent / "data" / "reference_answers.json").read_text())
D = e.load(); L = e.line_margin(D); S = e.sku_profit(L); T, _ = e.inventory(D)


def test_store_cm():
    assert abs(S.cm.sum() / S.net.sum() - REF["store_cm_pct_before_ads"]) < 0.001


def test_margin_killers():
    for sku, ref in REF["bottom_skus_by_cm_pct"].items():
        assert abs(S.loc[sku, "cm_pct"] - ref["cm_pct"]) < 0.002
        assert abs(S.loc[sku, "return_rate_units"] - ref["return_rate_units"]) < 0.002
    k, _ = e.margin_killers(S)
    assert {"DRK-POUR", "BND-GIFT"} <= set(k.index)


def test_stockouts():
    assert set(T[T.at_risk].index) == set(REF["stockout_skus"])
    for sku, ref in REF["stockout_skus"].items():
        assert abs(T.loc[sku, "days_of_stock"] - ref["days_of_stock"]) < 0.1
        assert T.loc[sku, "days_to_next_po"] == ref["days_to_next_po"]


def test_slow_movers():
    assert set(REF["slow_movers"]) <= set(T[T.slow_mover].index)
