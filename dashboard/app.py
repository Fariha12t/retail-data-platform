"""Streamlit dashboard over the marts schema (a free, runnable stand-in for the Power BI report).

Run:  streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from retail_pipeline.config import get_settings  # noqa: E402

st.set_page_config(page_title="Retail Data Platform", layout="wide")


@st.cache_resource
def engine():
    return create_engine(get_settings().db_url, pool_pre_ping=True)


@st.cache_data(ttl=300)
def q(sql: str, **params) -> pd.DataFrame:
    with engine().connect() as c:
        return pd.read_sql(text(sql), c, params=params)


st.title("Retail Data Platform")
try:
    rev = q("select * from marts.rpt_daily_revenue order by order_date")
except Exception as exc:  # no data yet / DB down
    st.error(f"Could not read marts.rpt_daily_revenue - run the pipeline first. ({exc})")
    st.stop()

lo, hi = rev["order_date"].min(), rev["order_date"].max()
start, end = st.sidebar.date_input("Date range", (max(lo, hi - pd.Timedelta(days=29)), hi), min_value=lo, max_value=hi)
view = rev[(rev["order_date"] >= start) & (rev["order_date"] <= end)]

tab_sales, tab_mkt, tab_inv, tab_ops = st.tabs(["Sales", "Marketing", "Inventory", "Pipeline health"])

with tab_sales:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net revenue", f"${view['net_revenue'].sum():,.0f}")
    c2.metric("Orders", f"{int(view['orders'].sum()):,}")
    c3.metric("Avg order value", f"${view['net_revenue'].sum() / max(view['orders'].sum(), 1):,.2f}")
    c4.metric("Gross margin", f"{view['gross_margin'].sum() / max(view['net_revenue'].sum(), 1) * 100:.1f}%")
    fig = px.bar(view, x="order_date", y="net_revenue", title="Daily net revenue")
    fig.add_scatter(x=view["order_date"], y=view["net_revenue_7d_avg"], mode="lines", name="7-day average")
    st.plotly_chart(fig, width="stretch")
    left, right = st.columns(2)
    cat = q("""select p.category, sum(f.net_amount) as net_revenue from marts.fact_order_items f
               join marts.dim_product p on p.product_key = f.product_key
               where f.is_revenue_order and f.order_date between :a and :b group by 1 order by 2 desc""", a=start, b=end)
    left.plotly_chart(px.bar(cat, x="category", y="net_revenue", title="Revenue by category"), width="stretch")
    prod = q("select product_name, category, units_sold, net_revenue, margin_pct, return_rate_pct from marts.rpt_product_performance order by net_revenue desc limit 10")
    right.subheader("Top products (lifetime)")
    right.dataframe(prod, hide_index=True, width="stretch")

with tab_mkt:
    m = q("""select channel, sum(spend) as spend, sum(net_revenue) as net_revenue, sum(orders) as orders,
             sum(net_revenue) / nullif(sum(spend), 0) as roas from marts.rpt_marketing_performance
             where report_date between :a and :b group by 1 order by 3 desc""", a=start, b=end)
    st.plotly_chart(px.bar(m, x="channel", y=["spend", "net_revenue"], barmode="group", title="Spend vs attributed revenue"), width="stretch")
    st.dataframe(m.round(2), hide_index=True, width="stretch")

with tab_inv:
    inv = q("select * from marts.rpt_inventory_status")
    counts = inv["stock_status"].value_counts().rename_axis("status").reset_index(name="products")
    st.plotly_chart(px.pie(counts, names="status", values="products", title="Stock status"), width="stretch")
    st.dataframe(inv[inv["stock_status"] != "healthy"].sort_values("days_of_cover"), hide_index=True, width="stretch")

with tab_ops:
    st.caption("Everything below comes from the audit schema written by the pipeline itself.")
    health = q("""select table_name, count(*) as batches, sum(rows_extracted) as extracted, sum(rows_valid) as loaded,
                  sum(rows_quarantined) as quarantined, sum(duplicates_removed) as dupes,
                  round(100.0 * sum(rows_quarantined) / nullif(sum(rows_extracted), 0), 2) as quarantine_pct,
                  max(finished_at) as last_success from audit.ingestion_batches where status = 'success' group by 1 order by 1""")
    st.dataframe(health, hide_index=True, width="stretch")
    failed = q("select batch_id, error, finished_at from audit.ingestion_batches where status = 'failed' order by finished_at desc limit 10")
    st.subheader("Recent failures")
    st.dataframe(failed, hide_index=True, width="stretch") if not failed.empty else st.success("No failed batches")
    versions = q("select version_number, count(*) as customers from marts.dim_customer where customer_id > 0 group by 1 order by 1")
    st.subheader("SCD Type 2: customer versions")
    st.dataframe(versions, hide_index=True, width="stretch")
    cost = q("select component, round(est_monthly_usd::numeric, 4) as est_monthly_usd, bytes_stored from audit.cost_metrics "
             "where metric_date = (select max(metric_date) from audit.cost_metrics) order by 2 desc")
    st.subheader("Estimated monthly cost (latest)")
    st.dataframe(cost, hide_index=True, width="stretch")
