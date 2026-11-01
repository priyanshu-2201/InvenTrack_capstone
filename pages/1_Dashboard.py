"""
Inventrack - 1. Analytics, P&L & Performance Dashboard
Modern Pastel SaaS Edition: Interactive Plotly visualisations, P&L financial metrics (₹),
moving averages, revenue trends, stock health, and category distribution.
Strictly scoped to authenticated user_id.
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from database.db_manager import (
    get_all_products,
    get_all_raw_materials,
    get_all_transactions,
    get_inventory_summary_metrics,
    get_pnl_and_moving_averages
)
from components.nav import render_sidebar_navigation, render_top_header

def create_pastel_card(title: str, value: str, subtitle: str = "", bg_color: str = "#ffffff", extra_html: str = ""):
    """
    Outputs a stylized HTML div for pastel SaaS metric cards with rounded corners,
    padding, soft pastel background color, bold prominent numbers, and optional widgets.
    """
    sub_markup = f'<div style="font-size: 0.85rem; color: #475569; margin-top: 0.35rem; font-weight: 500;">{subtitle}</div>' if subtitle else ""
    extra_markup = f'<div style="margin-top: 0.65rem;">{extra_html}</div>' if extra_html else ""

    return f"""
    <div style="
        background-color: {bg_color};
        border-radius: 18px;
        padding: 1.35rem 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03);
        border: 1px solid rgba(0, 0, 0, 0.04);
        margin-bottom: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 125px;
    ">
        <div>
            <div style="font-size: 0.88rem; font-weight: 600; color: #475569; letter-spacing: -0.01em;">{title}</div>
            <div style="font-size: 2.15rem; font-weight: 800; color: #1e293b; letter-spacing: -0.03em; margin: 0.35rem 0 0.1rem 0; line-height: 1.15; white-space: nowrap;">
                {value}
            </div>
            {sub_markup}
        </div>
        {extra_markup}
    </div>
    """

# Page configuration
st.set_page_config(
    page_title="Dashboard | Inventrack",
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
render_sidebar_navigation(current_page="Dashboard")

# Page Header
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 1rem;">
        <div>
            <h1 style="margin: 0; color: #1e293b; font-size: 2rem; letter-spacing: -0.025em;">Executive Analytics &amp; P&amp;L Dashboard</h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748b; font-size: 0.95rem;">
                Real-time financial metrics in Indian Rupees (₹), P&amp;L statements, 7-day/30-day moving averages, and catalog valuation.
            </p>
        </div>
        <div>
            <span class="badge badge-emerald">Live Account Data (INR ₹)</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# Fetch Data Scoped Strictly to Authenticated User
products_df = get_all_products(user_id=user_id)
materials_df = get_all_raw_materials(user_id=user_id)
transactions_df = get_all_transactions(user_id=user_id)
metrics = get_inventory_summary_metrics(user_id=user_id)

# Filter Controls Bar
filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])

with filter_col1:
    timeframe = st.selectbox(
        "Analysis Timeframe",
        ["All Time", "Past 30 Days", "Past 14 Days", "Past 7 Days"],
        index=0
    )

with filter_col2:
    all_categories = ["All Categories"] + sorted(products_df["category"].dropna().unique().tolist()) if not products_df.empty else ["All Categories"]
    selected_category = st.selectbox("Filter Product Category", all_categories, index=0)

with filter_col3:
    stock_status_filter = st.selectbox(
        "Filter Stock Status",
        ["All Items", "Low / Out of Stock Only", "Healthy Stock Only"],
        index=0
    )

# Compute P&L Metrics & Moving Averages for the selected timeframe
pnl_data = get_pnl_and_moving_averages(user_id=user_id, timeframe=timeframe)

# Apply Product Category & Stock Filters
filtered_prods = products_df.copy()
if not filtered_prods.empty:
    if selected_category != "All Categories":
        filtered_prods = filtered_prods[filtered_prods["category"] == selected_category]
    if stock_status_filter == "Low / Out of Stock Only":
        filtered_prods = filtered_prods[filtered_prods["stock_status"] != "Healthy"]
    elif stock_status_filter == "Healthy Stock Only":
        filtered_prods = filtered_prods[filtered_prods["stock_status"] == "Healthy"]

# -------------------------------------------------------------
# TOP METRICS (2-Column Layout)
# -------------------------------------------------------------
st.markdown("### Profit &amp; Loss (P&amp;L) Financial Performance")

top_c1, top_c2 = st.columns(2)
with top_c1:
    cash_left = pnl_data["net_flow"]
    card_cash = create_pastel_card(
        title="Cash left over",
        value=f"₹{cash_left:,.2f}",
        subtitle="Net operating flow (Revenue − Procurement)",
        bg_color="#e0f2fe"
    )
    st.markdown(card_cash, unsafe_allow_html=True)

with top_c2:
    profit = pnl_data["gross_profit"]
    split_progress = """
        <div style="width: 100%; height: 8px; background: rgba(0, 0, 0, 0.08); border-radius: 9999px; overflow: hidden; display: flex; margin-top: 10px;">
            <div style="width: 55%; background-color: #a855f7; height: 100%;" title="55% Profit Margin"></div>
            <div style="width: 45%; background-color: #fdba74; height: 100%;" title="45% Cost Margin"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.74rem; color: #64748b; margin-top: 5px; font-weight: 500;">
            <span style="color: #7e22ce;">55% Profit Margin</span>
            <span style="color: #c2410c;">45% COGS Ratio</span>
        </div>
    """
    card_profit = create_pastel_card(
        title="Profit on sales",
        value=f"₹{profit:,.2f}",
        subtitle=f"Gross margin: {pnl_data['gross_margin_pct']:.1f}%",
        bg_color="#f3e8ff",
        extra_html=split_progress
    )
    st.markdown(card_profit, unsafe_allow_html=True)

# -------------------------------------------------------------
# BOTTOM METRICS (3-Column Layout)
# -------------------------------------------------------------
bot_c1, bot_c2, bot_c3 = st.columns(3)

with bot_c1:
    card_sales = create_pastel_card(
        title="Total sales",
        value=f"₹{pnl_data['total_revenue']:,.2f}",
        subtitle=f"{metrics['total_sales_count']} sales recorded",
        bg_color="#dcfce7"
    )
    st.markdown(card_sales, unsafe_allow_html=True)

with bot_c2:
    cogs_ratio = (pnl_data['total_cogs'] / pnl_data['total_revenue'] * 100) if pnl_data['total_revenue'] > 0 else 0
    card_cogs = create_pastel_card(
        title="Cost of stock sold",
        value=f"₹{pnl_data['total_cogs']:,.2f}",
        subtitle=f"{cogs_ratio:.1f}% Cost of goods sold ratio",
        bg_color="#ffedd5"
    )
    st.markdown(card_cogs, unsafe_allow_html=True)

with bot_c3:
    card_shelf = create_pastel_card(
        title="Stock on shelves",
        value=f"₹{metrics['total_product_valuation']:,.2f}",
        subtitle=f"{int(metrics['total_product_units'])} units across {metrics['total_products']} products",
        bg_color="#fef08a"
    )
    st.markdown(card_shelf, unsafe_allow_html=True)

st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# CHART 1: MOVING AVERAGES & REVENUE TRAJECTORY (PLOTLY)
# -------------------------------------------------------------
st.markdown("### Sales Velocity &amp; Moving Averages (7-Day &amp; 30-Day)")

st.markdown("""
    <div class="chart-desc">
        <strong>Graph Representation &amp; Insights:</strong> This chart plots daily gross sales revenue in Indian Rupees (₹) against two statistical moving average smoothing curves.
        The <strong>slate bars</strong> indicate actual daily sales receipts, the <strong>purple line (7-Day MA)</strong> captures short-term weekly momentum and weekday fluctuations, and the <strong>amber dashed curve (30-Day MA)</strong> highlights the foundational monthly baseline.
    </div>
