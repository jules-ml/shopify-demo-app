"""Calculation engine for the Shopify True Profit & Stock-Out demo (SYNTHETIC Saltline data).
Formulas follow ../SPEC.md and match ../sanity_check.py / data/reference_answers.json."""
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def load(data_dir=DATA):
    d = Path(data_dir)
    return {
        "orders": pd.read_csv(d / "orders.csv", dtype=str, keep_default_na=False),
        "products": pd.read_csv(d / "products.csv", dtype=str, keep_default_na=False),
        "inventory": pd.read_csv(d / "inventory.csv"),
        "history": pd.read_csv(d / "inventory_history.csv", parse_dates=["Date"]),
        "refunds": pd.read_csv(d / "refunds.csv", dtype={"Name": str}),
        "labels": pd.read_csv(d / "shipping_labels.csv"),
        "fees": pd.read_csv(d / "fees.csv"),
        "ads": pd.read_csv(d / "ad_spend.csv", parse_dates=["Date"]),
        "lead_times": pd.read_csv(d / "supplier_lead_times.csv"),
        "pos": pd.read_csv(d / "purchase_orders.csv", parse_dates=["Expected Arrival"]),
    }


def _products(p):
    # accept current and legacy Shopify product headers
    p = p.rename(columns={"Variant SKU": "SKU", "Variant Price": "Price", "Variant Grams": "Weight value (grams)",
                          "Variant Cost": "Cost per item", "Handle": "URL handle"})
    p = p[p["SKU"].astype(str).str.strip() != ""].copy()
    p["Title"] = p["Title"].replace("", np.nan).ffill()
    return p.set_index("SKU")


def order_headers(o):
    hdr = o[o["Financial Status"] != ""].copy()
    hdr["created"] = pd.to_datetime(hdr["Created at"].str[:19])
    for c in ["Subtotal", "Shipping", "Taxes", "Total", "Discount Amount", "Refunded Amount"]:
        hdr[c] = hdr[c].astype(float)
    return hdr.set_index("Name")


def line_margin(D):
    o, r = D["orders"], D["refunds"].copy()
    pv = _products(D["products"])
    hdr = order_headers(o)
    L = o[["Name", "Lineitem SKU", "Lineitem quantity", "Lineitem price", "Lineitem discount"]].copy()
    L.columns = ["Name", "SKU", "qty", "price", "disc"]
    L[["qty", "price", "disc"]] = L[["qty", "price", "disc"]].astype(float)
    L["created"] = L.Name.map(hdr.created)
    L["cost"] = L.SKU.map(pv["Cost per item"].astype(float))
    L["grams"] = L.SKU.map(pv["Weight value (grams)"].astype(float))
    L["gross"] = L.qty * L.price
    L["net_items"] = L.gross - L.disc
    L["cogs"] = L.qty * L.cost
    taxratio = (hdr.Subtotal / (hdr.Subtotal + hdr.Taxes)).fillna(1)
    r["refund_ex_tax"] = r.Amount * r.Name.map(taxratio)
    rs = r.groupby(["Name", "Lineitem SKU"]).refund_ex_tax.sum()
    rq = r.groupby(["Name", "Lineitem SKU"])["Refund Quantity"].sum()
    rr = r[r.Restocked.astype(str).str.lower() == "true"].groupby(["Name", "Lineitem SKU"])["Refund Quantity"].sum()
    key = list(zip(L.Name, L.SKU))
    L["refund"] = [rs.get(k, 0.0) for k in key]
    L["refund_units"] = [rq.get(k, 0) for k in key]
    L["restocked_units"] = [rr.get(k, 0) for k in key]
    w = L.qty * L.grams
    L["wshare"] = w / w.groupby(L.Name).transform("sum")
    lab = D["labels"].set_index("Order Name")
    L["label"] = L.wshare * L.Name.map(lab["Label Cost"] + lab["Insurance Cost"])
    L["ship_rev"] = L.wshare * L.Name.map(hdr.Shipping)
    rshare = L.net_items / L.groupby("Name").net_items.transform("sum").replace(0, np.nan)
    L["fee"] = rshare.fillna(0) * L.Name.map(D["fees"].set_index("Name")["Processing Fee"])
    L["cogs_net"] = L.cogs - L.restocked_units * L.cost
    L["cm"] = L.net_items - L.refund + L.ship_rev - L.cogs_net - L.label - L.fee
    L["title"] = L.SKU.map(pv["Title"])
    return L


def sku_profit(L):
    s = L.groupby("SKU").agg(title=("title", "first"), units=("qty", "sum"), gross=("gross", "sum"), disc=("disc", "sum"),
                             net=("net_items", "sum"), refund=("refund", "sum"), refund_units=("refund_units", "sum"),
                             ship_rev=("ship_rev", "sum"), cogs_net=("cogs_net", "sum"), label=("label", "sum"),
                             fee=("fee", "sum"), cm=("cm", "sum"))
    s["cm_pct"] = s.cm / s.net
    s["disc_pct"] = s.disc / s.gross
    s["return_rate_units"] = s.refund_units / s.units
    s["ship_cost_per_unit"] = s.label / s.units
    return s.sort_values("cm_pct")


def margin_killers(s):
    store = s.cm.sum() / s.net.sum()
    return s[s.cm_pct < store / 2], store


def monthly(L, ads):
    m = L.groupby(L.created.dt.to_period("M")).agg(net=("net_items", "sum"), cm=("cm", "sum"))
    m["ad_spend"] = ads.groupby(ads.Date.dt.to_period("M")).Spend.sum()
    m["cm_after_ads"] = m.cm - m.ad_spend
    m["mer"] = m.net / m.ad_spend
    m.index = m.index.astype(str)
    return m


def inventory(D):
    ih, pv = D["history"], _products(D["products"])
    inv = D["inventory"].set_index("SKU")
    lt = D["lead_times"].set_index("SKU")
    asof = ih.Date.max()
    v30 = ih[ih.Date > asof - pd.Timedelta(days=30)].groupby("SKU")["Units Sold"].mean()
    v90 = ih[ih.Date > asof - pd.Timedelta(days=90)].groupby("SKU")["Units Sold"].sum()
    po = D["pos"]
    nextpo = po[po.Status == "open"].groupby("SKU")["Expected Arrival"].min()
    t = pd.DataFrame({
        "title": pv["Title"].reindex(inv.index),
        "available": inv["Available (not editable)"], "on_hand": inv["On hand (current)"],
        "incoming": inv["Incoming (not editable)"], "v30_per_day": v30,
        "lead_time": lt["Lead Time (days)"], "safety_days": lt["Safety Stock (days)"], "moq": lt["MOQ"],
        "units_90d": v90.reindex(inv.index).fillna(0),
    })
    t["days_of_stock"] = t.available / t.v30_per_day.replace(0, np.nan)
    t["reorder_point"] = (t.v30_per_day * (t.lead_time + t.safety_days)).round(0)
    t["days_to_next_po"] = (nextpo.reindex(t.index) - asof).dt.days
    t["inv_value_at_cost"] = t.on_hand * pv["Cost per item"].astype(float).reindex(t.index)
    t["at_risk"] = t.days_of_stock < t.days_to_next_po.fillna(t.lead_time)
    t["slow_mover"] = (t.days_of_stock > 180) | (t.units_90d < 10)
    t["below_reorder_point"] = t.available < t.reorder_point
    return t.sort_values("days_of_stock"), asof
