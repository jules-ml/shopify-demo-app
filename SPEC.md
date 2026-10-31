# SPEC: Shopify True Profit & Stock-Out Dashboard (Streamlit portfolio demo)

**All data in `data/` is SYNTHETIC.** It belongs to the fictional brand "Saltline Supply Co." and was made by `generate_data.py` (seed 20261026, run `python generate_data.py`). Run `python sanity_check.py` to see the expected answers. They're also saved in `data/reference_answers.json`.

**Pitch:** "I turn your Shopify, ad and cost exports into a dashboard that shows true profit per order and per product, plus which products stock out next, so the 3-hour Monday spreadsheet session goes away."

## Data files
The period is Oct 26, 2025 to Oct 25, 2026. Inventory is a snapshot as of the end of Oct 25, 2026.

| File | Rows | Format |
|---|---|---|
| `orders.csv` | 8,527 line rows (5,182 orders) | Shopify orders export ([doc](https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders)). One row per line item. **Order-level fields such as Subtotal, Shipping, Taxes, Total and Discount Code appear only on the first row of each order**, so forward-fill or group by `Name`. `Created at` looks like `2026-01-15 14:32:10 -0500`. |
| `products.csv` | 35 SKUs | Shopify products CSV, **current headers** ([doc](https://help.shopify.com/en/manual/products/import-export/using-csv)): `URL handle`, `SKU`, `Price`, `Cost per item`, `Weight value (grams)`. Older exports use `Handle`, `Variant SKU`, `Variant Price` and `Variant Grams`, so the mapper must accept both. |
| `inventory.csv` | 35 | Shopify inventory CSV, "All states" layout ([doc](https://help.shopify.com/en/manual/products/inventory/setup/inventory-csv)): `Available (not editable)`, `On hand (current)`, `Incoming (not editable)` and so on. |
| `inventory_history.csv` | 12,775 | Synthetic schema, because Shopify has no daily-history export: Date, SKU, On hand (end of day), Units Sold, Units Received, Units Adjusted. |
| `purchase_orders.csv` / `supplier_lead_times.csv` | 106 / 35 | Synthetic. These are the supplier details a client would fill in: lead time, safety-stock days, minimum order quantity (MOQ). |
| `refunds.csv` | 368 | Based on the Shopify transaction-history export (Order, Name, Kind=refund, Gateway, Created At, Amount…). **I added these columns:** Lineitem SKU, Refund Quantity, Restocked, Refund Reason, Order Created At. Refunds join on `Name`. |
| `shipping_labels.csv` | 5,182 | Synthetic, in a ShipStation-style layout: Order Name, Label Cost, Insurance Cost. This is the merchant's real shipping cost. The `Shipping` column in orders is what the customer paid. |
| `fees.csv` + `fee_assumptions.json` | 5,182 | **These are assumptions**, based on Shopify's Basic plan US online rates ([pricing page](https://www.shopify.com/pricing), checked Oct 2026). Standard cards: 2.9% + $0.30 on 80% of orders. Amex/premium: 3.5% + $0.30 on 12%. PayPal: 3.49% + $0.49 on 8%. For a real client, use their actual payout data. |
| `ad_spend.csv` | 2,616 | Daily spend by campaign for Meta, Google and TikTok, including the numbers each platform claims for itself. |
| `orders_messy.csv` + `orders_messy_answer_key.csv` | 810 / 207 | Test file for the upload tab. The answer key lists every issue I planted. |

## Screens and KPIs
Definitions used throughout:
- `net_items = Lineitem price × Lineitem quantity − Lineitem discount`
- `refund_ex_tax = refund Amount × Subtotal/(Subtotal+Taxes)`
- Shipping charged to the customer, label cost and insurance are split across an order's lines by weight share (`qty × Weight value (grams)`).
- Payment fees are split by each line's share of `net_items`.

1. **True Profit (by order and by SKU):**
   - Gross sales = Σ price × qty
   - Discounts = Σ Lineitem discount
   - Net sales = gross − discounts − refunds (ex tax)
   - **Contribution margin (CM) = net items − refunds + shipping charged − (COGS − restocked units × Cost per item) − label and insurance cost − payment fee**
   - CM% = CM / net items
   - After ads: CM − ad spend, and **MER = net item sales / total ad spend** (shown by month).
   - **Margin-killers table:** SKUs with CM% below half the store's CM%. Columns: return rate (refunded units / units sold), discount % (discounts / gross), shipping cost per unit, and CM $. Include a waterfall chart for each SKU.
2. **Refunds by original order week:** put each refund in the week of `Order Created At`, not the week it was processed. Show both views side by side with a toggle, plus a lag histogram (refund date minus order date).
3. **New vs returning customers:** an order is "new" if it's that Email's first order in the data. Show revenue and orders for new vs returning, repeat rate (customers with 2 or more orders / all customers), and orders and CM by Discount Code (for example, how WELCOME15 customers behave over time).
4. **Inventory and stock-outs:**
   - velocity v30 = units sold over the last 30 days / 30
   - **Days of stock = Available / v30**
   - **Reorder point = v30 × (lead time + safety days)**
   - **At risk** = days of stock < days until the next open purchase order arrives (or < lead time if there's no PO)
   - **Slow movers** = days of stock > 180, or fewer than 10 units sold in the last 90 days
   - Inventory value at cost = On hand × Cost per item
5. **Upload + data quality:** column mapping, then validation, then a cleaned table, then an exceptions report. Score it against `orders_messy_answer_key.csv`.

## Stories planted in the data (check that your app finds them)
- **Margin killers** (store-wide CM before ads is about 53%):
  - `DRK-POUR` Ceramic Pour-Over Set: CM about 6%. 22% of units come back, mostly "Arrived damaged". Shipping costs about $17 per unit (2.3 kg, plus fragile surcharge and insurance).
  - `BND-GIFT` Coastal Gift Bundle: CM about 13%. The BUNDLE40 code gives 31% average discount.
  - `HTX-THR-*` Linen Throws: CM 24–30%, with return rates of 22–29% ("Color not as pictured").
- **About to stock out:**
  - `CND-SSC-08`: about 6 days of stock, while the next PO arrives in 16 days.
  - `DRK-TMB-NVY`: about 7.6 days of stock, while the next PO arrives in 40 days.
  - Both bestsellers' demand picked up in the last 6 weeks.
- **Slow movers:** `SKN-FOIL`, `HFR-REED`, `HFR-WICK` and `DRK-MUG-TER`. Each has 263–414 units on hand, at most 8 units sold in 90 days, and about $10.5K tied up at cost combined.
- **Seasonality:** net item sales were about $41K in Nov 2025 and $46K in Dec 2025, against roughly $25K in a typical month. Black Friday weekend spikes. Jan–Feb are slow.
- **Refund lag:** 100% of refunds post in a later week than the order, with a median lag of 21 days.
- **TikTok test, Aug 2026:** TikTok spend jumps about 4x and MER drops to about 3.1, versus about 3.9 normally.
- **Customers:** about 69% of orders come from new customers, and the repeat rate is about 22%.

## Reusable "column mapping + validation" design
- `schema.yaml` defines canonical fields (`order_id`, `order_date`, `sku`, `qty`, `unit_price`, `line_discount`, `subtotal`, `shipping`, `taxes`, `total`, `email`, `discount_code`, `unit_cost`…). Each field has a type, a required flag, and a list of **aliases**, for example `sku: ["Lineitem SKU", "Lineitem sku", "Variant SKU", "SKU"]`.
- Mapper steps:
  1. Normalize headers: strip, lowercase, collapse spaces.
  2. Auto-match against the aliases, then fuzzy-match anything left (difflib).
  3. Let the user fix the matches in a `st.data_editor`.
  4. Save the mapping per client as JSON so next month's file drops straight in.
- Validators produce a row-level `issues` table (row, field, rule, value):
  - required fields not blank
  - dates parsed with several formats plus timezone offsets (flag the ambiguous ones)
  - currency strings cleaned (`$`, commas)
  - SKUs stripped and uppercased, then checked against the products catalog
  - quantity greater than 0
  - exact duplicates and duplicate (Name, SKU) pairs
  - forward-fill of order-level fields
  - Subtotal = Σ line net (tolerance ±$0.02)
- Output: clean parquet files plus `exceptions.csv`, and a quality score (% of rows clean). Every screen reads only the cleaned canonical tables.

## Suggested build order (5–6 evenings)
1. Loaders plus the canonical schema and mapper. Get `orders.csv` and `products.csv` into clean tables and match the order count (5,182).
2. Line-level CM engine (allocations, refunds, fees). Check the numbers against `reference_answers.json`.
3. True Profit screen, margin-killers table and waterfall chart.
4. Refund cohort view, and the new vs returning customers screen.
5. Inventory screen: days of stock, reorder point, at-risk list and slow movers.
6. Upload + data quality tab, scored against the answer key. Then deploy on Streamlit Community Cloud and record a 2-minute walkthrough.
