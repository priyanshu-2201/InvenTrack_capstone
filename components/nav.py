"""
Inventrack - Global Navigation Component (Header & Top Page Tabs)
Matches the exact pixel-aligned SaaS design reference:
1. Global Top Header: Logo, Active Search items with '/' shortcut, help icon, interactive Profile st.popover
2. Top Navigation Tabs: Dashboard, Inventory (with dynamic '{count} low' badge if count > 0),
   Transactions, Data import, and Live status 'Live · 48 KB saved'.
3. 100% Native, reliable interactive navigation routing via st.switch_page.
"""

import os
import streamlit as st
import pandas as pd
from database.db_manager import (
    get_user_by_id,
    get_low_stock_items,
    search_products_and_transactions,
    DB_PATH
)

PAGE_ROUTES = {
    "Dashboard": "app.py",
    "Inventory": "pages/2_Inventory.py",
    "Transactions": "pages/3_Transactions.py",
    "Data import": "pages/0_Data_Import.py",
    "Data Import": "pages/0_Data_Import.py",
}


def render_top_header(username: str = None):
    """
    Renders the global top header bar with:
    1. Logo & App Title (Inventrack)
    2. Active st.text_input search bar (keyed as 'search_query', placeholder 'Search items... (Press / to focus)')
    3. Dynamic search results table modal directly beneath the search row.
    4. Help icon and interactive profile st.popover with user info & Log out.
    """
    active_user = username or st.session_state.get("username", "")
    user_id = st.session_state.get("user_id")

    if not active_user and user_id:
        rec = get_user_by_id(user_id)
        if rec and rec.get("username"):
            active_user = rec["username"]
            st.session_state["username"] = active_user

    avatar_initial = active_user.strip()[0].upper() if active_user and active_user.strip() else "K"

    # Top Header Container
    st.markdown('<div class="top-bar-container top-nav-bar-wrapper">', unsafe_allow_html=True)
    c_left, c_center, c_right = st.columns([1.4, 3.8, 1.2], vertical_alignment="center")

    with c_left:
        st.markdown("""
            <div class="top-header-left">
                <div class="top-logo-box">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="3" y="3" width="18" height="18" rx="4" stroke="white" stroke-width="2.2"/>
                        <path d="M3 9H21" stroke="white" stroke-width="2.2"/>
                        <path d="M9 13H15" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <span class="top-logo-title">Inventrack</span>
            </div>
        """, unsafe_allow_html=True)

    with c_center:
        st.text_input(
            "Search items",
            placeholder="Search items... (Press / to focus)",
            key="search_query",
            label_visibility="collapsed"
        )

    with c_right:
        col_help, col_pop = st.columns([0.45, 0.55], vertical_alignment="center")
        with col_help:
            st.markdown('<div class="top-help-icon" title="Help &amp; Documentation">?</div>', unsafe_allow_html=True)
        with col_pop:
            with st.popover(avatar_initial, key="user_profile_popover"):
                st.markdown(f"**User:** {active_user}")
                st.caption(f"Account: Tenant #{user_id} · Administrator")
                st.markdown("**Platform:** Inventrack B2B SaaS")
                st.divider()
                if st.button("🚪 Log out", key="popover_logout", use_container_width=True):
                    st.session_state.clear()
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # Global keyboard shortcut for '/' to focus search input
    st.markdown("""
        <script>
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                const searchEl = document.querySelector('.st-key-search_query input');
                if (searchEl) searchEl.focus();
            }
        });
        </script>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # ACTIVE SEARCH RESULTS MODAL/DROPDOWN
    # Appears directly beneath search row when search_query is typed
    # -------------------------------------------------------------
    query = st.session_state.get("search_query", "").strip()
    if query and user_id:
        results = search_products_and_transactions(user_id=user_id, query=query)
        prods = results.get("products", [])
        txns = results.get("transactions", [])

        with st.container(border=True):
            r_col1, r_col2 = st.columns([4, 1], vertical_alignment="center")
            with r_col1:
                st.markdown(
                    f"🔍 **Search results for:** `{query}` &nbsp;·&nbsp; "
                    f"<span style='color: #64748b;'>{len(prods)} product(s), {len(txns)} transaction(s) found</span>",
                    unsafe_allow_html=True
                )
            with r_col2:
                if st.button("✕ Close Results", key="btn_close_search_res", use_container_width=True):
                    st.session_state["search_query"] = ""
                    st.rerun()

            if prods:
                df_prods = pd.DataFrame(prods)
                df_disp = pd.DataFrame()
                if "sku" in df_prods.columns:
                    df_disp["SKU"] = df_prods["sku"]
                if "item_name" in df_prods.columns:
                    df_disp["Item Name"] = df_prods["item_name"]
                if "current_stock" in df_prods.columns:
                    df_disp["Current Stock"] = df_prods["current_stock"].apply(lambda s: f"{s:,} units")
                if "price" in df_prods.columns:
                    df_disp["Price"] = df_prods["price"].apply(lambda p: f"₹{p:,.2f}")
                if "category" in df_prods.columns:
                    df_disp["Category"] = df_prods["category"]

                st.dataframe(df_disp, use_container_width=True, hide_index=True)
            else:
                st.info(f"No products found matching '{query}'.")

            if txns:
                with st.expander(f"Matching Transactions ({len(txns)})", expanded=False):
                    df_tx = pd.DataFrame(txns)
                    df_tx_disp = pd.DataFrame({
                        "Code": df_tx["transaction_code"],
                        "Type": df_tx["transaction_type"],
                        "Party": df_tx["party_name"],
                        "Amount": df_tx["total_amount"].apply(lambda a: f"₹{a:,.2f}"),
                        "Date": df_tx["transaction_date"]
                    })
                    st.dataframe(df_tx_disp, use_container_width=True, hide_index=True)

        st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)


def render_sidebar_navigation(current_page="Dashboard", low_stock_count=0):
    """
    Renders the horizontal top tabs navigation bar across:
    - Dashboard
    - Inventory (with '{count} low' badge if low stock > 0)
    - Transactions
    - Data import
    Using native, reliable Streamlit buttons with automatic page switching and active tab pill styling.
    """
    if low_stock_count is None or low_stock_count == 0:
        user_id = st.session_state.get("user_id")
        if user_id:
            try:
                low_items = get_low_stock_items(user_id)
                low_stock_count = len(low_items)
            except Exception:
                low_stock_count = 0
        else:
            low_stock_count = 0

    cur_clean = (current_page or "Dashboard").lower().replace(" ", "").replace("_", "")
    if "dashboard" in cur_clean:
        active_slug = "dashboard"
    elif "inventory" in cur_clean:
        active_slug = "inventory"
    elif "transaction" in cur_clean:
        active_slug = "transactions"
    elif "import" in cur_clean:
        active_slug = "data_import"
    else:
        active_slug = "dashboard"

    st.session_state['active_page'] = current_page

    # Dynamic CSS injection ensuring the active tab button has the soft blue SaaS fill
    st.markdown(f"""
    <style>
    .st-key-top_tab_{active_slug} button {{
        background-color: #dbeafe !important;
        background: #dbeafe !important;
        color: #1d4ed8 !important;
        border: 1px solid #bfdbfe !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 2px rgba(37, 99, 235, 0.08) !important;
    }}
    .st-key-top_tab_{active_slug} button * {{
        color: #1d4ed8 !important;
        font-weight: 600 !important;
    }}
    .st-key-top_tab_{active_slug} button span[data-testid="stIconMaterial"] {{
        color: #2563eb !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # Horizontal Top Navigation Tabs Bar
    col_dash, col_inv, col_trans, col_data, col_space, col_status = st.columns(
        [1.2, 1.5, 1.4, 1.4, 3.2, 1.5],
        vertical_alignment="center"
    )

    with col_dash:
        if st.button("Dashboard", key="top_tab_dashboard", icon=":material/grid_view:", use_container_width=True):
            if active_slug != "dashboard":
                st.session_state['active_page'] = "Dashboard"
                try:
                    st.switch_page("app.py")
                except Exception:
                    st.rerun()
            else:
                st.rerun()

    with col_inv:
        badge_str = f" :red[**{low_stock_count} low**]" if low_stock_count > 0 else ""
        if st.button(f"Inventory{badge_str}", key="top_tab_inventory", icon=":material/inventory_2:", use_container_width=True):
            if active_slug != "inventory":
                st.session_state['active_page'] = "Inventory"
                try:
                    st.switch_page("pages/2_Inventory.py")
                except Exception:
                    st.rerun()
            else:
                st.rerun()

    with col_trans:
        if st.button("Transactions", key="top_tab_transactions", icon=":material/receipt_long:", use_container_width=True):
            if active_slug != "transactions":
                st.session_state['active_page'] = "Transactions"
                try:
                    st.switch_page("pages/3_Transactions.py")
                except Exception:
                    st.rerun()
            else:
                st.rerun()

    with col_data:
        if st.button("Data import", key="top_tab_data_import", icon=":material/file_download:", use_container_width=True):
            if active_slug != "data_import":
                st.session_state['active_page'] = "Data Import"
                try:
                    st.switch_page("pages/0_Data_Import.py")
                except Exception:
                    st.rerun()
            else:
                st.rerun()

    with col_status:
        st.markdown("""
            <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding-right: 6px; height: 38px;">
                <span style="height: 8px; width: 8px; background-color: #22c55e; border-radius: 50%; display: inline-block;"></span>
                <span style="font-size: 13px; color: #64748b; font-weight: 500; white-space: nowrap;">Live · 48 KB saved</span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="top-nav-divider"></div>', unsafe_allow_html=True)


# Backwards compatibility aliases
render_top_navbar = render_sidebar_navigation
render_top_navigation = render_sidebar_navigation
render_tabs_navigation = render_sidebar_navigation
