"""Shopify True Profit & Stock-Out Dashboard - portfolio demo on SYNTHETIC data (fictional brand Saltline Supply Co.)."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import engine as e

st.set_page_config(page_title="Shopify True Profit & Stock-Out Dashboard", layout="wide")


@st.cache_data
def compute():
    D = e.load()
    L = e.line_margin(D)
    S = e.sku_profit(L)
    K, store = e.margin_killers(S)
    M = e.monthly(L, D["ads"])
    T, asof = e.inventory(D)
    return L, S, K, store, M, T, asof


L, S, K, store, M, T, asof = compute()
money = lambda x: f"${x:,.0f}"

st.title("True Profit & Stock-Out Dashboard")
st.caption("Demo on synthetic data for a fictional Shopify brand (Saltline Supply Co.), Oct 2025 to Oct 2026. "
           "Payment fees are assumptions based on Shopify Basic US rates.")

tab1, tab2 = st.tabs(["True profit", "Inventory & stock-outs"])

with tab1:
    net, cm, ads = S.net.sum(), S.cm.sum(), M.ad_spend.sum()
    c = st.columns(5)
    c[0].metric("Net item sales", money(net))
    c[1].metric("Contribution margin (before ads)", money(cm), f"{store:.1%} of net")
    c[2].metric("Ad spend", money(ads))
    c[3].metric("Profit after ads", money(cm - ads), f"{(cm - ads) / net:.1%} of net")
    c[4].metric("MER (net sales / ad spend)", f"{net / ads:.2f}")

    st.subheader("Margin killers")
    st.write(f"Products earning less than half the store's {store:.0%} contribution margin, "
             "after refunds, shipping labels, insurance and payment fees.")
    kt = K[["title", "units", "net", "cm", "cm_pct", "return_rate_units", "disc_pct", "ship_cost_per_unit"]].rename(columns={
        "title": "Product", "units": "Units", "net": "Net sales", "cm": "CM $", "cm_pct": "CM %",
        "return_rate_units": "Return rate", "disc_pct": "Discount %", "ship_cost_per_unit": "Ship cost / unit"})
    st.dataframe(kt.style.format({"Units": "{:,.0f}", "Net sales": "${:,.0f}", "CM $": "${:,.0f}", "CM %": "{:.1%}",
                                  "Return rate": "{:.1%}", "Discount %": "{:.1%}", "Ship cost / unit": "${:.2f}"}),
                 width="stretch")

    pick = st.selectbox("Where does the money go? Pick a product", S.index,
                        index=list(S.index).index(K.index[0]) if len(K) else 0,
                        format_func=lambda s: f"{s}  ({S.loc[s, 'title']})")
    r = S.loc[pick]
    steps = [("Gross sales", r.gross), ("Discounts", -r.disc), ("Refunds", -r.refund), ("Shipping charged", r.ship_rev),
             ("COGS (net of restocks)", -r.cogs_net), ("Labels + insurance", -r.label), ("Payment fees", -r.fee)]
    fig = go.Figure(go.Waterfall(x=[s[0] for s in steps] + ["Contribution margin"],
                                 y=[s[1] for s in steps] + [r.cm],
                                 measure=["relative"] * len(steps) + ["total"]))
    fig.update_layout(height=380, margin=dict(t=30, b=10), yaxis_tickprefix="$")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Monthly profit and ad efficiency")
    mc = M.reset_index().rename(columns={"created": "Month"})
    a, b = st.columns(2)
    a.plotly_chart(px.bar(mc, x="Month", y=["cm", "cm_after_ads"], barmode="group",
                          labels={"value": "$", "variable": ""}, title="Contribution margin, before and after ads"),
                   width="stretch")
    b.plotly_chart(px.line(mc, x="Month", y="mer", markers=True, title="MER by month", labels={"mer": "MER"}),
                   width="stretch")

    with st.expander("All products"):
        st.dataframe(S[["title", "units", "net", "cm", "cm_pct"]].sort_values("cm", ascending=False), width="stretch")

with tab2:
    risk, slow = T[T.at_risk], T[T.slow_mover]
    c = st.columns(4)
    c[0].metric("Will stock out before restock", len(risk))
    c[1].metric("Below reorder point", int(T.below_reorder_point.sum()))
    c[2].metric("Inventory value at cost", money(T.inv_value_at_cost.sum()))
    c[3].metric("Cash tied up in slow movers", money(slow.inv_value_at_cost.sum()))
    st.caption(f"Inventory as of {asof:%b %d, %Y}. Velocity uses the last 30 days of sales.")

    st.subheader("At risk: runs out before the next purchase order arrives")
    cols = {"title": "Product", "available": "Available", "v30_per_day": "Sold / day (30d)", "days_of_stock": "Days of stock",
            "days_to_next_po": "Days to next PO", "lead_time": "Lead time", "reorder_point": "Reorder point", "moq": "MOQ"}
    fmt = {"Sold / day (30d)": "{:.2f}", "Days of stock": "{:.1f}", "Days to next PO": "{:.0f}", "Reorder point": "{:.0f}"}
    st.dataframe(risk[list(cols)].rename(columns=cols).style.format(fmt, na_rep="none open"), width="stretch")

    st.subheader("Slow movers: cash sitting on shelves")
    sc = {"title": "Product", "on_hand": "On hand", "units_90d": "Sold (90d)", "days_of_stock": "Days of stock",
          "inv_value_at_cost": "Value at cost"}
    st.dataframe(slow.sort_values("inv_value_at_cost", ascending=False)[list(sc)].rename(columns=sc)
                 .style.format({"Sold (90d)": "{:.0f}", "Days of stock": "{:,.0f}", "Value at cost": "${:,.0f}"}),
                 width="stretch")

    with st.expander("Full stock table"):
        st.dataframe(T, width="stretch")
