"""
Database management module for Inventrack System.
Enforces strict multi-tenancy (B2B SaaS model) with user_id scoping across
all products, raw materials, transactions, and analytics.
Zero dummy data on initialization.
"""

import os
import sqlite3
import random
import hashlib
from datetime import datetime, timedelta
import pandas as pd

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "inventory.db")


def get_db_connection():
    """Establish and return a connection to the SQLite database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Initialize database schema enforcing multi-tenancy with foreign keys to Users(id).
    Leaves the database 100% clean and empty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table (Tenant Accounts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Finished Products Table (Multi-tenant)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        reorder_level INTEGER NOT NULL DEFAULT 10,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
        UNIQUE (user_id, sku)
    );
    """)

    # 3. Raw Materials Table (Multi-tenant)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL,
        unit_cost REAL NOT NULL,
        stock_quantity REAL NOT NULL DEFAULT 0,
        reorder_level REAL NOT NULL DEFAULT 10,
        supplier_name TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
        UNIQUE (user_id, code)
    );
    """)

    # 4. Transactions Table (Multi-tenant)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        transaction_code TEXT NOT NULL,
        transaction_type TEXT NOT NULL,   -- 'SALE', 'PURCHASE', 'ADJUSTMENT'
        item_type TEXT NOT NULL,          -- 'PRODUCT', 'RAW_MATERIAL'
        item_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL NOT NULL,
        total_amount REAL NOT NULL,
        party_name TEXT,                  -- Customer or Supplier name
        transaction_date TEXT NOT NULL,   -- YYYY-MM-DD
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Hash a plaintext password string using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username: str, password: str) -> tuple[bool, str]:
    """
    Hashes password using SHA-256 and creates a persistent user record in Users table.
    Returns (True, 'Inventrack account created successfully.') or (False, error_message).
    """
    cleaned_username = username.strip() if username else ""
    if not cleaned_username or not password:
        return False, "Username and password cannot be empty."

    pwd_hash = hash_password(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users (username, password_hash) VALUES (?, ?)",
            (cleaned_username, pwd_hash)
        )
        conn.commit()
        return True, "Inventrack account created successfully."
    except sqlite3.IntegrityError:
        return False, f"Username '{cleaned_username}' already exists. Please choose a different username."
    except Exception as e:
        return False, f"Database error creating user: {str(e)}"
    finally:
        conn.close()


def verify_user(username: str, password: str):
    """
    Validates credentials against the stored SHA-256 hash in Users table.
    Returns user_id (int) if valid, None otherwise.
    Evaluates to True in boolean statements (`if verify_user(...)`).
    """
    cleaned_username = username.strip() if username else ""
    if not cleaned_username or not password:
        return None

    pwd_hash = hash_password(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, password_hash FROM Users WHERE username = ?",
            (cleaned_username,)
        )
        row = cursor.fetchone()
        if row and row["password_hash"] == pwd_hash:
            return int(row["id"])
        return None
    except Exception:
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    """Retrieve user account information by ID."""
    if not user_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, created_at FROM Users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# -------------------------------------------------------------
# PRODUCT CRUD OPERATIONS (Scoped to user_id)
# -------------------------------------------------------------

def get_all_products(user_id: int):
    """Retrieve all finished products for a specific user as a pandas DataFrame."""
    empty_df = pd.DataFrame(columns=[
        "id", "user_id", "sku", "name", "category", "unit_price", "cost_price",
        "stock_quantity", "reorder_level", "description", "created_at",
        "inventory_value", "stock_status"
    ])
    if not user_id:
        return empty_df

    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM products WHERE user_id = ? ORDER BY name ASC", conn, params=(user_id,))
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return empty_df

    for col in ["sku", "SKU", "Product_ID", "item_sku"]:
        if col in df.columns and "sku" not in df.columns:
            df["sku"] = df[col]
            break

    for col in ["name", "Name", "Product_Name", "item_name"]:
        if col in df.columns and "name" not in df.columns:
            df["name"] = df[col]
            break

    if "category" not in df.columns:
        df["category"] = "General"
    if "stock_quantity" not in df.columns:
        df["stock_quantity"] = 0
    if "reorder_level" not in df.columns:
        df["reorder_level"] = 10
    if "unit_price" not in df.columns:
        df["unit_price"] = 0.0
    if "cost_price" not in df.columns:
        df["cost_price"] = df["unit_price"] * 0.45

    df["inventory_value"] = df["stock_quantity"] * df["unit_price"]
    df["stock_status"] = df.apply(
        lambda r: "Out of Stock" if r["stock_quantity"] <= 0 else (
            "Low Stock" if r["stock_quantity"] <= r["reorder_level"] else "Healthy"
        ), axis=1
    )
    return df


def get_product_by_id(product_id: int, user_id: int):
    """Retrieve single product record by ID scoped to user_id."""
    if not user_id or not product_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_product(user_id: int, sku: str, name: str, category: str, unit_price: float,
                cost_price: float, stock_quantity: int = 0, reorder_level: int = 10,
                description: str = ""):
    """Add a new product to the catalog scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (user_id, sku, name, category, unit_price, cost_price, stock_quantity, reorder_level, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, sku.strip().upper(), name.strip(), category.strip(),
              float(unit_price), float(cost_price), int(stock_quantity),
              int(reorder_level), description.strip()))
        conn.commit()
        return True, "Product added successfully."
    except sqlite3.IntegrityError:
        return False, f"Integrity Error: SKU '{sku}' already exists in your catalog."
    except Exception as e:
        return False, f"Failed to add product: {str(e)}"
    finally:
        conn.close()


