"""
Inventrack - Inventory & Flow Management System
Pixel-aligned SaaS Dashboard with 100% Dynamic SQLite Computations
All metrics, banners, badges, charts, and user profile data are strictly scoped to st.session_state['user_id'].
"""

import os
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from database.db_manager import (
    init_db,
    get_user_by_id,
    get_low_stock_items,
    get_stock_health_breakdown,
    get_financial_kpis,
    get_weekly_sales_trend,
    get_all_products,
    create_user,
    verify_user,
    DB_PATH
)
from components.nav import render_sidebar_navigation, render_top_header

# Page configuration
st.set_page_config(
    page_title="Inventrack",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject pixel-aligned CSS
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Completely hide and remove the sidebar across the application
st.markdown("""
<style>
section[data-testid="stSidebar"],
div[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
div[data-testid="collapsedControl"],
button[data-testid="stSidebarCollapseButton"],
button[data-testid="baseButton-headerNoPadding"],
[data-testid="stSidebarNav"],
div[data-testid="stSidebarNav"],
nav[data-testid="stSidebarNav"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
    z-index: 1000 !important;
    pointer-events: none !important;
}

.top-bar-container,
.top-nav-bar-wrapper,
.top-header-shell,
.top-header-bar {
    pointer-events: none !important;
}

.top-bar-container input,
.top-bar-container button,
.top-bar-container [data-testid="stPopover"],
.top-nav-bar-wrapper input,
.top-nav-bar-wrapper button,
.top-nav-bar-wrapper [data-testid="stPopover"] {
    pointer-events: auto !important;
}
</style>
""", unsafe_allow_html=True)

# Ensure database schema is ready
init_db()

# -------------------------------------------------------------
# AUTHENTICATION GATEWAY
# -------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"] or not st.session_state.get("user_id"):
    _, col_login, _ = st.columns([1, 1.4, 1])
    with col_login:
        st.markdown("""
            <div style="text-align: center; margin-top: 3.5rem; margin-bottom: 1.5rem;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; background: #2563eb; border-radius: 14px; margin-bottom: 0.8rem; box-shadow: 0 4px 12px rgba(37,99,235,0.25);">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2">
                        <rect x="3" y="3" width="18" height="18" rx="4"/>
                        <path d="M3 9H21"/>
                        <path d="M9 13H15"/>
                    </svg>
                </div>
                <h2 style="color: #1e293b; margin: 0; font-size: 1.85rem; font-weight: 800; letter-spacing: -0.025em;">Inventrack</h2>
                <p style="color: #64748b; font-size: 0.92rem; margin-top: 0.3rem;">B2B Inventory &amp; Financial Management Gateway</p>
            </div>
        """, unsafe_allow_html=True)

        tab_signin, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_signin:
            with st.form("signin_form", clear_on_submit=False):
                st.markdown("<p style='color: #475569; font-size: 0.88rem; margin-bottom: 0.6rem;'>Enter your credentials to access your store dashboard.</p>", unsafe_allow_html=True)
                login_user = st.text_input("Username", placeholder="Enter username", key="login_user")
                login_pass = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass")
                submit_login = st.form_submit_button("Sign In to Inventrack", use_container_width=True)

                if submit_login:
                    if not login_user or not login_pass:
                        st.error("Please enter both username and password.")
                    else:
                        user_id = verify_user(login_user, login_pass)
                        if user_id:
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = login_user.strip()
                            st.session_state["user_id"] = user_id
                            st.success("Authentication successful. Opening store dashboard...")
                            st.rerun()
                        else:
                            st.error("Invalid credentials. Please verify your username and password.")

        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                st.markdown("<p style='color: #475569; font-size: 0.88rem; margin-bottom: 0.6rem;'>Register a new account (starts as a 100% clean blank slate).</p>", unsafe_allow_html=True)
                new_user = st.text_input("Username", placeholder="Choose username", key="reg_user")
                new_pass = st.text_input("Password", type="password", placeholder="Choose password", key="reg_pass")
                submit_register = st.form_submit_button("Create Account", use_container_width=True)

                if submit_register:
                    if not new_user or not new_pass:
                        st.error("Please enter both username and password.")
                    else:
                        success, msg = create_user(new_user, new_pass)
                        if success:
                            st.success("Inventrack account created successfully.")
                        else:
                            st.error(msg)

        st.markdown("""
            <div style="text-align: center; margin-top: 1.5rem; color: #94a3b8; font-size: 0.8rem;">
                Inventrack Integrated Valuation &bull; Multi-Tenant B2B SaaS &bull; SHA-256 Backed
            </div>
        """, unsafe_allow_html=True)
    st.stop()

user_id = st.session_state.get("user_id")

# -------------------------------------------------------------
# 0. BALLOON ANIMATION & TOAST NOTIFICATION (Sale Completion Animation)
# Checked at top of dashboard rendering cycle to ensure complete playback
# -------------------------------------------------------------
if st.session_state.get('sale_success', False):
    st.balloons()
    st.toast("Sale recorded successfully!", icon="🎉")
    st.session_state['sale_success'] = False


@st.dialog("Record a Sale")
def record_sale_modal(current_user_id):
    """Interactive modal to quickly record a sale with live stock validation."""
    from database.db_manager import get_all_products, log_transaction
    from datetime import date

    products_df = get_all_products(user_id=current_user_id)
    if products_df.empty:
        st.warning("No products found in inventory. Please add or import products first.")
        return

    prod_options = {
        f"{r['name']} ({r['sku']}) · Stock: {r['stock_quantity']} · ₹{r['unit_price']:,.2f}": r
        for _, r in products_df.iterrows()
    }
    selected_label = st.selectbox("Select Product to Sell", list(prod_options.keys()), key="modal_sale_prod")
    selected_prod = prod_options[selected_label]

    with st.form("modal_record_sale_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            qty = st.number_input(
                "Quantity Sold",
                min_value=1,
                max_value=max(1, int(selected_prod["stock_quantity"])),
                value=1,
                step=1,
                key="modal_sale_qty"
            )
        with c2:
            unit_price = st.number_input(
                "Selling Price (₹)",
                min_value=0.0,
                value=float(selected_prod["unit_price"]),
                step=10.0,
                key="modal_sale_price"
            )

        c3, c4 = st.columns(2)
        with c3:
            party_name = st.text_input("Customer Name", value="Walk-in Customer", key="modal_sale_party")
        with c4:
            txn_date = st.date_input("Transaction Date", value=date.today(), key="modal_sale_date")

        notes = st.text_input("Invoice / Notes", placeholder="e.g. INV-1002, Paid via UPI", key="modal_sale_notes")
        total_val = qty * unit_price
        st.info(f"**Total Transaction Value:** ₹{total_val:,.2f}")

        submit = st.form_submit_button("Confirm & Complete Sale", use_container_width=True, type="primary")
        if submit:
            if qty > selected_prod["stock_quantity"]:
                st.error(f"Cannot complete sale: requested {qty} units, but only {selected_prod['stock_quantity']} available!")
            else:
                success, msg = log_transaction(
                    user_id=current_user_id,
                    transaction_type="SALE",
                    item_type="PRODUCT",
                    item_id=selected_prod["id"],
                    quantity=qty,
                    unit_price=unit_price,
                    party_name=party_name.strip() or "Walk-in Customer",
                    transaction_date=txn_date.strftime("%Y-%m-%d"),
                    notes=notes
                )
                if success:
                    st.session_state['sale_success'] = True
                    st.success(f"{msg} - Sale recorded successfully! Close dialog to view dashboard balloons.")
                    # Do NOT trigger st.rerun() immediately inside the submission block


# -------------------------------------------------------------
# 1. DYNAMIC USER PROFILE & GREETING
# Query Users table: SELECT username FROM Users WHERE id = ?
# -------------------------------------------------------------
user_record = get_user_by_id(user_id)
username = user_record["username"] if user_record and user_record.get("username") else st.session_state.get("username", "Khushi")
st.session_state["username"] = username

# Dynamic Alert Check: Query products for stock <= reorder_level
low_stock_items = get_low_stock_items(user_id=user_id)
low_count = len(low_stock_items)

# Render Global Top Header (active search bar & popover) & Sidebar Navigation (native routing)
render_top_header(username=username)
render_sidebar_navigation(current_page="Dashboard", low_stock_count=low_count)

# -------------------------------------------------------------
# 2. HEADER & TOP CONTROLS
# -------------------------------------------------------------
hdr_left, hdr_right = st.columns([1.25, 1.75], vertical_alignment="bottom")

with hdr_left:
    date_str = datetime.now().strftime("%A, %d %B · all amounts in ₹")
    st.markdown(f"""
        <div style="margin-bottom: 0.4rem;">
            <div class="dash-title">Welcome back, {username}</div>
            <div class="dash-subtitle">{date_str}</div>
        </div>
    """, unsafe_allow_html=True)

with hdr_right:
    st.markdown('<div class="action-btn-row">', unsafe_allow_html=True)
    btn_col1, btn_col2, btn_col3 = st.columns([1.15, 1.05, 0.95], vertical_alignment="center")
    with btn_col1:
        if st.button("Record a sale", icon=":material/point_of_sale:", key="btn_record_sale", use_container_width=True):
            record_sale_modal(user_id)
    with btn_col2:
        if st.button("Import data", icon=":material/upload:", key="btn_import_data", use_container_width=True):
            st.session_state['current_page'] = 'Data import'
            st.switch_page("pages/0_Data_Import.py")
    with btn_col3:
        if st.button("Refresh", icon=":material/refresh:", key="btn_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 3. FILTER PILLS & CATEGORY DROPDOWN (Tight Horizontal Container)
# -------------------------------------------------------------
if "active_filter" not in st.session_state:
    st.session_state["active_filter"] = "All time"
if "filter_time" not in st.session_state:
    st.session_state["filter_time"] = st.session_state["active_filter"]

active_timeframe = st.session_state.get("active_filter", "All time")

p1, p2, p3, p_cat, p_fill = st.columns([0.16, 0.16, 0.16, 0.28, 0.24], gap="small", vertical_alignment="center")

with p1:
    if active_timeframe == "All time":
        if st.button("All time", icon=":material/check:", key="filter_pill_active"):
            st.session_state["active_filter"] = "All time"
            st.session_state["filter_time"] = "All time"
            st.rerun()
    else:
        if st.button("All time", key="filter_pill_inactive_all_time"):
            st.session_state["active_filter"] = "All time"
            st.session_state["filter_time"] = "All time"
            st.rerun()

with p2:
    if active_timeframe == "This month":
        if st.button("This month", icon=":material/check:", key="filter_pill_active"):
            st.session_state["active_filter"] = "This month"
            st.session_state["filter_time"] = "This month"
            st.rerun()
    else:
        if st.button("This month", key="filter_pill_inactive_this_month"):
            st.session_state["active_filter"] = "This month"
            st.session_state["filter_time"] = "This month"
            st.rerun()

with p3:
    if active_timeframe == "Last 7 days":
        if st.button("Last 7 days", icon=":material/check:", key="filter_pill_active"):
            st.session_state["active_filter"] = "Last 7 days"
            st.session_state["filter_time"] = "Last 7 days"
            st.rerun()
    else:
        if st.button("Last 7 days", key="filter_pill_inactive_last_7_days"):
            st.session_state["active_filter"] = "Last 7 days"
            st.session_state["filter_time"] = "Last 7 days"
            st.rerun()

with p_cat:
    products_catalog = get_all_products(user_id=user_id)
    raw_cats = sorted(products_catalog["category"].dropna().unique().tolist()) if not products_catalog.empty else []
    categories = ["🏷️ All categories"] + [f"🏷️ {c}" for c in raw_cats]
    selected_cat_raw = st.selectbox("Category", categories, label_visibility="collapsed", key="select_cat_pill")
    selected_cat = selected_cat_raw.replace("🏷️", "").strip()

st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 4. ALERT BANNER (Dynamic Low Stock Warning)
# If count > 0: renders warning banner with exact count and names.
# If count == 0: completely hidden.
# -------------------------------------------------------------
if not st.session_state.get("dismiss_low_alert", False) and low_count > 0:
    low_names = [item["name"] for item in low_stock_items[:3]]
    if len(low_stock_items) > 3:
        items_str = f"{', '.join(low_names)} and {len(low_stock_items) - 3} more"
    elif len(low_names) == 2:
        items_str = f"{low_names[0]} and {low_names[1]}"
    else:
        items_str = ", ".join(low_names)

    items_label = f"{low_count} item is running low" if low_count == 1 else f"{low_count} items are running low"

    alert_c1, alert_c2, alert_c3 = st.columns([5.5, 1.15, 0.35], vertical_alignment="center")
    with alert_c1:
        st.markdown(f"""
            <div class="alert-banner-yellow">
                <div class="alert-text">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    <span><strong>{items_label}:</strong> {items_str}. Reorder soon so you don't run out.</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with alert_c2:
        if st.button("See low items", key="btn_see_low", use_container_width=True):
            st.switch_page("pages/2_Inventory.py")

    with alert_c3:
        if st.button("✕", key="btn_dismiss_alert", help="Dismiss alert"):
            st.session_state["dismiss_low_alert"] = True
            st.rerun()

    st.markdown("<div style='height: 1.0rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. DYNAMIC 'MONEY IN AND OUT' METRICS
# Aggregates Transactions and Products scoped to user_id
# -------------------------------------------------------------
kpi_data = get_financial_kpis(user_id=user_id, timeframe=active_timeframe, category=selected_cat)

total_sales = kpi_data["total_sales"]
cogs = kpi_data["cogs"]
profit = kpi_data["profit"]
cash_left = kpi_data["cash_left"]
margin_pct = kpi_data["margin_pct"]
cost_ratio = kpi_data["cost_ratio"]

# Dynamic Badges
sales_growth = kpi_data["sales_growth"]
if sales_growth is not None:
    arrow = "↗" if sales_growth >= 0 else "↘"
    sales_badge_text = f"{arrow} {abs(sales_growth):.0f}%"
else:
    sales_badge_text = "↗ 0%"

cogs_growth = kpi_data["cogs_growth"]
if cogs_growth is not None:
    arrow = "↗" if cogs_growth >= 0 else "↘"
    cogs_badge_text = f"{arrow} {abs(cogs_growth):.0f}%"
else:
    cogs_badge_text = "↗ 0%"

profit_growth = kpi_data["profit_growth"]
if profit_growth is not None:
    arrow = "↗" if profit_growth >= 0 else "↘"
    profit_badge_text = f"{arrow} {abs(profit_growth):.0f}%"
else:
    profit_badge_text = "↗ 0%"

cash_growth = kpi_data["cash_growth"]
if cash_growth is not None:
    arrow = "↗" if cash_growth >= 0 else "↘"
    cash_badge_text = f"{arrow} {abs(cash_growth):.0f}%"
else:
    cash_badge_text = "↗ 0%"

st.markdown("""
    <div>
        <div class="section-heading">Money in and out</div>
        <div class="section-subheading">What you earned, what it cost and what you kept.</div>
    </div>
""", unsafe_allow_html=True)

m_c1, m_c2, m_c3, m_c4 = st.columns(4)

with m_c1:
    st.markdown(f"""
        <div class="white-metric-card">
            <div class="card-top-row">
                <div class="accent-icon-sq sq-blue">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="2" y="6" width="20" height="12" rx="2"/>
                        <circle cx="12" cy="12" r="3"/>
                        <line x1="6" y1="12" x2="6.01" y2="12"/>
                        <line x1="18" y1="12" x2="18.01" y2="12"/>
                    </svg>
                </div>
                <span class="card-title-text">Total sales</span>
            </div>
            <div class="card-big-value">₹{total_sales:,.2f}</div>
            <div class="card-bottom-row">
                <span class="badge-green-pill">{sales_badge_text}</span>
                <span class="card-sublabel">vs last period</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with m_c2:
    st.markdown(f"""
        <div class="white-metric-card">
            <div class="card-top-row">
                <div class="accent-icon-sq sq-peach">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="9" cy="21" r="1"/>
                        <circle cx="20" cy="21" r="1"/>
                        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                    </svg>
                </div>
                <span class="card-title-text">Cost of stock sold</span>
            </div>
            <div class="card-big-value">₹{cogs:,.2f}</div>
            <div class="card-bottom-row">
                <span class="badge-gray-pill">{cogs_badge_text}</span>
                <span class="card-sublabel">{cost_ratio:.0f}% of sales</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with m_c3:
    st.markdown(f"""
        <div class="white-metric-card">
            <div class="card-top-row">
                <div class="accent-icon-sq sq-green">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2V5z"/>
                        <circle cx="7" cy="10" r="1"/>
                    </svg>
                </div>
                <span class="card-title-text">Profit on sales</span>
            </div>
            <div class="card-big-value">₹{profit:,.2f}</div>
            <div class="card-bottom-row">
                <span class="badge-green-pill">{profit_badge_text}</span>
                <span class="card-sublabel">{margin_pct:.0f}% margin</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with m_c4:
    cash_status_label = "healthy surplus" if cash_left >= 0 else "operating deficit"
    st.markdown(f"""
        <div class="white-metric-card">
            <div class="card-top-row">
                <div class="accent-icon-sq sq-amber">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/>
                        <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/>
                        <path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>
                    </svg>
                </div>
                <span class="card-title-text">Cash left over</span>
            </div>
            <div class="card-big-value">₹{cash_left:,.2f}</div>
            <div class="card-bottom-row">
                <span class="badge-green-pill">{cash_badge_text}</span>
                <span class="card-sublabel">{cash_status_label}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 6. BOTTOM VISUALIZATIONS (Dynamic SQL Computations)
# -------------------------------------------------------------
viz_c1, viz_c2 = st.columns([1.5, 1.0])

# Left Column: Sales this week Bar Chart (Live Daily SQL Query)
with viz_c1:
    with st.container(border=True):
        st.markdown("""
            <div class="viz-title">Sales this week</div>
            <div class="viz-subtitle">Sample trend · ₹ per day</div>
        """, unsafe_allow_html=True)

        weekly_trend = get_weekly_sales_trend(user_id=user_id)
        bar_days = weekly_trend["days"]
        bar_sales = weekly_trend["sales"]

        fig_sales = go.Figure(data=[
            go.Bar(
                x=bar_days,
                y=bar_sales,
                marker=dict(
                    color="#2563eb",
                    line_width=0,
                    cornerradius=4
                ),
                hovertemplate="<b>%{x}:</b> ₹%{y:,.2f}<extra></extra>"
            )
        ])

        fig_sales.update_layout(
            template="plotly_white",
            height=250,
            margin=dict(t=10, b=20, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.35,
            xaxis=dict(
                showgrid=False,
                showline=False,
                showticklabels=False,
                zeroline=False
            ),
            yaxis=dict(
                showgrid=False,
                showline=False,
                showticklabels=False,
                zeroline=False
            )
        )
        st.plotly_chart(fig_sales, use_container_width=True, config={'displayModeBar': False})

# Right Column: Stock on shelves Donut Chart (Live SQL Product Health Counts)
with viz_c2:
    with st.container(border=True):
        stock_breakdown = get_stock_health_breakdown(user_id=user_id, category=selected_cat)
        total_items = stock_breakdown["total"]
        healthy_count = stock_breakdown["healthy"]
        low_count_num = stock_breakdown["low"]
        out_count = stock_breakdown["out"]
        catalog_val = stock_breakdown["valuation"]

        st.markdown(f"""
            <div class="viz-title">Stock on shelves</div>
            <div class="viz-subtitle">₹{catalog_val:,.2f} · {total_items} items tracked</div>
        """, unsafe_allow_html=True)

        donut_sub1, donut_sub2 = st.columns([1.25, 0.95], vertical_alignment="center")

        with donut_sub1:
            if total_items > 0:
                donut_values = [healthy_count, low_count_num, out_count]
                donut_colors = ["#16a34a", "#eab308", "#dc2626"]
            else:
                donut_values = [1]
                donut_colors = ["#e2e8f0"]

            fig_donut = go.Figure(data=[go.Pie(
                labels=["Healthy", "Low", "Out"] if total_items > 0 else ["No Items"],
                values=donut_values,
                hole=0.68,
                marker=dict(colors=donut_colors),
                textinfo="none",
                hoverinfo="label+value" if total_items > 0 else "none",
                sort=False
            )])

            fig_donut.update_layout(
                annotations=[dict(
                    text=f"<b>{total_items}</b>",
                    x=0.5,
                    y=0.5,
                    font_size=26,
                    font_color="#1e293b",
                    font_family="Inter, Plus Jakarta Sans, sans-serif",
                    showarrow=False
                )],
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=250,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})

        with donut_sub2:
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; gap: 14px; font-size: 0.88rem; color: #475569; padding-top: 15px; margin-bottom: 25px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 12px; height: 12px; border-radius: 3px; background: #16a34a; display: inline-block;"></span>
                        <span style="font-weight: 500;">Healthy &middot; {healthy_count}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 12px; height: 12px; border-radius: 3px; background: #eab308; display: inline-block;"></span>
                        <span style="font-weight: 500;">Low &middot; {low_count_num}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 12px; height: 12px; border-radius: 3px; background: #dc2626; display: inline-block;"></span>
                        <span style="font-weight: 500;">Out &middot; {out_count}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Add item", icon=":material/add:", key="btn_add_item_shelf", use_container_width=False):
                st.switch_page("pages/2_Inventory.py")
