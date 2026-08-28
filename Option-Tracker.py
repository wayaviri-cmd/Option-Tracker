import datetime as dt
from datetime import timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# App Configuration
st.set_page_config(page_title="Options Tracker", layout="centered", initial_sidebar_state="collapsed")

# Mobile CSS: Kill Streamlit floating bottom footer + force ultra-slim single row inputs
st.markdown("""
<style>
    /* Remove default Streamlit top/bottom viewport padding */
    .block-container {
        padding-top: 0.1rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
        max-width: 100% !important;
    }
    
    /* Completely eliminate bottom floating badges/toolbars */
    #MainMenu, footer, header, [data-testid="stStatusWidget"], 
    .viewerBadge_container, [data-testid="stDecoration"],
    div[class*="viewerBadge"], iframe[title*="streamlit"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    /* Force Streamlit Columns to STAY SIDE-BY-SIDE on mobile screens */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: flex-end !important;
        gap: 4px !important;
    }
    [data-testid="column"] {
        width: auto !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        padding: 0 !important;
    }

    /* Ultra-small labels & inputs */
    .stTextInput > label, .stSelectbox > label, .stNumberInput > label {
        font-size: 0.60rem !important;
        line-height: 1 !important;
        margin-bottom: 1px !important;
        color: #9ca3af !important;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        min-height: 28px !important;
        height: 28px !important;
        font-size: 0.75rem !important;
        padding: 0 4px !important;
        border-radius: 4px !important;
        background-color: #111827 !important;
        color: #ffffff !important;
        border: 1px solid #374151 !important;
    }

    /* Small Green Run Button without label offset */
    div.stButton {
        margin-top: 0px !important;
    }
    div.stButton > button {
        background-color: #15803d !important;
        color: #ffffff !important;
        border: 1px solid #166534 !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        height: 28px !important;
        min-height: 28px !important;
        width: 100% !important;
        padding: 0 !important;
        border-radius: 4px !important;
    }
    div.stButton > button:hover {
        background-color: #166534 !important;
    }
</style>
""", unsafe_allow_html=True)

# Ultra-Compact 1-Line Input Header
c1, c2, c3, c4 = st.columns([1.3, 1.1, 1.0, 0.9])
with c1:
    ticker_input = st.text_input("Ticker", value="INTC").strip().upper()
with c2:
    side_choice = st.selectbox("Side", ["Put", "Call"], index=0)
with c3:
    pct_step = st.number_input("Step %", min_value=0.5, max_value=10.0, value=2.0, step=0.5) / 100.0
with c4:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    submitted = st.button("Run")

MAX_DAYS_AHEAD = 30

run_time_utc = dt.datetime.now(timezone.utc)
run_timestamp_str = run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

try:
    ticker = yf.Ticker(ticker_input)
    hist = ticker.history(period="5d")
    
    if hist.empty:
        st.error(f"Could not load '{ticker_input}'.")
        st.stop()

    current_price = float(hist["Close"].iloc[-1])
    side = side_choice.lower()

    all_options = ticker.options
    if not all_options:
        st.warning(f"No option chain for {ticker_input}.")
        st.stop()

    today = run_time_utc.date()
    expirations = [
        dt.datetime.strptime(s, "%Y-%m-%d").date()
        for s in all_options
        if 0 <= (dt.datetime.strptime(s, "%Y-%m-%d").date() - today).days <= MAX_DAYS_AHEAD
    ]
    expirations.sort()

    if not expirations:
        for s in all_options:
            try:
                d = dt.datetime.strptime(s, "%Y-%m-%d").date()
                if (d - today).days >= 0:
                    expirations.append(d)
            except Exception:
                continue
        expirations.sort()
        expirations = expirations[:4]

    if not expirations:
        st.warning("No upcoming expiration dates.")
        st.stop()

    # Strikes calculation
    direction = 1 if side == "call" else -1
    strikes = sorted([
        round(current_price * (1 + direction * pct_step * i), 1)
        for i in range(4)
    ])

    data = {s: [] for s in strikes}
    valid_dates = []

    for d in expirations:
        date_str = d.strftime("%Y-%m-%d")
        try:
            chain = ticker.option_chain(date_str)
            df = chain.calls if side == "call" else chain.puts

            if df is None or df.empty or "strike" not in df.columns:
                continue

            valid_dates.append(d)
            for s in strikes:
                idx = (df["strike"] - s).abs().idxmin()
                val = df.loc[idx].get("lastPrice")
                data[s].append(float(val) if pd.notna(val) else None)
        except Exception:
            continue

    if not valid_dates:
        st.warning("No option chain data available.")
        st.stop()

    # Build Plot
    fig = go.Figure()
    date_strings = [d.strftime("%b %d") for d in valid_dates]

    for strike, vals in data.items():
        p_pct_vals = [(v / strike * 100) if (v is not None and strike > 0) else None for v in vals]
        fig.add_trace(go.Scatter(
            x=date_strings,
            y=vals,
            customdata=p_pct_vals,
            mode="lines+markers",
            name=f"{strike}",
            hovertemplate=f"<b>Strike:</b> {strike}<br><b>Last:</b> %{{y:.2f}}<br><b>P%:</b> %{{customdata:.2f}}%<extra></extra>"
        ))

    fig.update_layout(
        height=520,
        title={
            'text': f"<b>{ticker_input}</b> {side.upper()}s | Spot: <b>{current_price:.2f}</b>",
            'x': 0.02,
            'xanchor': 'left',
            'font': {'size': 14}
        },
        xaxis=dict(
            fixedrange=True,
            tickfont=dict(size=12, color="#e5e7eb"),
            showgrid=True,
            gridcolor='#1e222d'
        ),
        yaxis=dict(
            fixedrange=True,
            title=dict(text="Last", font=dict(size=12, color="#e5e7eb")),
            tickfont=dict(size=12, color="#e5e7eb"),
            showgrid=True,
            gridcolor='#1e222d'
        ),
        template="plotly_dark",
        hovermode="x unified",
        # Top-Left Inside Legend
        legend=dict(
            x=0.02,
            y=0.98,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(15, 23, 42, 0.75)',
            bordercolor='#374151',
            borderwidth=1,
            font=dict(size=12)
        ),
        # Extra 55px bottom margin ensures dates sit well above the browser toolbar
        margin=dict(l=10, r=5, t=30, b=55),
        annotations=[
            dict(
                text=f"Run: {run_timestamp_str}",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.98,
                y=-0.14,
                xanchor="right",
                yanchor="top",
                font=dict(size=8, color="#6b7280")
            )
        ]
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'displayModeBar': False,
            'responsive': True,
            'scrollZoom': False,
            'doubleClick': False
        }
    )

except Exception as e:
    st.error(f"Error: {e}")