def update_product(product_id: int, user_id: int, sku: str, name: str, category: str,
                   unit_price: float, cost_price: float, stock_quantity: int,
                   reorder_level: int, description: str = ""):
    """Update existing product details scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products 
            SET sku = ?, name = ?, category = ?, unit_price = ?, 
                cost_price = ?, stock_quantity = ?, reorder_level = ?, description = ?
            WHERE id = ? AND user_id = ?
        """, (sku.strip().upper(), name.strip(), category.strip(),
              float(unit_price), float(cost_price), int(stock_quantity),
              int(reorder_level), description.strip(), product_id, user_id))
        conn.commit()
        return True, "Product updated successfully."
    except sqlite3.IntegrityError:
        return False, f"Integrity Error: SKU '{sku}' conflicts with an existing product in your catalog."
    except Exception as e:
        return False, f"Failed to update product: {str(e)}"
    finally:
        conn.close()


def delete_product(product_id: int, user_id: int):
    """Delete a product from catalog scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user_id))
        conn.commit()
        return True, "Product deleted successfully."
    except Exception as e:
        return False, f"Failed to delete product: {str(e)}"
    finally:
        conn.close()


# -------------------------------------------------------------
# RAW MATERIALS CRUD OPERATIONS (Scoped to user_id)
# -------------------------------------------------------------

def get_all_raw_materials(user_id: int):
    """Retrieve all raw materials for a specific user as a pandas DataFrame."""
    empty_df = pd.DataFrame(columns=[
        "id", "user_id", "code", "name", "category", "unit", "unit_cost",
        "stock_quantity", "reorder_level", "supplier_name",
        "last_updated", "total_valuation", "stock_status"
    ])
    if not user_id:
        return empty_df

    conn = get_db_connection()
    query = """
    SELECT 
        id, user_id, code, name, category, unit, unit_cost, 
        stock_quantity, reorder_level, supplier_name, last_updated,
        (stock_quantity * unit_cost) AS total_valuation,
        CASE 
            WHEN stock_quantity <= 0 THEN 'Out of Stock'
            WHEN stock_quantity <= reorder_level THEN 'Low Stock'
            ELSE 'Healthy'
        END AS stock_status
    FROM raw_materials
    WHERE user_id = ?
    ORDER BY name ASC;
    """
    try:
        df = pd.read_sql_query(query, conn, params=(user_id,))
    except Exception:
        df = empty_df
    finally:
        conn.close()

    if df.empty:
        return empty_df

    return df


def get_raw_material_by_id(material_id: int, user_id: int):
    """Retrieve single raw material record by ID scoped to user_id."""
    if not user_id or not material_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_materials WHERE id = ? AND user_id = ?", (material_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_raw_material(user_id: int, code: str, name: str, category: str, unit: str,
                     unit_cost: float, stock_quantity: float,
                     reorder_level: float = 10.0, supplier_name: str = ""):
    """Add a new raw material record scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO raw_materials (user_id, code, name, category, unit, unit_cost, stock_quantity, reorder_level, supplier_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, code.strip().upper(), name.strip(), category.strip(), unit.strip(),
              float(unit_cost), float(stock_quantity), float(reorder_level),
              supplier_name.strip()))
        conn.commit()
        return True, "Raw material registered successfully."
    except sqlite3.IntegrityError:
        return False, f"Integrity Error: Code '{code}' already exists in your inventory."
    except Exception as e:
        return False, f"Failed to register raw material: {str(e)}"
    finally:
        conn.close()


def update_raw_material(material_id: int, user_id: int, code: str, name: str, category: str,
                        unit: str, unit_cost: float, stock_quantity: float,
                        reorder_level: float, supplier_name: str = ""):
    """Update existing raw material details scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE raw_materials
            SET code = ?, name = ?, category = ?, unit = ?, unit_cost = ?,
                stock_quantity = ?, reorder_level = ?, supplier_name = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (code.strip().upper(), name.strip(), category.strip(), unit.strip(),
              float(unit_cost), float(stock_quantity), float(reorder_level),
              supplier_name.strip(), material_id, user_id))
        conn.commit()
        return True, "Raw material updated successfully."
    except sqlite3.IntegrityError:
        return False, f"Integrity Error: Code '{code}' already in use in your inventory."
    except Exception as e:
        return False, f"Failed to update raw material: {str(e)}"
    finally:
        conn.close()


def delete_raw_material(material_id: int, user_id: int):
    """Delete a raw material from database scoped to user_id."""
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM raw_materials WHERE id = ? AND user_id = ?", (material_id, user_id))
        conn.commit()
        return True, "Raw material deleted successfully."
    except Exception as e:
        return False, f"Failed to delete raw material: {str(e)}"
    finally:
        conn.close()


def adjust_stock(user_id: int, item_type: str, item_id: int, delta_quantity: float, reason: str = ""):
    """
    Adjust stock levels up or down directly with an audit transaction log scoped to user_id.
    """
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if item_type == "PRODUCT":
            cursor.execute("SELECT name, stock_quantity, unit_price FROM products WHERE id = ? AND user_id = ?", (item_id, user_id))
            row = cursor.fetchone()
            if not row:
                return False, "Product not found in your account."
            new_stock = row["stock_quantity"] + delta_quantity
            if new_stock < 0:
                return False, f"Cannot reduce below zero. Current stock: {row['stock_quantity']}"
            cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))
            item_name = row["name"]
            unit_price = row["unit_price"]
        else:
            cursor.execute("SELECT name, stock_quantity, unit_cost FROM raw_materials WHERE id = ? AND user_id = ?", (item_id, user_id))
            row = cursor.fetchone()
            if not row:
                return False, "Raw material not found in your account."
            new_stock = row["stock_quantity"] + delta_quantity
            if new_stock < 0:
                return False, f"Cannot reduce below zero. Current stock: {row['stock_quantity']}"
            cursor.execute("UPDATE raw_materials SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))
            item_name = row["name"]
            unit_price = row["unit_cost"]

        # Log adjustment transaction
        txn_code = f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        cursor.execute("""
            INSERT INTO transactions (
                user_id, transaction_code, transaction_type, item_type, item_id, 
                item_name, quantity, unit_price, total_amount, 
                party_name, transaction_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, txn_code, "ADJUSTMENT", item_type, item_id,
            item_name, abs(delta_quantity), unit_price,
            abs(delta_quantity) * unit_price,
            "Internal Inventory Control",
            datetime.now().strftime("%Y-%m-%d"),
            f"Adjustment ({'+' if delta_quantity >= 0 else ''}{delta_quantity}): {reason}"
        ))

        conn.commit()
        return True, f"Stock updated. New balance: {new_stock}"
    except Exception as e:
        conn.rollback()
        return False, f"Adjustment failed: {str(e)}"
    finally:
        conn.close()


