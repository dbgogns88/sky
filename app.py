import os
import streamlit as st
import pandas as pd
from io import BytesIO

from pwa import inject_pwa

# Page config and custom CSS
st.set_page_config(
    page_title="Sky Order Converter",
    page_icon="👗",
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
    "Quantity": ["quantity", "qty", "total qty", "item quantity"],
}


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


TEXT_COLS = [
    "orderDetailId", "orderId", "orderDate", "poNumber", "companyName",
    "orderStatus", "confirmDate", "shipDate", "payment", "shipment",
    "phoneNumber", "fax", "billingStreet", "billingCity", "billingState",
    "billingZipcode", "billingCountry", "shipToCompanyName", "shippingStreet",
    "shippingCity", "shippingState", "shippingZipcode", "shippingCountry",
    "styleNo", "vendorStyleNo", "Color/Scent", "size", "pack",
    "stockAvailability", "supplierName", "cancelDate",
]

NUMERIC_COLS = [
    "totalAmount", "discount", "couponAmount", "creditUsed", "additionaldiscount",
    "HandlingFee", "shippingCharge", "totalQty", "unitPrice", "subTotal",
    "redeemedPoint", "earnedPoint",
]


def safe_str(val, default=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s


def prepare_erp_export(df: pd.DataFrame) -> pd.DataFrame:
    """Fill empty cells with defaults to prevent DBNull errors on ERP (.NET) import."""
    export_df = df.copy()

    for col in TEXT_COLS:
        if col not in export_df.columns:
            continue
        export_df[col] = export_df[col].apply(safe_str)
        # Empty Excel cells become DBNull — replace empty strings with a single space
        export_df[col] = export_df[col].replace("", " ")

    for col in NUMERIC_COLS:
        if col not in export_df.columns:
            continue
        export_df[col] = pd.to_numeric(export_df[col], errors="coerce").fillna(0)

    return export_df


def write_erp_excel(df: pd.DataFrame) -> bytes:
    """Write ERP-compatible Excel with openpyxl, ensuring no blank (None) cells."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Order"

    cols = df.columns.tolist()
    ws.append(cols)

    for _, row in df.iterrows():
        values = []
        for col in cols:
            val = row[col]
            if col in NUMERIC_COLS:
                values.append(float(val) if pd.notna(val) else 0)
            else:
                s = safe_str(val, " ")
                values.append(s if s else " ")
        ws.append(values)

    output = BytesIO()
    wb.save(output)
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

    .main-header {
        font-size: 28px;
        font-weight: 700;
        color: #F1F5F9;
        margin-bottom: 8px;
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
    </style>
""", unsafe_allow_html=True)

# Header section
st.markdown('<div class="main-header">⚡ Sky Order Converter</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Instantly convert Faire order files to Sky upload format.</div>', unsafe_allow_html=True)

# 3. File upload section (Step 1)
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
                "SKU", "Option Name", "Wholesale Price", "Quantity",
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

            fg_cols = [
                "orderDetailId", "orderId", "orderDate", "poNumber", "companyName", "totalAmount",
                "discount", "couponAmount", "creditUsed", "additionaldiscount", "HandlingFee",
                "shippingCharge", "orderStatus", "confirmDate", "shipDate", "payment", "shipment",
                "phoneNumber", "fax", "billingStreet", "billingCity", "billingState", "billingZipcode",
                "billingCountry", "shipToCompanyName", "shippingStreet", "shippingCity", "shippingState",
                "shippingZipcode", "shippingCountry", "styleNo", "vendorStyleNo", "Color/Scent",
                "size", "pack", "totalQty", "unitPrice", "subTotal", "stockAvailability",
                "redeemedPoint", "earnedPoint", "supplierName", "cancelDate",
            ]

            output_rows = []
            total_order_amt = 0.0
            unique_orders = set()

            def parse_date(d_str):
                if pd.isna(d_str) or not str(d_str).strip():
                    return " "
                try:
                    return pd.to_datetime(d_str).strftime("%m/%d/%Y")
                except Exception:
                    return safe_str(d_str, " ")

            for _, row in faire_df.iterrows():
                opt_name = safe_str(row.get("Option Name", ""))
                color, pack_str, size_str = "", "", ""

                if "/" in opt_name:
                    color_part, size_part = opt_name.split("/", 1)
                    color = color_part.strip()
                    size_part = size_part.strip()
                    if "-" in size_part:
                        p_part, s_part = size_part.split("-", 1)
                        pack_str = ",".join(p_part.strip().split("/"))
                        size_str = "S,M,L" if s_part.strip().upper() == "SML" else s_part.strip()
                    else:
                        pack_str = size_part
                else:
                    color = opt_name

                if not size_str:
                    size_str = "OS"
                if not pack_str:
                    pack_str = "1"

                price = 0.0
                try:
                    price = float(str(row["Wholesale Price"]).replace("$", "").replace(",", "").strip())
                except (ValueError, TypeError):
                    pass

                qty = row["Quantity"]
                try:
                    qty = int(float(qty))
                except (ValueError, TypeError):
                    qty = 0

                subtotal = qty * price
                total_order_amt += subtotal
                unique_orders.add(row["Order Number"])

                fg_row = {c: " " for c in fg_cols}
                fg_row.update({
                    "orderDetailId": str(len(output_rows) + 1),
                    "orderId": safe_str(row["Order Number"]),
                    "orderDate": parse_date(row["Order Date"]),
                    "poNumber": safe_str(row.get("Purchase Order Number", "")),
                    "companyName": safe_str(row["Retailer Name"]),
                    "orderStatus": "Confirmed" if safe_str(row["Status"]) == "Processing" else safe_str(row["Status"]),
                    "shipDate": parse_date(row.get("Ship Date", "")),
                    "billingStreet": safe_str(row.get("Address 1", "")),
                    "billingCity": safe_str(row.get("City", "")),
                    "billingState": safe_str(row.get("State", "")),
                    "billingZipcode": safe_str(row.get("Zip Code", "")),
                    "billingCountry": safe_str(row.get("Country", "")),
                    "shipToCompanyName": safe_str(row["Retailer Name"]),
                    "shippingStreet": safe_str(row.get("Address 1", "")),
                    "shippingCity": safe_str(row.get("City", "")),
                    "shippingState": safe_str(row.get("State", "")),
                    "shippingZipcode": safe_str(row.get("Zip Code", "")),
                    "shippingCountry": safe_str(row.get("Country", "")),
                    "styleNo": safe_str(row["SKU"]),
                    "vendorStyleNo": safe_str(row["SKU"]),
                    "Color/Scent": color or " ",
                    "size": size_str,
                    "pack": pack_str,
                    "totalQty": qty,
                    "unitPrice": price,
                    "subTotal": subtotal,
                    "totalAmount": subtotal,
                })
                output_rows.append(fg_row)

            converted_df = pd.DataFrame(output_rows, columns=fg_cols)
            export_df = prepare_erp_export(converted_df)

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
            st.markdown(
                f'<div class="stat-card"><div class="stat-val">{int(converted_df["totalQty"].sum())} pcs</div>'
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
            converted_df[["orderId", "companyName", "styleNo", "Color/Scent", "size", "pack", "totalQty", "unitPrice"]],
            use_container_width=True,
        )

        processed_data = write_erp_excel(export_df)

        st.write("")
        st.download_button(
            label="🚀 Download Sky Upload Excel",
            data=processed_data,
            file_name="Sky_Upload_Orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"⚠️ An error occurred while processing the file. Please check the format.\n\n**Error:** {e}")