""", unsafe_allow_html=True)

daily_sales_df = pnl_data["daily_sales_df"]

if not daily_sales_df.empty:
    fig_ma = go.Figure()

    fig_ma.add_trace(go.Bar(
        x=daily_sales_df["Date"],
        y=daily_sales_df["Daily_Sales"],
        name="Daily Sales (₹)",
        marker_color="rgba(148, 163, 184, 0.4)",
        marker_line=dict(width=1, color="#94a3b8"),
        hovertemplate="<b>Date:</b> %{x}<br><b>Daily Sales:</b> ₹%{y:,.2f}<extra></extra>"
    ))

    fig_ma.add_trace(go.Scatter(
        x=daily_sales_df["Date"],
        y=daily_sales_df["7_Day_MA"],
        name="7-Day Moving Avg (₹)",
        line=dict(color="#8b5cf6", width=3),
        mode="lines+markers",
        marker=dict(size=4, color="#7c3aed"),
        hovertemplate="<b>7-Day MA:</b> ₹%{y:,.2f}<extra></extra>"
    ))

    fig_ma.add_trace(go.Scatter(
        x=daily_sales_df["Date"],
        y=daily_sales_df["30_Day_MA"],
        name="30-Day Moving Avg (₹)",
        line=dict(color="#f59e0b", width=2.5, dash="dash"),
        mode="lines",
        hovertemplate="<b>30-Day MA:</b> ₹%{y:,.2f}<extra></extra>"
    ))

    fig_ma.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color="#1e293b"),
        height=360,
        margin=dict(l=20, r=20, t=20, b=30),
        hovermode="x unified",
        xaxis=dict(
            gridcolor="#f1f5f9",
            linecolor="#cbd5e1",
            tickfont=dict(color="#475569")
        ),
        yaxis=dict(
            title="Revenue (₹)",
            title_font=dict(color="#1e293b"),
            gridcolor="#f1f5f9",
            linecolor="#cbd5e1",
            tickfont=dict(color="#475569")
        ),
        autosize=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#475569")
        )
    )
    st.plotly_chart(fig_ma, use_container_width=True, config={'responsive': True, 'displayModeBar': True, 'displaylogo': False})
else:
    st.info("No historical sales records available to compute moving averages.")

st.markdown("<div style='height: 1.2rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# CHART ROW 2: P&L BREAKDOWN & CATEGORY VALUATION DONUT
# -------------------------------------------------------------
chart_col1, chart_col2 = st.columns([3, 2])

with chart_col1:
    st.markdown("#### P&amp;L Financial Structure")
    st.markdown("""
        <div class="chart-desc">
            <strong>Graph Representation:</strong> Comparative financial breakdown displaying total <strong>Gross Revenue</strong> (Sky Blue), <strong>Cost of Goods Sold / COGS</strong> (Peach/Orange), and the resulting <strong>Gross Profit</strong> (Purple) in Indian Rupees (₹).
        </div>
    """, unsafe_allow_html=True)

    if pnl_data["total_revenue"] > 0:
        pnl_breakdown_df = pd.DataFrame([
            {"Metric": "Gross Revenue", "Amount": pnl_data["total_revenue"], "Type": "Revenue"},
            {"Metric": "Cost of Goods (COGS)", "Amount": pnl_data["total_cogs"], "Type": "Cost"},
            {"Metric": "Gross Profit", "Amount": pnl_data["gross_profit"], "Type": "Profit"}
        ])

        fig_pnl = px.bar(
            pnl_breakdown_df,
            x="Metric",
            y="Amount",
            color="Type",
            text="Amount",
            color_discrete_map={
                "Revenue": "#38bdf8",
                "Cost": "#fb923c",
                "Profit": "#a855f7"
            }
        )
        fig_pnl.update_traces(
            texttemplate='₹%{text:,.2f}',
            textposition='outside',
            textfont=dict(color="#1e293b")
        )
        fig_pnl.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color="#1e293b"),
            height=320,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(tickfont=dict(color="#1e293b"), linecolor="#cbd5e1"),
            yaxis=dict(
                title="Amount (₹)",
                title_font=dict(color="#1e293b"),
                gridcolor="#f1f5f9",
                tickfont=dict(color="#475569"),
                linecolor="#cbd5e1"
            ),
            autosize=True,
            showlegend=False
        )
        st.plotly_chart(fig_pnl, use_container_width=True, config={'responsive': True, 'displayModeBar': True, 'displaylogo': False})
    else:
        st.info("No revenue recorded for P&L structure.")

with chart_col2:
    st.markdown("#### Catalog Valuation by Category")
    st.markdown("""
        <div class="chart-desc">
            <strong>Proportional Distribution:</strong> Capital allocation across product categories based on holding valuation (Stock Quantity × Unit Price in ₹).
        </div>
    """, unsafe_allow_html=True)

    if not products_df.empty:
        cat_val = products_df.groupby("category")["inventory_value"].sum().reset_index()
        PASTEL_COLORS = ["#38bdf8", "#a855f7", "#34d399", "#facc15", "#fb923c", "#f472b6", "#818cf8"]
        fig_donut = px.pie(
            cat_val,
            values="inventory_value",
            names="category",
            hole=0.55,
            color_discrete_sequence=PASTEL_COLORS
        )
        fig_donut.update_traces(
            textposition='inside',
            textinfo='percent+label',
            textfont=dict(color="#1e293b", family="Plus Jakarta Sans"),
            hovertemplate="<b>%{label}:</b> ₹%{value:,.2f} (%{percent})<extra></extra>"
        )
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color="#1e293b"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            autosize=True,
            showlegend=False
        )
        st.plotly_chart(fig_donut, use_container_width=True, config={'responsive': True, 'displayModeBar': True, 'displaylogo': False})
    else:
        st.info("No product categories found.")

st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# CHART 4: INVENTORY HEALTH & MONTHLY P&L TABLE
# -------------------------------------------------------------
c_stk, c_pnl_tbl = st.columns([3, 2])

with c_stk:
    st.markdown("#### Inventory Health vs Minimum Reorder Threshold")
    st.markdown("""
        <div class="chart-desc">
            <strong>Stock Sufficiency:</strong> Side-by-side grouped bar chart comparing actual physical units (Sky Blue) against minimum safety thresholds (Slate).
        </div>
    """, unsafe_allow_html=True)

    if not filtered_prods.empty:
        fig_stock = go.Figure()

        fig_stock.add_trace(go.Bar(
            name='Current Stock (Units)',
            x=filtered_prods['name'].str[:22],
            y=filtered_prods['stock_quantity'],
            marker_color='#38bdf8',
            text=filtered_prods['stock_quantity'],
            textposition='auto',
            textfont=dict(color="#1e293b")
        ))

        fig_stock.add_trace(go.Bar(
            name='Min Threshold (Units)',
            x=filtered_prods['name'].str[:22],
            y=filtered_prods['reorder_level'],
            marker_color='#cbd5e1',
            text=filtered_prods['reorder_level'],
            textposition='auto',
            textfont=dict(color="#1e293b")
        ))

        fig_stock.update_layout(
            barmode='group',
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color="#1e293b"),
            margin=dict(l=20, r=20, t=20, b=40),
            height=340,
            autosize=True,
            xaxis=dict(
                tickangle=-30,
                tickfont=dict(color="#475569"),
                linecolor="#cbd5e1"
            ),
            yaxis=dict(
                gridcolor="#f1f5f9",
                linecolor="#cbd5e1",
                tickfont=dict(color="#475569")
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#475569")
            )
        )
        st.plotly_chart(fig_stock, use_container_width=True, config={'responsive': True, 'displayModeBar': True, 'displaylogo': False})
    else:
        st.info("No catalog items found.")

with c_pnl_tbl:
    st.markdown("#### Monthly P&amp;L Summary Statement")
    monthly_pnl_df = pnl_data["monthly_pnl_df"]
    if not monthly_pnl_df.empty:
        disp_pnl = monthly_pnl_df.copy()
        disp_pnl.columns = ["Month", "Revenue (₹)", "Units", "COGS (₹)", "Gross Profit (₹)", "Margin %"]
        disp_pnl["Revenue (₹)"] = disp_pnl["Revenue (₹)"].apply(lambda x: f"₹{x:,.2f}")
        disp_pnl["COGS (₹)"] = disp_pnl["COGS (₹)"].apply(lambda x: f"₹{x:,.2f}")
        disp_pnl["Gross Profit (₹)"] = disp_pnl["Gross Profit (₹)"].apply(lambda x: f"₹{x:,.2f}")
        disp_pnl["Margin %"] = disp_pnl["Margin %"].apply(lambda x: f"{x:.1f}%")

        st.dataframe(disp_pnl, use_container_width=True, hide_index=True)
    else:
        st.info("No monthly P&L records available.")

# -------------------------------------------------------------
# RECENT LEDGER ACTIVITY FEED (Scoped to user_id)
# -------------------------------------------------------------
st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
st.markdown("### Recent Ledger Activity")
tx_df = get_all_transactions(user_id=user_id, limit=6)

if not tx_df.empty:
    display_tx = tx_df[[
        "transaction_code", "transaction_type", "item_name",
        "quantity", "unit_price", "total_amount", "party_name", "transaction_date"
    ]].copy()
    display_tx.columns = [
        "Code", "Type", "Item Description", "Qty", "Unit Price (₹)",
        "Total (₹)", "Counter Party", "Date"
    ]
    st.dataframe(
        display_tx,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No transaction records found in your account.")