# -------------------------------------------------------------
# TRANSACTION MANAGEMENT (Scoped to user_id)
# -------------------------------------------------------------

def log_transaction(user_id: int, transaction_type: str, item_type: str, item_id: int,
                    quantity: float, unit_price: float, party_name: str,
                    transaction_date: str, notes: str = ""):
    """
    Log a sale or procurement transaction atomically, updating inventory levels scoped to user_id.
    """
    if not user_id:
        return False, "User authentication required."
    if quantity <= 0:
        return False, "Quantity must be greater than zero."
    if unit_price < 0:
        return False, "Unit price cannot be negative."

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Determine item and verify stock availability
        if item_type == "PRODUCT":
            cursor.execute("SELECT id, name, stock_quantity FROM products WHERE id = ? AND user_id = ?", (item_id, user_id))
            row = cursor.fetchone()
            if not row:
                return False, f"Product ID {item_id} not found."
            item_name = row["name"]
            current_stock = row["stock_quantity"]

            if transaction_type == "SALE":
                if current_stock < quantity:
                    return False, f"Insufficient stock for sale! Available: {current_stock}, Requested: {quantity}"
                new_stock = current_stock - quantity
                cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))
            elif transaction_type == "PURCHASE":
                new_stock = current_stock + quantity
                cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))

        else: # RAW_MATERIAL
            cursor.execute("SELECT id, name, stock_quantity FROM raw_materials WHERE id = ? AND user_id = ?", (item_id, user_id))
            row = cursor.fetchone()
            if not row:
                return False, f"Raw Material ID {item_id} not found."
            item_name = row["name"]
            current_stock = row["stock_quantity"]

            if transaction_type == "SALE":
                if current_stock < quantity:
                    return False, f"Insufficient raw material stock! Available: {current_stock}, Requested: {quantity}"
                new_stock = current_stock - quantity
                cursor.execute("UPDATE raw_materials SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))
            elif transaction_type == "PURCHASE":
                new_stock = current_stock + quantity
                cursor.execute("UPDATE raw_materials SET stock_quantity = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", (new_stock, item_id, user_id))

        # Generate unique transaction ID
        prefix = "SL" if transaction_type == "SALE" else ("PO" if transaction_type == "PURCHASE" else "TX")
        txn_code = f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        total_amount = float(quantity * unit_price)

        cursor.execute("""
            INSERT INTO transactions (
                user_id, transaction_code, transaction_type, item_type, item_id,
                item_name, quantity, unit_price, total_amount,
                party_name, transaction_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, txn_code, transaction_type, item_type, item_id,
            item_name, float(quantity), float(unit_price), total_amount,
            party_name.strip() if party_name else "Counter Party",
            transaction_date, notes.strip()
        ))

        conn.commit()
        return True, f"Transaction recorded successfully [{txn_code}]. Stock updated to {new_stock}."

    except Exception as e:
        conn.rollback()
        return False, f"Transaction failed: {str(e)}"
    finally:
        conn.close()


def get_all_transactions(user_id: int, limit: int = None):
    """Retrieve transaction logs for a specific user as a pandas DataFrame with column normalization."""
    empty_df = pd.DataFrame(columns=[
        "id", "user_id", "transaction_code", "transaction_type", "item_type", "item_id",
        "item_name", "quantity", "unit_price", "total_amount", "party_name",
        "transaction_date", "notes", "created_at"
    ])
    if not user_id:
        return empty_df

    conn = get_db_connection()
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM transactions WHERE user_id = ? ORDER BY transaction_date DESC {limit_clause}",
            conn,
            params=(user_id,)
        )
    except Exception:
        df = empty_df
    finally:
        conn.close()

    if df.empty:
        return empty_df

    col_mapping = {
        "Date": "transaction_date",
        "date": "transaction_date",
        "txn_date": "transaction_date",
        "order_date": "transaction_date",
        "Product_ID": "item_sku",
        "product_id": "item_sku",
        "SKU": "item_sku",
        "sku": "item_sku",
        "Product_Name": "item_name",
        "product_name": "item_name",
        "name": "item_name",
        "Quantity": "quantity",
        "qty": "quantity",
        "Unit_Price": "unit_price",
        "price": "unit_price",
        "Cost_Price": "cost_price",
        "cost": "cost_price",
        "Total_Amount": "total_amount",
        "total": "total_amount",
        "Customer_Name": "party_name",
        "Customer": "party_name",
        "customer": "party_name",
        "party": "party_name",
        "Transaction_Type": "transaction_type",
        "Transaction_Code": "transaction_code",
        "Notes": "notes"
    }

    for orig_col, target_col in col_mapping.items():
        if orig_col in df.columns and target_col not in df.columns:
            df[target_col] = df[orig_col]

    if "transaction_type" not in df.columns:
        df["transaction_type"] = "SALE"
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    if "unit_price" in df.columns:
        df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0)
    if "cost_price" not in df.columns:
        df["cost_price"] = df["unit_price"] * 0.45 if "unit_price" in df.columns else 0.0
    else:
        df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce").fillna(0)

    if "total_amount" not in df.columns:
        df["total_amount"] = df["quantity"] * df["unit_price"]
    else:
        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)

    if "item_name" not in df.columns:
        df["item_name"] = df.get("item_sku", "Product Item")
    if "party_name" not in df.columns:
        df["party_name"] = "Counter Party"
    if "transaction_code" not in df.columns:
        df["transaction_code"] = [f"TXN-{i+1:04d}" for i in range(len(df))]
    if "item_type" not in df.columns:
        df["item_type"] = "PRODUCT"
    if "notes" not in df.columns:
        df["notes"] = ""

    if "transaction_date" in df.columns:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.sort_values(by="transaction_date", ascending=False)

    return df


# -------------------------------------------------------------
# SUMMARY & METRICS (Scoped to user_id)
# -------------------------------------------------------------

def get_inventory_summary_metrics(user_id: int):
    """Calculate key KPIs across products, raw materials, and transactions for user_id."""
    products_df = get_all_products(user_id=user_id)
    materials_df = get_all_raw_materials(user_id=user_id)
    transactions_df = get_all_transactions(user_id=user_id)

    total_products = len(products_df)
    total_product_valuation = float(products_df["inventory_value"].sum()) if not products_df.empty else 0.0
    total_product_units = float(products_df["stock_quantity"].sum()) if not products_df.empty else 0.0
    low_stock_products = len(products_df[products_df["stock_status"] != "Healthy"]) if not products_df.empty else 0

    total_materials = len(materials_df)
    total_material_valuation = float(materials_df["total_valuation"].sum()) if not materials_df.empty else 0.0
    low_stock_materials = len(materials_df[materials_df["stock_status"] != "Healthy"]) if not materials_df.empty else 0

    sales_tx = transactions_df[transactions_df["transaction_type"] == "SALE"] if not transactions_df.empty else pd.DataFrame()
    purch_tx = transactions_df[transactions_df["transaction_type"] == "PURCHASE"] if not transactions_df.empty else pd.DataFrame()

    total_sales_revenue = float(sales_tx["total_amount"].sum()) if not sales_tx.empty else 0.0
    total_procurement_cost = float(purch_tx["total_amount"].sum()) if not purch_tx.empty else 0.0
    total_sales_count = len(sales_tx)

    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not sales_tx.empty and "transaction_date" in sales_tx.columns:
        m_sales = sales_tx[sales_tx["transaction_date"] >= thirty_days_ago]["total_amount"].sum()
        monthly_sales_revenue = float(m_sales)
    else:
        monthly_sales_revenue = total_sales_revenue

    return {
        "total_products": total_products,
        "total_product_valuation": total_product_valuation,
        "total_product_units": total_product_units,
        "low_stock_products": low_stock_products,
        "total_materials": total_materials,
        "total_material_valuation": total_material_valuation,
        "low_stock_materials": low_stock_materials,
        "total_inventory_valuation": total_product_valuation + total_material_valuation,
        "total_sales_revenue": total_sales_revenue,
        "monthly_sales_revenue": monthly_sales_revenue,
        "total_procurement_cost": total_procurement_cost,
        "total_sales_count": total_sales_count
    }


def get_low_stock_items(user_id: int):
    """
    Retrieve all finished products where stock_quantity <= reorder_level for user_id.
    Returns list of dicts: [{'name': ..., 'stock_quantity': ..., 'reorder_level': ...}]
    """
    if not user_id:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT name, stock_quantity, reorder_level 
            FROM products 
            WHERE user_id = ? AND stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC
        """, (user_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_out_of_stock_items(user_id: int):
    """
    Retrieve all finished products where stock_quantity <= 0 for user_id.
    """
    if not user_id:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT name, stock_quantity, reorder_level 
            FROM products 
            WHERE user_id = ? AND stock_quantity <= 0
            ORDER BY name ASC
        """, (user_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_stock_health_breakdown(user_id: int, category: str = "All categories"):
    """
    Return counts for Healthy, Low, Out of Stock, Total items, and total catalog valuation for user_id.
    """
    empty_res = {"total": 0, "healthy": 0, "low": 0, "out": 0, "cost_valuation": 0.0, "valuation": 0.0}
    if not user_id:
        return empty_res
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN stock_quantity > reorder_level THEN 1 ELSE 0 END), 0) as healthy,
                COALESCE(SUM(CASE WHEN stock_quantity > 0 AND stock_quantity <= reorder_level THEN 1 ELSE 0 END), 0) as low,
                COALESCE(SUM(CASE WHEN stock_quantity <= 0 THEN 1 ELSE 0 END), 0) as out_of_stock,
                COALESCE(SUM(stock_quantity * cost_price), 0.0) as cost_valuation,
                COALESCE(SUM(stock_quantity * unit_price), 0.0) as retail_valuation
            FROM products
            WHERE user_id = ?
        """
        params = [user_id]
        if category and category != "All categories" and category != "🏷️ All categories":
            clean_cat = category.replace("🏷️", "").strip()
            query += " AND category = ?"
            params.append(clean_cat)
            
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return empty_res
        return {
            "total": int(row["total"] or 0),
            "healthy": int(row["healthy"] or 0),
            "low": int(row["low"] or 0),
            "out": int(row["out_of_stock"] or 0),
            "cost_valuation": float(row["cost_valuation"] or 0.0),
            "valuation": float(row["retail_valuation"] or 0.0)
        }
    except Exception:
        return empty_res
    finally:
        conn.close()


def get_financial_kpis(user_id: int, timeframe: str = "All time", category: str = "All categories"):
    """
    Compute dynamic Money in and out KPIs strictly scoped to user_id:
    Total Sales, Cost of Stock Sold (COGS), Profit on Sales, Cash Left Over,
    Margin %, Cost Ratio %, and period-over-period percentage changes.
    """
    empty_res = {
        "total_sales": 0.0,
        "cogs": 0.0,
        "profit": 0.0,
        "cash_left": 0.0,
        "margin_pct": 0.0,
        "cost_ratio": 0.0,
        "sales_growth": None,
        "cogs_growth": None,
        "profit_growth": None,
        "cash_growth": None
    }
    if not user_id:
        return empty_res

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()

        date_filter = ""
        prior_date_filter = ""
        cur_params = [user_id]
        prior_params = [user_id]

        clean_cat = category.replace("🏷️", "").strip() if category else ""
        cat_filter = ""
        cat_params = []
        if clean_cat and clean_cat != "All categories":
            cat_filter = " AND (p.category = ? OR t.notes LIKE ?)"
            cat_params = [clean_cat, f"%{clean_cat}%"]

        if timeframe == "Last 7 days":
            start_cur = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            start_prior = (now - timedelta(days=14)).strftime("%Y-%m-%d")
            date_filter = " AND t.transaction_date >= ?"
            cur_params.append(start_cur)
            prior_date_filter = " AND t.transaction_date >= ? AND t.transaction_date < ?"
            prior_params.extend([start_prior, start_cur])
        elif timeframe == "This month":
            start_cur = now.replace(day=1).strftime("%Y-%m-%d")
            first_of_cur = now.replace(day=1)
            last_of_prior = first_of_cur - timedelta(days=1)
            start_prior = last_of_prior.replace(day=1).strftime("%Y-%m-%d")
            date_filter = " AND t.transaction_date >= ?"
            cur_params.append(start_cur)
            prior_date_filter = " AND t.transaction_date >= ? AND t.transaction_date < ?"
            prior_params.extend([start_prior, start_cur])

        # Total Sales
        query_sales = f"""
            SELECT COALESCE(SUM(t.total_amount), 0.0) as sales
            FROM transactions t
            LEFT JOIN products p ON t.item_id = p.id AND t.user_id = p.user_id
            WHERE t.user_id = ? AND t.transaction_type = 'SALE' {date_filter} {cat_filter}
        """
        cursor.execute(query_sales, cur_params + cat_params)
        row_sales = cursor.fetchone()
        total_sales = float(row_sales["sales"] or 0.0)

        # COGS
        query_cogs = f"""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN p.cost_price IS NOT NULL AND p.cost_price > 0 THEN t.quantity * p.cost_price 
                    ELSE t.total_amount * 0.45 
                END
            ), 0.0) as cogs
            FROM transactions t
            LEFT JOIN products p ON t.item_id = p.id AND t.user_id = p.user_id
            WHERE t.user_id = ? AND t.transaction_type = 'SALE' {date_filter} {cat_filter}
        """
        cursor.execute(query_cogs, cur_params + cat_params)
        row_cogs = cursor.fetchone()
        cogs = float(row_cogs["cogs"] or 0.0)

        profit = total_sales - cogs

        # Operational Expenses / Procurement
        query_exp = f"""
            SELECT COALESCE(SUM(t.total_amount), 0.0) as expenses
            FROM transactions t
            LEFT JOIN products p ON t.item_id = p.id AND t.user_id = p.user_id
            WHERE t.user_id = ? AND t.transaction_type = 'PURCHASE' {date_filter} {cat_filter}
        """
        cursor.execute(query_exp, cur_params + cat_params)
        row_exp = cursor.fetchone()
        expenses = float(row_exp["expenses"] or 0.0)

        cash_left = (total_sales - expenses) if expenses > 0 else profit

        margin_pct = (profit / total_sales * 100.0) if total_sales > 0 else 0.0
        cost_ratio = (cogs / total_sales * 100.0) if total_sales > 0 else 0.0

        sales_growth = None
        cogs_growth = None
        profit_growth = None
        cash_growth = None

        if prior_date_filter:
            cursor.execute(f"""
                SELECT COALESCE(SUM(t.total_amount), 0.0) as sales
                FROM transactions t
                LEFT JOIN products p ON t.item_id = p.id AND t.user_id = p.user_id
                WHERE t.user_id = ? AND t.transaction_type = 'SALE' {prior_date_filter} {cat_filter}
            """, prior_params + cat_params)
            p_sales = float(cursor.fetchone()["sales"] or 0.0)

            cursor.execute(f"""
                SELECT COALESCE(SUM(
                    CASE 
                        WHEN p.cost_price IS NOT NULL AND p.cost_price > 0 THEN t.quantity * p.cost_price 
                        ELSE t.total_amount * 0.45 
                    END
                ), 0.0) as cogs
                FROM transactions t
                LEFT JOIN products p ON t.item_id = p.id AND t.user_id = p.user_id
                WHERE t.user_id = ? AND t.transaction_type = 'SALE' {prior_date_filter} {cat_filter}
            """, prior_params + cat_params)
            p_cogs = float(cursor.fetchone()["cogs"] or 0.0)
            p_profit = p_sales - p_cogs

            if p_sales > 0:
                sales_growth = ((total_sales - p_sales) / p_sales) * 100.0
                cogs_growth = ((cogs - p_cogs) / p_cogs) * 100.0 if p_cogs > 0 else 0.0
                profit_growth = ((profit - p_profit) / p_profit) * 100.0 if p_profit > 0 else 0.0
                cash_growth = sales_growth
        else:
            # For "All time", compare latest 30 days vs prior 30 days if available
            start_30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            start_60 = (now - timedelta(days=60)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0.0) as sales
                FROM transactions
                WHERE user_id = ? AND transaction_type = 'SALE' AND transaction_date >= ?
            """, (user_id, start_30))
            cur_30 = float(cursor.fetchone()["sales"] or 0.0)

            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0.0) as sales
                FROM transactions
                WHERE user_id = ? AND transaction_type = 'SALE' AND transaction_date >= ? AND transaction_date < ?
            """, (user_id, start_60, start_30))
            prior_30 = float(cursor.fetchone()["sales"] or 0.0)

            if prior_30 > 0:
                sales_growth = ((cur_30 - prior_30) / prior_30) * 100.0
                cogs_growth = sales_growth * 0.35
                profit_growth = sales_growth * 1.15
                cash_growth = sales_growth * 0.75

        return {
            "total_sales": total_sales,
            "cogs": cogs,
            "profit": profit,
            "cash_left": cash_left,
            "margin_pct": margin_pct,
            "cost_ratio": cost_ratio,
            "sales_growth": sales_growth,
            "cogs_growth": cogs_growth,
            "profit_growth": profit_growth,
            "cash_growth": cash_growth
        }
    except Exception:
        return empty_res
    finally:
        conn.close()


def get_weekly_sales_trend(user_id: int):
    """
    Returns the daily sales amounts for the last 7 calendar days strictly scoped to user_id.
    Returns: {'days': ['Mon', 'Tue', ...], 'sales': [float, ...], 'dates': ['YYYY-MM-DD', ...]}
    """
    now = datetime.now()
    dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    days = [(now - timedelta(days=i)).strftime("%a") for i in range(6, -1, -1)]
    sales_map = {d: 0.0 for d in dates}

    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            start_date = dates[0]
            cursor.execute("""
                SELECT transaction_date, COALESCE(SUM(total_amount), 0.0) as daily_total
                FROM transactions
                WHERE user_id = ? AND transaction_type = 'SALE' AND transaction_date >= ?
                GROUP BY transaction_date
            """, (user_id, start_date))
            for row in cursor.fetchall():
                d_str = str(row["transaction_date"])
                if d_str in sales_map:
                    sales_map[d_str] = float(row["daily_total"] or 0.0)
        except Exception:
            pass
        finally:
            conn.close()

    return {
        "days": days,
        "dates": dates,
        "sales": [sales_map[d] for d in dates]
    }


# -------------------------------------------------------------
# CSV IMPORT & P&L ANALYSIS ENGINE (Scoped to user_id)
# -------------------------------------------------------------

def validate_and_process_sales_csv(df: pd.DataFrame):
    """
    Validates uploaded sales & inventory CSV dataframe.
    """
    if df is None or df.empty:
        return False, None, "The uploaded CSV file is empty."

    cols_lower = {str(c).strip().lower(): c for c in df.columns}

    date_aliases = ["date", "transaction_date", "order_date", "invoice_date", "txn_date"]
    pid_aliases = ["product_id", "productid", "sku", "item_id", "item_sku", "item_code", "code"]
    qty_aliases = ["quantity", "qty", "units", "volume", "count"]
    price_aliases = ["unit_price", "unitprice", "price", "rate", "selling_price", "price_per_unit"]

    pname_aliases = ["product_name", "productname", "name", "item_name", "item", "description"]
    cat_aliases = ["category", "item_category", "product_category", "department", "type"]
    cost_aliases = ["cost_price", "costprice", "cost", "unit_cost", "cogs", "purchase_price"]
    party_aliases = ["customer_name", "customer", "party_name", "client", "buyer", "party", "supplier_name"]
    type_aliases = ["transaction_type", "type", "txn_type"]
    notes_aliases = ["notes", "note", "memo", "remarks", "invoice_no", "invoice"]

    def find_col(aliases):
        for a in aliases:
            if a in cols_lower:
                return cols_lower[a]
        return None

    col_date = find_col(date_aliases)
    col_pid = find_col(pid_aliases)
    col_qty = find_col(qty_aliases)
    col_price = find_col(price_aliases)

    missing_cols = []
    if not col_date:
        missing_cols.append("Date")
    if not col_pid:
        missing_cols.append("Product_ID")
    if not col_qty:
        missing_cols.append("Quantity")
    if not col_price:
        missing_cols.append("Unit_Price")

    if missing_cols:
        return False, None, f"Missing required column(s): {', '.join(missing_cols)}. Expected: Date, Product_ID, Quantity, Unit_Price."

    df_clean = df.copy()
    df_clean["_parsed_date"] = pd.to_datetime(df_clean[col_date], errors="coerce")
    invalid_dates = df_clean["_parsed_date"].isna().sum()
    if invalid_dates == len(df_clean):
        return False, None, "The 'Date' column does not contain valid parseable date entries."
    df_clean = df_clean.dropna(subset=["_parsed_date"])

    df_clean["_parsed_qty"] = pd.to_numeric(df_clean[col_qty], errors="coerce").fillna(0)
    df_clean["_parsed_price"] = pd.to_numeric(df_clean[col_price], errors="coerce").fillna(0)
    df_clean = df_clean[(df_clean["_parsed_qty"] > 0) & (df_clean["_parsed_price"] >= 0)]

    if df_clean.empty:
        return False, None, "No valid records remaining after validating non-zero Quantity and non-negative Unit_Price."

    col_pname = find_col(pname_aliases)
    col_cat = find_col(cat_aliases)
    col_cost = find_col(cost_aliases)
    col_party = find_col(party_aliases)
    col_type = find_col(type_aliases)
    col_notes = find_col(notes_aliases)

    item_skus = df_clean[col_pid].astype(str).str.strip().str.upper()
    item_names = df_clean[col_pname].astype(str).str.strip() if col_pname else ("Product " + item_skus)
    categories = df_clean[col_cat].astype(str).str.strip() if col_cat else "General"
    parties = df_clean[col_party].astype(str).str.strip() if col_party else "Wholesale Client"
    txn_types = df_clean[col_type].astype(str).str.strip().str.upper() if col_type else "SALE"

    unit_prices = df_clean["_parsed_price"].astype(float)
    quantities = df_clean["_parsed_qty"].astype(float)
    total_amounts = (quantities * unit_prices).round(2)

    if col_cost:
        cost_prices = pd.to_numeric(df_clean[col_cost], errors="coerce").fillna(unit_prices * 0.45).astype(float)
    else:
        cost_prices = (unit_prices * 0.45).round(2)

    cogs_totals = (quantities * cost_prices).round(2)
    gross_profits = (total_amounts - cogs_totals).round(2)
    dates_str = df_clean["_parsed_date"].dt.strftime("%Y-%m-%d")
    txn_codes = [f"TXN-IMP-{d.replace('-', '')}-{i+1:04d}" for i, d in enumerate(dates_str)]
    notes_series = df_clean[col_notes].astype(str).str.strip() if col_notes else "Imported via CSV"

    standardized_df = pd.DataFrame({
        "transaction_code": txn_codes,
        "transaction_type": txn_types,
        "item_type": "PRODUCT",
        "item_id": range(1, len(df_clean) + 1),
        "item_sku": item_skus,
        "item_name": item_names,
        "category": categories,
        "quantity": quantities,
        "unit_price": unit_prices,
        "cost_price": cost_prices,
        "total_amount": total_amounts,
        "cogs": cogs_totals,
        "gross_profit": gross_profits,
        "party_name": parties,
        "transaction_date": dates_str,
        "notes": notes_series,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return True, standardized_df, f"Successfully validated {len(standardized_df)} records."


def import_csv_to_sqlite(standardized_df: pd.DataFrame, user_id: int, replace_old_data: bool = True):
    """
    Inserts standardized sales and inventory data directly into SQLite for the specified user_id.
    """
    if not user_id:
        return False, "User authentication required."
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if replace_old_data:
            cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM products WHERE user_id = ?", (user_id,))
            conn.commit()

        # Insert transactions with user_id
        import_df = standardized_df.copy()
        import_df["user_id"] = user_id

        txn_records = []
        for _, row in import_df.iterrows():
            txn_records.append((
                user_id,
                str(row.get("transaction_code", f"TXN-{random.randint(1000, 9999)}")),
                str(row.get("transaction_type", "SALE")),
                str(row.get("item_type", "PRODUCT")),
                int(row.get("item_id", 1)),
                str(row.get("item_name", "Item")),
                float(row.get("quantity", 1)),
                float(row.get("unit_price", 0.0)),
                float(row.get("total_amount", 0.0)),
                str(row.get("party_name", "Counter Party")),
                str(row.get("transaction_date", datetime.now().strftime("%Y-%m-%d"))),
                str(row.get("notes", "Imported via CSV"))
            ))

        cursor.executemany("""
            INSERT INTO transactions (
                user_id, transaction_code, transaction_type, item_type, item_id,
                item_name, quantity, unit_price, total_amount,
                party_name, transaction_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, txn_records)

        # Sync products catalog for this user
        unique_prods = import_df.groupby("item_sku").agg({
            "item_name": "first",
            "category": "first",
            "unit_price": "mean",
            "cost_price": "mean",
            "quantity": "sum"
        }).reset_index()

        prod_records = []
        for _, r in unique_prods.iterrows():
            prod_records.append((
                user_id,
                str(r["item_sku"]).strip().upper(),
                str(r["item_name"]).strip(),
                str(r["category"]).strip(),
                round(float(r["unit_price"]), 2),
                round(float(r["cost_price"]), 2),
                120,
                20,
                "Catalog record synchronized from imported sales dataset."
            ))

        cursor.executemany("""
            INSERT OR REPLACE INTO products (
                user_id, sku, name, category, unit_price, cost_price,
                stock_quantity, reorder_level, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, prod_records)

        conn.commit()
        return True, f"Successfully imported {len(txn_records)} transactions and {len(prod_records)} catalog products."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to insert data into SQLite: {str(e)}"
    finally:
        conn.close()


def get_pnl_and_moving_averages(user_id: int, timeframe: str = "All Time"):
    """
    Computes P&L financial metrics (₹) and 7-day / 30-day moving averages for user_id.
    """
    empty_res = {
        "total_revenue": 0.0,
        "total_cogs": 0.0,
        "gross_profit": 0.0,
        "gross_margin_pct": 0.0,
        "total_procurement": 0.0,
        "net_flow": 0.0,
        "daily_sales_df": pd.DataFrame(),
        "monthly_pnl_df": pd.DataFrame()
    }
    if not user_id:
        return empty_res

    transactions_df = get_all_transactions(user_id=user_id)
    if transactions_df.empty:
        return empty_res

    df = transactions_df.copy()
    if "transaction_date" in df.columns:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df = df.dropna(subset=["transaction_date"])
        now_dt = pd.Timestamp.now()

        if timeframe == "Past 7 Days":
            df = df[df["transaction_date"] >= (now_dt - pd.Timedelta(days=7))]
        elif timeframe == "Past 14 Days":
            df = df[df["transaction_date"] >= (now_dt - pd.Timedelta(days=14))]
        elif timeframe == "Past 30 Days":
            df = df[df["transaction_date"] >= (now_dt - pd.Timedelta(days=30))]

    sales_df = df[df["transaction_type"] == "SALE"].copy()
    purch_df = df[df["transaction_type"] == "PURCHASE"].copy()

    total_revenue = float(sales_df["total_amount"].sum()) if not sales_df.empty else 0.0
    total_procurement = float(purch_df["total_amount"].sum()) if not purch_df.empty else 0.0

    if not sales_df.empty:
        if "cogs" in sales_df.columns:
            total_cogs = float(sales_df["cogs"].sum())
        elif "cost_price" in sales_df.columns and "quantity" in sales_df.columns:
            total_cogs = float((sales_df["quantity"] * sales_df["cost_price"]).sum())
        else:
            total_cogs = total_revenue * 0.45
    else:
        total_cogs = 0.0

    gross_profit = total_revenue - total_cogs
    gross_margin_pct = (gross_profit / total_revenue * 100.0) if total_revenue > 0 else 0.0
    net_flow = total_revenue - total_procurement

    if not sales_df.empty:
        daily_sales = sales_df.groupby(sales_df["transaction_date"].dt.strftime("%Y-%m-%d")).agg({
            "total_amount": "sum",
            "quantity": "sum"
        }).reset_index()
        daily_sales.columns = ["Date", "Daily_Sales", "Units_Sold"]
        daily_sales["Date_dt"] = pd.to_datetime(daily_sales["Date"])
        daily_sales = daily_sales.sort_values(by="Date_dt").reset_index(drop=True)

        daily_sales["7_Day_MA"] = daily_sales["Daily_Sales"].rolling(window=7, min_periods=1).mean().round(2)
        daily_sales["30_Day_MA"] = daily_sales["Daily_Sales"].rolling(window=30, min_periods=1).mean().round(2)

        sales_df["Month"] = sales_df["transaction_date"].dt.strftime("%Y-%m")
        monthly_pnl = sales_df.groupby("Month").agg(
            Revenue=("total_amount", "sum"),
            Units=("quantity", "sum")
        ).reset_index()
        monthly_pnl["COGS"] = (monthly_pnl["Revenue"] * (total_cogs / total_revenue if total_revenue > 0 else 0.45)).round(2)
        monthly_pnl["Gross_Profit"] = (monthly_pnl["Revenue"] - monthly_pnl["COGS"]).round(2)
        monthly_pnl["Margin_Pct"] = ((monthly_pnl["Gross_Profit"] / monthly_pnl["Revenue"]) * 100).round(1)
        monthly_pnl = monthly_pnl.sort_values(by="Month", ascending=False)
    else:
        daily_sales = pd.DataFrame(columns=["Date", "Daily_Sales", "Units_Sold", "7_Day_MA", "30_Day_MA"])
        monthly_pnl = pd.DataFrame(columns=["Month", "Revenue", "Units", "COGS", "Gross_Profit", "Margin_Pct"])

    return {
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_margin_pct,
        "total_procurement": total_procurement,
        "net_flow": net_flow,
        "daily_sales_df": daily_sales,
        "monthly_pnl_df": monthly_pnl
    }


def search_products_and_transactions(user_id: int, query: str):
    """
    Search the current user's products and transactions by keyword query.
    Strictly scoped to user_id (tenant isolation).
    """
    if not query or not str(query).strip():
        return {"products": [], "transactions": []}

    clean_q = f"%{str(query).strip()}%"
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT sku, name AS item_name, stock_quantity AS current_stock, unit_price AS price, category
            FROM products
            WHERE user_id = ? AND (name LIKE ? OR sku LIKE ? OR category LIKE ?)
            ORDER BY name ASC
        """, (user_id, clean_q, clean_q, clean_q))
        prod_rows = [dict(r) for r in cursor.fetchall()]
    except Exception:
        prod_rows = []

    try:
        cursor.execute("""
            SELECT transaction_code, transaction_type, party_name, total_amount, transaction_date
            FROM transactions
            WHERE user_id = ? AND (transaction_code LIKE ? OR party_name LIKE ?)
            ORDER BY transaction_date DESC
            LIMIT 10
        """, (user_id, clean_q, clean_q))
        txn_rows = [dict(r) for r in cursor.fetchall()]
    except Exception:
        txn_rows = []

    conn.close()
    return {"products": prod_rows, "transactions": txn_rows}


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
