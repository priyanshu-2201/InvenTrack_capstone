"""
Inventrack - 2. Inventory Management Portal
Complete CRUD interfaces for Finished Products and Raw Materials, plus Quick Stock Adjustments.
Strictly scoped to authenticated user_id.
"""

import os
import streamlit as st
import pandas as pd
from database.db_manager import (
    get_all_products,
    get_product_by_id,
    add_product,
    update_product,
    delete_product,
    get_all_raw_materials,
    get_raw_material_by_id,
    add_raw_material,
    update_raw_material,
    delete_raw_material,
    adjust_stock
)
from components.nav import render_sidebar_navigation, render_top_header

# Page configuration
st.set_page_config(
    page_title="Inventory Control | Inventrack",
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
render_sidebar_navigation(current_page="Inventory")

# Header
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 1rem;">
        <div>
            <h1 style="margin: 0; color: #1e293b; font-size: 2rem; letter-spacing: -0.025em;">Master Inventory Management</h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748b; font-size: 0.95rem;">
                Maintain finished product catalogs, raw material formulations, unit costs in Indian Rupees (₹), and warehouse allocations.
            </p>
        </div>
        <div>
            <span class="badge badge-emerald">Live Account CRUD (INR ₹)</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# Main Navigation Tabs
tab_products, tab_materials, tab_adjust = st.tabs([
    "Finished Products Catalog",
    "Raw Materials Inventory",
    "Quick Stock Adjustment"
])


# =============================================================
# TAB 1: FINISHED PRODUCTS (Scoped to user_id)
# =============================================================
with tab_products:
    products_df = get_all_products(user_id=user_id)

    # Metrics Summary Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Product SKUs", len(products_df))
    with m2:
        total_units = int(products_df["stock_quantity"].sum()) if not products_df.empty else 0
        st.metric("Total Units in Stock", f"{total_units:,}")
    with m3:
        total_val = products_df["inventory_value"].sum() if not products_df.empty else 0
        st.metric("Total Catalog Valuation", f"₹{total_val:,.2f}")
    with m4:
        low_count = len(products_df[products_df["stock_status"] != "Healthy"]) if not products_df.empty else 0
        st.metric("Below Reorder Level", f"{low_count} SKUs", delta="-Needs Order" if low_count > 0 else "Optimal", delta_color="inverse")

    st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

    # Search & Filter
    sf_col1, sf_col2, sf_col3 = st.columns([2, 1.5, 1.5])
    with sf_col1:
        search_query = st.text_input("Search Products by SKU or Name", "", key="prod_search")
    with sf_col2:
        categories = ["All Categories"] + sorted(products_df["category"].unique().tolist()) if not products_df.empty else ["All Categories"]
        selected_cat = st.selectbox("Filter by Category", categories, key="prod_cat")
    with sf_col3:
        status_options = ["All Statuses", "Low Stock", "Out of Stock", "Healthy"]
        selected_status = st.selectbox("Filter by Stock Health", status_options, key="prod_status")

    # Filtered Table
    disp_prods = products_df.copy()
    if search_query:
        query = search_query.lower()
        disp_prods = disp_prods[
            disp_prods["name"].str.lower().str.contains(query, na=False) |
            disp_prods["sku"].str.lower().str.contains(query, na=False) |
            disp_prods["description"].str.lower().str.contains(query, na=False)
        ]
    if selected_cat != "All Categories":
        disp_prods = disp_prods[disp_prods["category"] == selected_cat]
    if selected_status != "All Statuses":
        disp_prods = disp_prods[disp_prods["stock_status"] == selected_status]

    st.markdown(f"**Showing {len(disp_prods)} of {len(products_df)} products**")
    
    # Render Table
    if not disp_prods.empty:
        table_view = disp_prods[[
            "id", "sku", "name", "category", "unit_price", "cost_price",
            "stock_quantity", "reorder_level", "stock_status", "inventory_value"
        ]].copy()
        table_view.columns = [
            "ID", "SKU", "Product Name", "Category", "Price (₹)", "Cost (₹)",
            "Stock", "Reorder Level", "Status", "Total Value (₹)"
        ]
        st.dataframe(table_view, use_container_width=True, hide_index=True)

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            csv_prods = disp_prods.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Catalog (CSV)",
                data=csv_prods,
                file_name="products_inventory.csv",
                mime="text/csv",
                key="btn_dl_prods"
            )
    else:
        st.info("No products match the filter criteria.")

    st.markdown("---")

    # Product Actions Expanders
    act_col1, act_col2 = st.columns(2)

    with act_col1:
        with st.expander("Add New Finished Product", expanded=False):
            with st.form("form_add_product", clear_on_submit=True):
                st.markdown("##### Product Details")
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    new_sku = st.text_input("Product SKU *", placeholder="e.g. SKU-VLT-115")
                    new_name = st.text_input("Product Name *", placeholder="e.g. Lavender Hydrating Toner")
                    new_cat = st.text_input("Category *", placeholder="e.g. Skincare")
                with p_col2:
                    new_price = st.number_input("Selling Price (₹) *", min_value=0.0, value=25.0, step=0.5)
                    new_cost = st.number_input("Production Cost (₹) *", min_value=0.0, value=8.0, step=0.5)
                    new_stock = st.number_input("Initial Stock Quantity *", min_value=0, value=50, step=1)
                    new_reorder = st.number_input("Reorder Threshold *", min_value=1, value=15, step=1)

                new_desc = st.text_area("Product Description", placeholder="Key ingredients, benefits, batch notes...")
                submit_add_p = st.form_submit_button("Register Product", use_container_width=True)

                if submit_add_p:
                    if not new_sku or not new_name or not new_cat:
                        st.error("Please fill in all required fields (SKU, Name, Category).")
                    else:
                        success, msg = add_product(
                            user_id=user_id,
                            sku=new_sku, name=new_name, category=new_cat,
                            unit_price=new_price, cost_price=new_cost,
                            stock_quantity=new_stock, reorder_level=new_reorder,
                            description=new_desc
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    with act_col2:
        with st.expander("Edit Existing Product", expanded=False):
            if not products_df.empty:
                prod_choices = {f"{row['name']} ({row['sku']})": row['id'] for _, row in products_df.iterrows()}
                selected_prod_label = st.selectbox("Select Product to Edit", list(prod_choices.keys()), key="edit_prod_select")
                selected_prod_id = prod_choices[selected_prod_label]
                prod_data = get_product_by_id(product_id=selected_prod_id, user_id=user_id)

                if prod_data:
                    with st.form("form_edit_product"):
                        st.markdown(f"##### Modifying ID #{prod_data['id']}: {prod_data['name']}")
                        ep_c1, ep_c2 = st.columns(2)
                        with ep_c1:
                            edit_sku = st.text_input("SKU", value=prod_data["sku"])
                            edit_name = st.text_input("Product Name", value=prod_data["name"])
                            edit_cat = st.text_input("Category", value=prod_data["category"])
                        with ep_c2:
                            edit_price = st.number_input("Selling Price (₹)", min_value=0.0, value=float(prod_data["unit_price"]), step=0.5)
                            edit_cost = st.number_input("Cost Price (₹)", min_value=0.0, value=float(prod_data["cost_price"]), step=0.5)
                            edit_stock = st.number_input("Stock Quantity", min_value=0, value=int(prod_data["stock_quantity"]), step=1)
                            edit_reorder = st.number_input("Reorder Threshold", min_value=1, value=int(prod_data["reorder_level"]), step=1)

                        edit_desc = st.text_area("Description", value=prod_data["description"] or "")
                        submit_edit_p = st.form_submit_button("Save Changes", use_container_width=True)

                        if submit_edit_p:
                            success, msg = update_product(
                                product_id=selected_prod_id,
                                user_id=user_id,
                                sku=edit_sku, name=edit_name, category=edit_cat,
                                unit_price=edit_price, cost_price=edit_cost,
                                stock_quantity=edit_stock, reorder_level=edit_reorder,
                                description=edit_desc
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.info("No products available to edit.")

    # Delete Section
    with st.expander("Delete a Product", expanded=False):
        if not products_df.empty:
            del_prod_choices = {f"{row['name']} ({row['sku']}) [ID: {row['id']}]": row['id'] for _, row in products_df.iterrows()}
            prod_to_delete = st.selectbox("Select Product to Permanently Remove", list(del_prod_choices.keys()), key="del_prod_sel")
            target_del_id = del_prod_choices[prod_to_delete]

            col_btn, col_warn = st.columns([1, 3])
            with col_btn:
                confirm_del = st.button("Confirm Delete", type="primary", key="btn_del_prod")
            with col_warn:
                st.warning("⚠️ Deleting a product is irreversible and removes it from your catalog.")

            if confirm_del:
                success, msg = delete_product(product_id=target_del_id, user_id=user_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# =============================================================
# TAB 2: RAW MATERIALS (Scoped to user_id)
# =============================================================
with tab_materials:
    materials_df = get_all_raw_materials(user_id=user_id)

    # Raw Materials Metrics
    rm1, rm2, rm3 = st.columns(3)
    with rm1:
        st.metric("Total Raw Materials", len(materials_df))
    with rm2:
        mat_val = materials_df["total_valuation"].sum() if not materials_df.empty else 0
        st.metric("Raw Materials Valuation", f"₹{mat_val:,.2f}")
    with rm3:
        low_rm = len(materials_df[materials_df["stock_status"] != "Healthy"]) if not materials_df.empty else 0
        st.metric("Materials Low / Depleted", f"{low_rm} items", delta="-Action Needed" if low_rm > 0 else "Sufficient", delta_color="inverse")

    st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

    # Search & Filter
    rf_col1, rf_col2 = st.columns([2, 1])
    with rf_col1:
        search_mat = st.text_input("Search Raw Materials by Code, Name or Supplier", "", key="rm_search")
    with rf_col2:
        rm_categories = ["All Categories"] + sorted(materials_df["category"].unique().tolist()) if not materials_df.empty else ["All Categories"]
        selected_rm_cat = st.selectbox("Filter by Category", rm_categories, key="rm_cat")

    disp_materials = materials_df.copy()
    if search_mat:
        q_m = search_mat.lower()
        disp_materials = disp_materials[
            disp_materials["name"].str.lower().str.contains(q_m, na=False) |
            disp_materials["code"].str.lower().str.contains(q_m, na=False) |
            disp_materials["supplier_name"].str.lower().str.contains(q_m, na=False)
        ]
    if selected_rm_cat != "All Categories":
        disp_materials = disp_materials[disp_materials["category"] == selected_rm_cat]

    st.markdown(f"**Showing {len(disp_materials)} of {len(materials_df)} raw materials**")

    # Render Materials Table
    if not disp_materials.empty:
        table_mat = disp_materials[[
            "id", "code", "name", "category", "unit", "unit_cost",
            "stock_quantity", "reorder_level", "supplier_name", "stock_status", "total_valuation"
        ]].copy()
        table_mat.columns = [
            "ID", "Code", "Material Name", "Category", "Unit", "Cost/Unit (₹)",
            "Stock Qty", "Min Level", "Primary Supplier", "Status", "Valuation (₹)"
        ]
        st.dataframe(table_mat, use_container_width=True, hide_index=True)

        col_dlm, _ = st.columns([1, 4])
        with col_dlm:
            csv_mats = disp_materials.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Raw Materials (CSV)",
                data=csv_mats,
                file_name="raw_materials_inventory.csv",
                mime="text/csv",
                key="btn_dl_mats"
            )
    else:
        st.info("No raw materials match the query.")

    st.markdown("---")

    # Raw Material Actions Expanders
    rm_act1, rm_act2 = st.columns(2)

    with rm_act1:
        with st.expander("Register New Raw Material", expanded=False):
            with st.form("form_add_material", clear_on_submit=True):
                st.markdown("##### Raw Material Specifications")
                m_c1, m_c2 = st.columns(2)
                with m_c1:
                    m_code = st.text_input("Material Code *", placeholder="e.g. RM-ESS-11")
                    m_name = st.text_input("Material Name *", placeholder="e.g. Peppermint Essential Oil")
                    m_cat = st.text_input("Category *", placeholder="e.g. Essential Oils")
                    m_unit = st.selectbox("Unit of Measure *", ["Units", "Liters", "Kilograms", "Grams", "Meters", "Boxes"])
                with m_c2:
                    m_cost = st.number_input("Unit Cost (₹) *", min_value=0.0, value=15.0, step=0.5)
                    m_stock = st.number_input("Current Stock *", min_value=0.0, value=25.0, step=1.0)
                    m_reorder = st.number_input("Reorder Threshold *", min_value=0.0, value=10.0, step=1.0)
                    m_supp = st.text_input("Supplier Name", placeholder="e.g. Botanical Bio Supply Co.")

                submit_add_m = st.form_submit_button("Register Material", use_container_width=True)

                if submit_add_m:
                    if not m_code or not m_name or not m_cat:
                        st.error("Please fill in required fields (Code, Name, Category).")
                    else:
                        success, msg = add_raw_material(
                            user_id=user_id,
                            code=m_code, name=m_name, category=m_cat,
                            unit=m_unit, unit_cost=m_cost, stock_quantity=m_stock,
                            reorder_level=m_reorder, supplier_name=m_supp
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    with rm_act2:
        with st.expander("Update Raw Material", expanded=False):
            if not materials_df.empty:
                mat_choices = {f"{row['name']} ({row['code']})": row['id'] for _, row in materials_df.iterrows()}
                selected_mat_label = st.selectbox("Select Raw Material to Edit", list(mat_choices.keys()), key="edit_mat_sel")
                selected_mat_id = mat_choices[selected_mat_label]
                mat_data = get_raw_material_by_id(material_id=selected_mat_id, user_id=user_id)

                if mat_data:
                    with st.form("form_edit_material"):
                        st.markdown(f"##### Modifying ID #{mat_data['id']}: {mat_data['name']}")
                        em_c1, em_c2 = st.columns(2)
                        with em_c1:
                            em_code = st.text_input("Code", value=mat_data["code"])
                            em_name = st.text_input("Material Name", value=mat_data["name"])
                            em_cat = st.text_input("Category", value=mat_data["category"])
                            unit_options = ["Units", "Liters", "Kilograms", "Grams", "Meters", "Boxes"]
                            curr_unit_idx = unit_options.index(mat_data["unit"]) if mat_data["unit"] in unit_options else 0
                            em_unit = st.selectbox("Unit", unit_options, index=curr_unit_idx)
                        with em_c2:
                            em_cost = st.number_input("Unit Cost (₹)", min_value=0.0, value=float(mat_data["unit_cost"]), step=0.5)
                            em_stock = st.number_input("Stock Quantity", min_value=0.0, value=float(mat_data["stock_quantity"]), step=1.0)
                            em_reorder = st.number_input("Reorder Level", min_value=0.0, value=float(mat_data["reorder_level"]), step=1.0)
                            em_supp = st.text_input("Supplier", value=mat_data["supplier_name"] or "")

                        submit_edit_m = st.form_submit_button("Update Specifications", use_container_width=True)

                        if submit_edit_m:
                            success, msg = update_raw_material(
                                material_id=selected_mat_id,
                                user_id=user_id,
                                code=em_code, name=em_name, category=em_cat,
                                unit=em_unit, unit_cost=em_cost,
                                stock_quantity=em_stock, reorder_level=em_reorder,
                                supplier_name=em_supp
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.info("No raw materials available to edit.")

    # Delete Material Section
    with st.expander("Delete Raw Material", expanded=False):
        if not materials_df.empty:
            del_mat_choices = {f"{row['name']} ({row['code']}) [ID: {row['id']}]": row['id'] for _, row in materials_df.iterrows()}
            mat_to_delete = st.selectbox("Select Raw Material to Permanently Delete", list(del_mat_choices.keys()), key="del_mat_sel")
            target_del_mat_id = del_mat_choices[mat_to_delete]

            col_m_del, col_m_warn = st.columns([1, 3])
            with col_m_del:
                confirm_del_m = st.button("Confirm Delete", type="primary", key="btn_del_mat")
            with col_m_warn:
                st.warning("⚠️ Deleting a raw material is irreversible.")

            if confirm_del_m:
                success, msg = delete_raw_material(material_id=target_del_mat_id, user_id=user_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# =============================================================
# TAB 3: QUICK STOCK ADJUSTMENT (Scoped to user_id)
# =============================================================
with tab_adjust:
    st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.2rem;">
            <h3 style="margin-top: 0; color: #1e293b;">Direct Stock Adjustment &amp; Audit Rebalancing</h3>
            <p style="color: #64748b; font-size: 0.95rem; margin-bottom: 0;">
                Quickly reconcile physical stock discrepancies, scrap expired batches, or log incoming manual replenishments.
                Every adjustment automatically creates an audit entry in the transaction ledger.
            </p>
        </div>
    """, unsafe_allow_html=True)

    adj_c1, adj_c2 = st.columns([1, 1])

    with adj_c1:
        adj_item_type = st.radio("Select Item Category", ["Finished Product", "Raw Material"], horizontal=True)

        if adj_item_type == "Finished Product":
            prods = get_all_products(user_id=user_id)
            if not prods.empty:
                adj_choices = {f"{r['name']} ({r['sku']}) - Stock: {r['stock_quantity']}": r['id'] for _, r in prods.iterrows()}
                selected_item_label = st.selectbox("Choose Product", list(adj_choices.keys()))
                adj_item_id = adj_choices[selected_item_label]
            else:
                st.warning("No products available in your account.")
                adj_item_id = None
        else:
            mats = get_all_raw_materials(user_id=user_id)
            if not mats.empty:
                adj_choices = {f"{r['name']} ({r['code']}) - Stock: {r['stock_quantity']} {r['unit']}": r['id'] for _, r in mats.iterrows()}
                selected_item_label = st.selectbox("Choose Raw Material", list(adj_choices.keys()))
                adj_item_id = adj_choices[selected_item_label]
            else:
                st.warning("No raw materials available in your account.")
                adj_item_id = None

    with adj_c2:
        adj_mode = st.radio("Adjustment Action", ["Increase Stock (+)", "Decrease / Scrap (-)"], horizontal=True)
        adj_amount = st.number_input("Adjustment Quantity", min_value=0.1, value=5.0, step=1.0)
        adj_reason = st.text_input("Audit Reason / Memo", placeholder="e.g. Physical count correction, damaged batch, QA sampling")

        delta = adj_amount if "Increase" in adj_mode else -adj_amount

        st.markdown(f"**Applied Adjustment:** `{' ' if delta > 0 else ''}{delta}` units")

        if st.button("Apply Stock Adjustment", use_container_width=True, type="primary"):
            if not adj_item_id:
                st.error("Please select a valid item.")
            elif not adj_reason.strip():
                st.warning("Please provide an audit reason for tracking purposes.")
            else:
                type_code = "PRODUCT" if adj_item_type == "Finished Product" else "RAW_MATERIAL"
                success, msg = adjust_stock(
                    user_id=user_id,
                    item_type=type_code,
                    item_id=adj_item_id,
                    delta_quantity=delta,
                    reason=adj_reason
                )
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
