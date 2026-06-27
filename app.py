import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd
from io import BytesIO

from pwa import inject_pwa

# Page config and custom CSS
st.set_page_config(
    page_title="Sky Order Converter",
    page_icon="static/sky-logo.png",
    layout="centered"
)

if not os.environ.get("SKY_DESKTOP"):
    inject_pwa()

# Faire export column names → internal standard column names
COLUMN_ALIASES = {
    "Order Number": ["order number", "order #", "order no"],
    "Order Date": ["order date"],
    "Purchase Order Number": ["purchase order number", "purchase order no", "po number"],
    "Retailer Name": ["retailer name", "retailer shop name", "shop name", "company name"],
    "Status": ["status", "order status"],
    "Ship Date": ["ship date", "shipped date"],
    "Address 1": ["address 1", "address", "street", "shipping address", "retailer address"],
    "City": ["city"],
    "State": ["state", "province"],
    "Zip Code": ["zip code", "zip", "postal code", "postcode"],
    "Country": ["country"],
    "SKU": ["sku", "style no", "style number", "vendor style no"],
    "Option Name": ["option name", "variant", "color/scent", "color", "product option"],
    "Wholesale Price": ["wholesale price", "unit price", "price"],
    "Retail Price": ["retail price"],
    "Quantity": ["quantity", "qty", "total qty", "item quantity"],
    "Product Name": ["product name"],
    "Address 2": ["address 2"],
    "GTIN": ["gtin"],
    "Scheduled Order Date": ["scheduled order date"],
    "Notes": ["notes", "memo"],
}

