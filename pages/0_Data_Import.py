"""
Inventrack - 0. Data Import Portal
CSV Ingestion Engine for Historical Sales and Inventory Data.
Validates schemas (Date, Product_ID, Quantity, Unit_Price) and directly writes to SQLite scoped to user_id.
"""

import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from database.db_manager import (
    validate_and_process_sales_csv,
    import_csv_to_sqlite,
    get_all_transactions,
    get_all_products,
    DB_PATH
)
from components.nav import render_sidebar_navigation, render_top_header

# Page configuration
st.set_page_config(
    page_title="Data Import | Inventrack",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject modern pastel CSS
css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Authentication Guard
if not st.session_state.get("authenticated", False) or not st.session_state.get("user_id"):
    st.warning("Access restricted. Please authenticate via the main portal.")
    if st.button("Go to Login Gateway"):
        st.switch_page("app.py")
    st.stop()

user_id = st.session_state["user_id"]

# Render Global Top Header & Sidebar Navigation
render_top_header()
render_sidebar_navigation(current_page="Data Import")

# Page Header
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 1rem;">
        <div>
            <h1 style="margin: 0; color: #1e293b; font-size: 2rem; letter-spacing: -0.025em;">Data Import &amp; Ingestion Engine</h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748b; font-size: 0.95rem;">
                Upload historical sales and inventory CSV datasets. Validates schemas, inserts directly into your account's SQLite tables, and updates all ₹ financial metrics.
            </p>
        </div>
        <div>
            <span class="badge badge-blue">Multi-Tenant Ingestion Engine</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# Top Info Card
st.markdown("""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;">
        <h4 style="margin: 0 0 0.5rem 0; color: #1e293b;">Required CSV Schema &amp; Specifications</h4>
        <p style="color: #475569; font-size: 0.9rem; margin-bottom: 0.5rem;">
            The CSV ingestion pipeline requires the following core columns (case-insensitive):
        </p>
        <div style="display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.6rem;">
            <span class="badge badge-slate">Date (e.g. YYYY-MM-DD)</span>
            <span class="badge badge-slate">Product_ID (or SKU)</span>
            <span class="badge badge-slate">Quantity (Integer/Float &gt; 0)</span>
            <span class="badge badge-slate">Unit_Price (₹ Price &gt;= 0)</span>
        </div>
        <p style="color: #64748b; font-size: 0.82rem; margin: 0;">
            <em>Optional supported columns:</em> <code>Product_Name</code>, <code>Category</code>, <code>Cost_Price</code> (for accurate P&amp;L and gross margins), <code>Customer_Name</code>, <code>Notes</code>.
        </p>
    </div>
""", unsafe_allow_html=True)

# Helper function to generate sample test CSV
def generate_sample_csv_string():
    sample_rows = [
        {"Date": "2026-09-01", "Product_ID": "SKU-VLT-101", "Product_Name": "Botanical Day Serum 50ml", "Category": "Skincare", "Quantity": 15, "Unit_Price": 1850.00, "Cost_Price": 750.00, "Customer_Name": "Mumbai Wellness Spa"},
        {"Date": "2026-09-03", "Product_ID": "SKU-VLT-102", "Product_Name": "Lavender Night Elixir 30ml", "Category": "Skincare", "Quantity": 10, "Unit_Price": 2200.00, "Cost_Price": 900.00, "Customer_Name": "Delhi Luxe Retail"},
        {"Date": "2026-09-05", "Product_ID": "SKU-VLT-103", "Product_Name": "Botanical Cleansing Foam 150ml", "Category": "Cleansers", "Quantity": 28, "Unit_Price": 950.00, "Cost_Price": 380.00, "Customer_Name": "Bengaluru Beauty Hub"},
        {"Date": "2026-09-07", "Product_ID": "SKU-VLT-104", "Product_Name": "Silk Velvet Body Creme 200ml", "Category": "Body Care", "Quantity": 18, "Unit_Price": 1250.00, "Cost_Price": 520.00, "Customer_Name": "Hyderabad Emporium"},
        {"Date": "2026-09-10", "Product_ID": "SKU-VLT-105", "Product_Name": "Pure Lavender Oil 15ml", "Category": "Aromatherapy", "Quantity": 35, "Unit_Price": 850.00, "Cost_Price": 320.00, "Customer_Name": "Chennai Organics Co."},
        {"Date": "2026-09-12", "Product_ID": "SKU-VLT-106", "Product_Name": "Mineral Crystal Bath Salts 350g", "Category": "Bath & Spa", "Quantity": 22, "Unit_Price": 780.00, "Cost_Price": 290.00, "Customer_Name": "Pune Retail Store"},
        {"Date": "2026-09-15", "Product_ID": "SKU-VLT-107", "Product_Name": "Glow Lip Balm 10ml", "Category": "Lip Care", "Quantity": 45, "Unit_Price": 620.00, "Cost_Price": 210.00, "Customer_Name": "Kolkata Luxury Center"},
        {"Date": "2026-09-18", "Product_ID": "SKU-VLT-108", "Product_Name": "Aroma Mist Spray 250ml", "Category": "Aromatherapy", "Quantity": 20, "Unit_Price": 1100.00, "Cost_Price": 440.00, "Customer_Name": "Jaipur Boutique"},
        {"Date": "2026-09-22", "Product_ID": "SKU-VLT-101", "Product_Name": "Botanical Day Serum 50ml", "Category": "Skincare", "Quantity": 25, "Unit_Price": 1850.00, "Cost_Price": 750.00, "Customer_Name": "Goa Resort Spa"},
        {"Date": "2026-09-25", "Product_ID": "SKU-VLT-102", "Product_Name": "Lavender Night Elixir 30ml", "Category": "Skincare", "Quantity": 14, "Unit_Price": 2200.00, "Cost_Price": 900.00, "Customer_Name": "Ahmedabad Lifestyle Hub"},
        {"Date": "2026-09-28", "Product_ID": "SKU-VLT-103", "Product_Name": "Botanical Cleansing Foam 150ml", "Category": "Cleansers", "Quantity": 32, "Unit_Price": 950.00, "Cost_Price": 380.00, "Customer_Name": "Surat Organics Hub"},
        {"Date": "2026-10-02", "Product_ID": "SKU-VLT-104", "Product_Name": "Silk Velvet Body Creme 200ml", "Category": "Body Care", "Quantity": 16, "Unit_Price": 1250.00, "Cost_Price": 520.00, "Customer_Name": "Indore Beauty Emporium"},
        {"Date": "2026-10-05", "Product_ID": "SKU-VLT-105", "Product_Name": "Pure Lavender Oil 15ml", "Category": "Aromatherapy", "Quantity": 40, "Unit_Price": 850.00, "Cost_Price": 320.00, "Customer_Name": "Chandigarh Spa Hub"},
        {"Date": "2026-10-08", "Product_ID": "SKU-VLT-106", "Product_Name": "Mineral Crystal Bath Salts 350g", "Category": "Bath & Spa", "Quantity": 26, "Unit_Price": 780.00, "Cost_Price": 290.00, "Customer_Name": "Kochi Botanical Market"},
        {"Date": "2026-10-12", "Product_ID": "SKU-VLT-107", "Product_Name": "Glow Lip Balm 10ml", "Category": "Lip Care", "Quantity": 50, "Unit_Price": 620.00, "Cost_Price": 210.00, "Customer_Name": "Lucknow Boutique Store"},
        {"Date": "2026-10-15", "Product_ID": "SKU-VLT-108", "Product_Name": "Aroma Mist Spray 250ml", "Category": "Aromatherapy", "Quantity": 28, "Unit_Price": 1100.00, "Cost_Price": 440.00, "Customer_Name": "Nagpur Wellness Clinic"},
        {"Date": "2026-10-18", "Product_ID": "SKU-VLT-101", "Product_Name": "Botanical Day Serum 50ml", "Category": "Skincare", "Quantity": 30, "Unit_Price": 1850.00, "Cost_Price": 750.00, "Customer_Name": "Mumbai Luxe Retail"},
        {"Date": "2026-10-22", "Product_ID": "SKU-VLT-102", "Product_Name": "Lavender Night Elixir 30ml", "Category": "Skincare", "Quantity": 18, "Unit_Price": 2200.00, "Cost_Price": 900.00, "Customer_Name": "Delhi Beauty Clinic"},
        {"Date": "2026-10-25", "Product_ID": "SKU-VLT-105", "Product_Name": "Pure Lavender Oil 15ml", "Category": "Aromatherapy", "Quantity": 45, "Unit_Price": 850.00, "Cost_Price": 320.00, "Customer_Name": "Bengaluru Central Store"}
    ]
    return pd.DataFrame(sample_rows).to_csv(index=False)

# Ingestion Options Bar
c_up, c_tpl = st.columns([3, 1.2])

with c_tpl:
    st.markdown("##### Sample Template")
    sample_csv_data = generate_sample_csv_string()
    st.download_button(
        label="Download Template CSV",
        data=sample_csv_data,
        file_name="inventrack_sales_inventory_template.csv",
        mime="text/csv",
        use_container_width=True
    )
    if st.button("Load Demo Dataset", use_container_width=True, help="Populate with real-world historical sales data"):
        st.session_state["demo_csv_loaded"] = True
        st.rerun()

with c_up:
    st.markdown("##### Upload File")
    uploaded_file = st.file_uploader(
        "Upload Historical Sales / Inventory CSV File",
        type=["csv"],
        help="Upload CSV containing Date, Product_ID, Quantity, Unit_Price"
    )

# Determine data source
df_raw = None
source_name = ""

if uploaded_file is not None:
    try:
        df_raw = pd.read_csv(uploaded_file)
        source_name = f"Uploaded File: {uploaded_file.name}"
    except Exception as e:
        st.error(f"Failed to read CSV: {str(e)}")
elif st.session_state.get("demo_csv_loaded", False):
    df_raw = pd.read_csv(io.StringIO(sample_csv_data))
    source_name = "Demo Real-World Sales Dataset (INR ₹)"

# Process and Validate Data
if df_raw is not None:
    st.markdown("---")
    st.markdown(f"### Schema Validation & Preview — *{source_name}*")

    # Validate using pandas function
    is_valid, standardized_df, val_msg = validate_and_process_sales_csv(df_raw)

    if not is_valid:
        st.error(f"Validation Failed: {val_msg}")
        st.markdown("#### Detected Columns in Uploaded File:")
        st.code(", ".join(df_raw.columns.tolist()), language="text")
        st.markdown("Please adjust your CSV headers to match: `Date`, `Product_ID`, `Quantity`, `Unit_Price`.")
    else:
        st.success(f"Validation Passed: {val_msg}")

        # Metrics Summary of the uploaded data
        total_rows = len(standardized_df)
        total_units = int(standardized_df["quantity"].sum())
        total_revenue = float(standardized_df["total_amount"].sum())
        total_cogs = float(standardized_df["cogs"].sum())
        est_gross_profit = total_revenue - total_cogs
        margin_pct = (est_gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        unique_skus = standardized_df["item_sku"].nunique()
        start_date = standardized_df["transaction_date"].min()
        end_date = standardized_df["transaction_date"].max()

        v1, v2, v3, v4, v5 = st.columns(5)
        with v1:
            st.metric("Total Records", f"{total_rows:,} rows")
        with v2:
            st.metric("Total Units Sold", f"{total_units:,} units")
        with v3:
            st.metric("Total Revenue (₹)", f"₹{total_revenue:,.2f}")
        with v4:
            st.metric("Est. Gross Profit (₹)", f"₹{est_gross_profit:,.2f}", delta=f"{margin_pct:.1f}% Margin")
        with v5:
            st.metric("Date Span", f"{start_date} to {end_date}")

        # Data preview
        with st.expander("View Standardized Ingestion Dataset (First 15 Rows)", expanded=True):
            preview_cols = [
                "transaction_date", "item_sku", "item_name", "category",
                "quantity", "unit_price", "cost_price", "total_amount", "party_name"
            ]
            preview_display = standardized_df[preview_cols].head(15).copy()
            preview_display.columns = [
                "Date", "Product ID / SKU", "Product Name", "Category",
                "Qty", "Unit Price (₹)", "Cost Price (₹)", "Total (₹)", "Customer"
            ]
            st.dataframe(preview_display, use_container_width=True, hide_index=True)

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        # Ingestion execution panel
        ingest_col1, ingest_col2 = st.columns([2, 1])

        with ingest_col1:
            replace_mock = st.checkbox(
                "Cleanly overwrite previous dataset for this account",
                value=True,
                help="When enabled, previous records for this user account are cleared before importing."
            )

        with ingest_col2:
            st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
            if st.button("Ingest Data to Account", type="primary", use_container_width=True):
                with st.spinner("Ingesting records into SQLite database..."):
                    success, msg = import_csv_to_sqlite(standardized_df, user_id=user_id, replace_old_data=replace_mock)
                    if success:
                        st.cache_data.clear()
                        st.success(msg)
                        st.balloons()
                        st.markdown("""
                            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 1.2rem; margin-top: 1rem; color: #065f46;">
                                <h4 style="margin: 0 0 0.5rem 0; color: #047857;">Data Successfully Ingested!</h4>
                                <p style="margin: 0; font-size: 0.95rem;">
                                    Your account database has been updated. Navigate to <strong>Dashboard</strong> to view the newly computed ₹ financial metrics, moving averages, and P&amp;L module!
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(msg)

else:
    # Empty State & Instructions
    st.info("Please upload a CSV file or click 'Load Demo Dataset' to inspect and insert historical data into your account.")

# Current SQLite Database Summary (Scoped to user_id)
st.markdown("---")
st.markdown("### Current Account Database State")

c_db1, c_db2 = st.columns(2)
with c_db1:
    current_txns = get_all_transactions(user_id=user_id)
    st.markdown(f"**Current Transactions in Account (`transactions` table):** `{len(current_txns):,}` records")
    if not current_txns.empty:
        curr_rev = current_txns["total_amount"].sum()
        st.markdown(f"- Total Cumulative Turnover: **₹{curr_rev:,.2f}**")
        st.markdown(f"- Date Range: **{current_txns['transaction_date'].min()}** to **{current_txns['transaction_date'].max()}**")

with c_db2:
    current_prods = get_all_products(user_id=user_id)
    st.markdown(f"**Current Catalog SKUs in Account (`products` table):** `{len(current_prods):,}` active products")
    if not current_prods.empty:
        curr_val = current_prods["inventory_value"].sum()
        st.markdown(f"- Total Catalog Value: **₹{curr_val:,.2f}**")
        st.markdown(f"- Categories: {', '.join(current_prods['category'].unique().tolist()[:4])}...")
