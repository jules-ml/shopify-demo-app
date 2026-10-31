# Shopify True Profit & Stock-Out Dashboard (starter)
Runs on the SYNTHETIC Saltline data in ../data. Covers spec screens 1 (true profit, margin killers, waterfall, MER) and 4 (days of stock, at-risk list, slow movers).
Run: `pip install -r requirements.txt && streamlit run streamlit_app.py`
Test: `pytest test_engine.py` (checks against data/reference_answers.json)
Deploy on Streamlit Community Cloud: push the shopify-demo folder (app/ + data/) to a GitHub repo, main file `app/streamlit_app.py`.
Not built yet: refunds-by-order-week (screen 2), new vs returning (screen 3), upload + data quality (screen 5).