OUTPUT_COLS = [
    "custpoNum", "customer", "Order_Date", "styleNum", "description", "color",
    "sizeInfo", "quantityInfo", "unitPrice", "Retail_Price", "SKU",
    "Purchase_Order_Number", "state", "zipCode", "Country", "GTIN", "Status",
    "Ship_Date", "Scheduled_Order_Date", "memo", "shipAdd1", "shipAdd2",
    "Product_Name", "Option_Name",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize BOM, whitespace, and casing; map Faire export columns to standard names."""
    df = df.copy()
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    lookup = {c.lower(): c for c in df.columns}

    rename_map = {}
    for standard, aliases in COLUMN_ALIASES.items():
        if standard in df.columns:
            continue
        for alias in aliases:
            if alias in lookup:
                rename_map[lookup[alias]] = standard
                break

    return df.rename(columns=rename_map)


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def get_missing_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [col for col in required if col not in df.columns]


def safe_str(val, default=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s


def parse_price(val) -> float:
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def fmt_date(val) -> str:
    s = safe_str(val)
    if not s:
        return ""
    lower = s.lower()
    if "no ship" in lower or "no scheduled" in lower:
        return s
    try:
        return pd.to_datetime(val, dayfirst=False).strftime("%Y%m%d")
    except Exception:
        return s


def parse_option_name(option_name: str) -> tuple[str, str, str]:
    """Return (color, sizeInfo part, full Option_Name)."""
    opt = safe_str(option_name)
    if not opt:
        return "", "", opt
    if " / " not in opt:
        return "", opt, opt

    left, size = opt.rsplit(" / ", 1)
    left, size = left.strip(), size.strip()
    if "/" in left:
        primary, secondary = left.split("/", 1)
        return primary.strip(), f"{secondary.strip()} / {size}", opt
    return left, size, opt


SIZE_ORDER = {
    "XXS": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5,
    "XXL": 6, "2XL": 6, "3XL": 7, "4XL": 8, "5XL": 9,
    "OS": 90, "ONE SIZE": 90,
}


def extract_size_key(size_part: str) -> str:
    s = safe_str(size_part)
    if " / " in s:
        return s.rsplit(" / ", 1)[1].strip().upper()
    return s.upper()


def size_sort_key(size_part: str) -> tuple:
    key = extract_size_key(size_part)
    return (SIZE_ORDER.get(key, 50), key)


def sort_size_qty_pairs(sizes: list[str], qtys: list[str]) -> tuple[list[str], list[str]]:
    pairs = sorted(zip(sizes, qtys), key=lambda pair: size_sort_key(pair[0]))
    if not pairs:
        return [], []
    sorted_sizes, sorted_qtys = zip(*pairs)
    return list(sorted_sizes), list(sorted_qtys)


def build_ship_address(row) -> tuple[str, object]:
    addr1 = safe_str(row.get("Address 1", ""))
    addr2 = safe_str(row.get("Address 2", ""))
    ship_add1 = f"{addr1} {addr2}".strip() if addr2 else addr1
    city = safe_str(row.get("City", ""))
    ship_add2 = city if city else pd.NA
    return ship_add1, ship_add2


def optional_field(val):
    return val if pd.notna(val) and safe_str(val) else pd.NA


def sum_quantity_info(val) -> int:
    total = 0
    for part in safe_str(val).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            total += int(float(part))
        except ValueError:
            pass
    return total


def pacific_now() -> datetime:
    return datetime.now(ZoneInfo("America/Los_Angeles"))


def convert_faire_to_sky(faire_df: pd.DataFrame) -> tuple[pd.DataFrame, set[str], float]:
    """Convert Faire order summary CSV rows to Sky upload Excel format."""
    groups: dict[tuple[str, str], dict] = {}
    group_order: list[tuple[str, str]] = []
    unique_orders: set[str] = set()
    total_order_amt = 0.0

    for _, row in faire_df.iterrows():
        order_no = safe_str(row.get("Order Number", ""))
        sku = safe_str(row.get("SKU", ""))
        if not order_no or not sku:
            continue

        unique_orders.add(order_no)
        color, size_part, full_opt = parse_option_name(row.get("Option Name", ""))
        try:
            qty = int(float(row["Quantity"]))
        except (ValueError, TypeError):
            qty = 0

        price = parse_price(row.get("Wholesale Price", 0))
        total_order_amt += qty * price

        key = (order_no, sku)
        if key not in groups:
            ship_add1, ship_add2 = build_ship_address(row)
            notes = row.get("Notes")
            memo = safe_str(notes) if pd.notna(notes) and safe_str(notes) else "'-"
            groups[key] = {
                "sizes": [size_part],
                "qtys": [str(qty)],
                "color": color,
                "first_opt": full_opt,
                "custpoNum": order_no,
                "customer": safe_str(row.get("Retailer Name", "")),
                "Order_Date": fmt_date(row.get("Order Date", "")),
                "styleNum": sku,
                "description": safe_str(row.get("Product Name", "")),
                "unitPrice": price,
                "Retail_Price": parse_price(row.get("Retail Price", 0)),
                "SKU": sku,
                "Purchase_Order_Number": optional_field(row.get("Purchase Order Number")),
                "state": safe_str(row.get("State", "")),
                "zipCode": safe_str(row.get("Zip Code", "")),
                "Country": safe_str(row.get("Country", "")),
                "GTIN": optional_field(row.get("GTIN")),
                "Status": safe_str(row.get("Status", "")),
                "Ship_Date": fmt_date(row.get("Ship Date", "")),
                "Scheduled_Order_Date": fmt_date(row.get("Scheduled Order Date", "")),
                "memo": memo,
                "shipAdd1": ship_add1,
                "shipAdd2": ship_add2,
                "Product_Name": safe_str(row.get("Product Name", "")),
                "Option_Name": full_opt,
            }
            group_order.append(key)
        else:
            g = groups[key]
            g["sizes"].append(size_part)
            g["qtys"].append(str(qty))

    rows = []
    for key in group_order:
        g = groups[key]
        sizes, qtys = sort_size_qty_pairs(g["sizes"], g["qtys"])
        rows.append({
            "custpoNum": g["custpoNum"],
            "customer": g["customer"],
            "Order_Date": g["Order_Date"],
            "styleNum": g["styleNum"],
            "description": g["description"],
            "color": g["color"] if g["color"] else pd.NA,
            "sizeInfo": ",".join(sizes),
            "quantityInfo": ",".join(qtys),
            "unitPrice": g["unitPrice"],
            "Retail_Price": g["Retail_Price"],
            "SKU": g["SKU"],
            "Purchase_Order_Number": g["Purchase_Order_Number"],
            "state": g["state"],
            "zipCode": g["zipCode"],
            "Country": g["Country"],
            "GTIN": g["GTIN"],
            "Status": g["Status"],
            "Ship_Date": g["Ship_Date"],
            "Scheduled_Order_Date": g["Scheduled_Order_Date"],
            "memo": g["memo"],
            "shipAdd1": g["shipAdd1"],
            "shipAdd2": g["shipAdd2"],
            "Product_Name": g["Product_Name"],
            "Option_Name": g["first_opt"],
        })

    return pd.DataFrame(rows, columns=OUTPUT_COLS), unique_orders, total_order_amt


def write_sky_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Order")
    return output.getvalue()


# Custom CSS for card-style UI and hide Streamlit chrome
st.markdown("""
    <style>
    /* Hide header, deploy button, menu, footer */
    header[data-testid="stHeader"] {
        visibility: hidden;
        height: 0;
    }
    [data-testid="stToolbar"],
    [data-testid="stToolbarActions"],
    [data-testid="stDecoration"],
    .stAppDeployButton,
    #MainMenu {
        display: none !important;
    }
    footer {
        visibility: hidden;
    }
    .block-container {
        padding-top: 2rem;
    }

    .stApp {
        background-color: #0B1120;
    }

    .sky-logo {
        height: 22px;
        width: 22px;
        vertical-align: middle;
        margin-right: 6px;
        object-fit: contain;
    }
    .sky-logo-md {
        height: 30px;
        width: 30px;
        vertical-align: middle;
        margin-right: 10px;
        object-fit: contain;
    }
    .sky-logo-lg {
        height: 36px;
        width: 36px;
        vertical-align: middle;
        margin-right: 10px;
        object-fit: contain;
    }
    .main-header {
        font-size: 28px;
        font-weight: 700;
        color: #F1F5F9;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
    }
    .sub-header {
        font-size: 15px;
        color: #94A3B8;
        margin-bottom: 32px;
    }
    .step-title {
        font-size: 16px;
        font-weight: 600;
        color: #CBD5E1;
        margin-bottom: 8px;
    }
    .step-box {
        background-color: #151E2E;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #1E293B;
        margin-bottom: 24px;
    }
    .stat-card {
        background-color: #151E2E;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .stat-val {
        font-size: 24px;
        font-weight: 700;
        color: #818CF8;
    }
    .stat-lbl {
        font-size: 12px;
        color: #94A3B8;
        margin-top: 4px;
    }

    /* File uploader & buttons */
    [data-testid="stFileUploader"] section {
        background-color: #151E2E;
        border: 1px dashed #334155;
        border-radius: 12px;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #818CF8;
    }
    .stDownloadButton button {
        background: linear-gradient(135deg, #6366F1, #818CF8) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
    }
    hr {
        border-color: #1E293B !important;
    }

    .sky-notice {
        background: linear-gradient(90deg, rgba(99,102,241,0.18), rgba(129,140,248,0.10));
        border: 1px solid rgba(129, 140, 248, 0.35);
        border-radius: 10px;
        padding: 10px 16px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 14px;
        color: #C7D2FE;
    }
    .sky-notice-badge {
        background: #6366F1;
        color: #fff;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 999px;
        white-space: nowrap;
        letter-spacing: 0.03em;
    }
    .platform-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-bottom: 28px;
    }
    .platform-card {
        background: #151E2E;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .platform-card.active {
        border-color: #818CF8;
        box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.25);
        background: linear-gradient(180deg, #1a2236 0%, #151E2E 100%);
    }
    .platform-card.coming {
        opacity: 0.85;
    }
    .platform-icon {
        font-size: 22px;
        margin-bottom: 6px;
    }
    .platform-name {
        font-size: 14px;
        font-weight: 600;
        color: #E2E8F0;
    }
    .platform-status {
        font-size: 11px;
        margin-top: 4px;
        color: #94A3B8;
    }
    .platform-status.live { color: #34D399; }
    .platform-status.soon { color: #FBBF24; }
    .coming-soon-box {
        background: #151E2E;
        border: 1px dashed #334155;
        border-radius: 14px;
        padding: 40px 24px;
        text-align: center;
        margin-top: 8px;
    }
    .coming-soon-box h3 {
        color: #F1F5F9;
        font-size: 20px;
        margin: 0 0 8px 0;
    }
    .coming-soon-box p {
        color: #94A3B8;
        font-size: 14px;
        margin: 0;
        line-height: 1.6;
    }
    .upload-card {
        background: #151E2E;
        border: 1px solid #1E293B;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 8px;
    }
    div[data-testid="stHorizontalBlock"] button {
        border-radius: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

SOURCES = {
    "faire": {"label": "Faire", "icon": "🛍️", "live": True},
    "shopify": {"label": "Shopify", "icon": "🟢", "live": False},
    "company_order": {"label": "Company Order", "icon": "📄", "live": False},
}

if "order_source" not in st.session_state:
    st.session_state.order_source = "faire"

LOGO_URL = "/app/static/sky-logo.png"

# Header notice — Skysoft
st.markdown(f"""
    <div class="sky-notice">
        <span class="sky-notice-badge">SKYSOFT</span>
        <span>
            <img src="{LOGO_URL}" class="sky-logo" alt="Sky"/>
            <strong>Sky New App</strong> coming soon — stay tuned for the next release from Skysoft.
        </span>
    </div>
""", unsafe_allow_html=True)


st.markdown(
    f'<div class="main-header"><img src="{LOGO_URL}" class="sky-logo-lg" alt="Sky"/> Sky Order Converter</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Convert order files from multiple platforms into Sky upload Excel format.</div>',
    unsafe_allow_html=True,
)

# Platform selector
st.markdown('<div class="step-title">Select Order Source</div>', unsafe_allow_html=True)
p1, p2, p3 = st.columns(3)
with p1:
    if st.button("🛍️  Faire", use_container_width=True, type="primary" if st.session_state.order_source == "faire" else "secondary"):
        st.session_state.order_source = "faire"
with p2:
    if st.button("🟢  Shopify", use_container_width=True, type="primary" if st.session_state.order_source == "shopify" else "secondary"):
        st.session_state.order_source = "shopify"
with p3:
    if st.button("📄  Company Order", use_container_width=True, type="primary" if st.session_state.order_source == "company_order" else "secondary"):
        st.session_state.order_source = "company_order"

source = st.session_state.order_source
source_meta = SOURCES[source]

# Status badge under buttons
if source_meta["live"]:
    st.markdown(
        f'<p style="color:#34D399;font-size:13px;margin:4px 0 20px 0;">● {source_meta["label"]} converter is <strong>live</strong></p>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<p style="color:#FBBF24;font-size:13px;margin:4px 0 20px 0;">● {source_meta["label"]} converter — <strong>Coming Soon</strong></p>',
        unsafe_allow_html=True,
    )

# Coming Soon platforms
if not source_meta["live"]:
    st.markdown(f"""
        <div class="coming-soon-box">
            <h3>🚀 {source_meta["label"]} — Coming Soon</h3>
            <p>
                Upload your {source_meta["label"]} order Excel file here and it will be<br>
                automatically converted to Sky upload format.<br><br>
                <strong>This feature is under development.</strong>
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.file_uploader(
        f"Upload {source_meta['label']} order file (preview)",
        type=["csv", "xlsx", "xls"],
        label_visibility="collapsed",
        disabled=True,
        key=f"uploader_{source}",
    )
    st.info(f"**{source_meta['label']}** order conversion is coming soon. Please use **Faire** for now.")
    st.stop()

# Faire — live converter
st.markdown('<div class="step-title">STEP 1. Upload Faire Order File</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Select a CSV or Excel file",
    type=["csv", "xlsx", "xls"],
    label_visibility="collapsed",
)

# 4. Conversion and dashboard section (Step 2)
if uploaded_file is not None:
    st.success(f"✅ File selected: **{uploaded_file.name}**")

    try:
        with st.spinner("Reading and converting file..."):
            raw_df = read_uploaded_file(uploaded_file)
            faire_df = normalize_columns(raw_df)

            required_cols = [
                "Order Number", "Order Date", "Retailer Name", "Status",
                "SKU", "Option Name", "Wholesale Price", "Quantity", "Product Name",
            ]
            missing = get_missing_columns(faire_df, required_cols)
            if missing:
                st.error(
                    "⚠️ Could not recognize the Faire order file format.\n\n"
                    f"**Missing required columns:** {', '.join(missing)}\n\n"
                    f"**Columns found in file:** {', '.join(faire_df.columns.tolist())}\n\n"
                    "Please re-export from Faire Brand Portal → Orders → Export → **Order summary**."
                )
                st.stop()

            faire_df = faire_df.dropna(subset=["Order Number"])
            if faire_df.empty:
                st.warning("⚠️ File was read, but no valid order data (Order Number) was found.")
                st.stop()

            converted_df, unique_orders, total_order_amt = convert_faire_to_sky(faire_df)

        st.write("---")
        st.markdown('<div class="step-title" style="margin-bottom: 16px;">STEP 2. Conversion Results & Summary</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f'<div class="stat-card"><div class="stat-val">{len(unique_orders)} orders</div>'
                f'<div class="stat-lbl">Total Orders</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            total_units = converted_df["quantityInfo"].apply(sum_quantity_info).sum()
            st.markdown(
                f'<div class="stat-card"><div class="stat-val">{int(total_units)} pcs</div>'
                f'<div class="stat-lbl">Total Units</div></div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div class="stat-card"><div class="stat-val">${total_order_amt:,.2f}</div>'
                f'<div class="stat-lbl">Total Order Amount</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        st.dataframe(
            converted_df[[
                "custpoNum", "customer", "styleNum", "color",
                "sizeInfo", "quantityInfo", "unitPrice",
            ]],
            use_container_width=True,
        )

        processed_data = write_sky_excel(converted_df)

        st.write("")
        download_name = f"Faire_All_Orders_{pacific_now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.download_button(
            label="🚀 Download Sky Upload Excel",
            data=processed_data,
            file_name=download_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"⚠️ An error occurred while processing the file. Please check the format.\n\n**Error:** {e}")
