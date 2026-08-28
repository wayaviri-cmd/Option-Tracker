import datetime as dt
from datetime import timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# App Configuration
st.set_page_config(page_title="Options Tracker", layout="centered", initial_sidebar_state="collapsed")

# Aggressive Mobile Single-Page CSS
st.markdown("""
<style>
    /* Remove padding to fit entirely on one phone screen */
    .block-container {
        padding-top: 0.1rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
        max-width: 100% !important;
    }
    
    /* Completely kill Streamlit headers, badges, and floating bottom widgets */
    #MainMenu, footer, header, [data-testid="stStatusWidget"], 
    .viewerBadge_container, [data-testid="stDecoration"],
    div[class*="viewerBadge"], iframe[title*="streamlit"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    /* Force bottom inputs into a single compact horizontal line */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: flex-end !important;
        gap: 4px !important;
        margin-top: 0.2rem !important;
    }
    [data-testid="column"] {
        width: auto !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        padding: 0 !important;
    }

    /* Compact inputs */
    .stTextInput > label, .stSelectbox > label, .stNumberInput > label {
        font-size: 0.65rem !important;
        line-height: 1 !important;
        margin-bottom: 1px !important;
        color: #9ca3af !important;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        min-height: 30px !important;
        height: 30px !important;
        font-size: 0.80rem !important;
        padding: 0 4px !important;
        border-radius: 4px !important;
        background-color: #111827 !important;
        color: #ffffff !important;
        border: 1px solid #374151 !important;
    }

    /* Small Green Run Button */
    div.stButton {
        margin-top: 0px !important;
    }
    div.stButton > button {
        background-color: #15803d !important;
        color: #ffffff !important;
        border: 1px solid #166534 !important;
        font-size: 0.80rem !important;
        font-weight: 700 !important;
        height: 30px !important;
        min-height: 30px !important;
        width: 100% !important;
        padding: 0 !important;
        border-radius: 4px !important;
    }
    div.stButton > button:hover {
        background-color: #166534 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State values for inputs
if "ticker" not in st.session_state:
    st.session_state["ticker"] = "INTC"
if "side" not in st.session_state:
    st.session_state["side"] = "Put"
if "step_pct" not in st.session_state:
    st.session_state["step_pct"] = 2.0

MAX_DAYS_AHEAD = 30
run_time_utc = dt.datetime.now(timezone.utc)
run_timestamp_str = run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

# ----------------- 1. DATA PROCESSING & PLOT AT TOP -----------------
try:
    ticker = yf.Ticker(st.session_state["ticker"])
    hist = ticker.history(period="5d")
    
    if hist.empty:
        st.error(f"Could not load '{st.session_state['ticker']}'.")
    else:
        current_price = float(hist["Close"].iloc[-1])
        side = st.session_state["side"].lower()
        pct_step = st.session_state["step_pct"] / 100.0

        all_options = ticker.options
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

        if valid_dates:
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
                height=450,  # Scaled to fit comfortably above the bottom inputs
                title={
                    'text': f"<b>{st.session_state['ticker']}</b> {side.upper()}s | Spot: <b>{current_price:.2f}</b>",
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
                # Inside Top-Left Legend
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
                margin=dict(l=8, r=5, t=30, b=25),
                annotations=[
                    dict(
                        text=f"Run: {run_timestamp_str}",
                        showarrow=False,
                        xref="paper",
                        yref="paper",
                        x=0.98,
                        y=-0.08,
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

# ----------------- 2. DATA ENTRY AT THE BOTTOM -----------------
c1, c2, c3, c4 = st.columns([1.3, 1.1, 1.0, 0.9])
with c1:
    ticker_val = st.text_input("Ticker", value=st.session_state["ticker"]).strip().upper()
with c2:
    side_val = st.selectbox("Side", ["Put", "Call"], index=0 if st.session_state["side"] == "Put" else 1)
with c3:
    step_val = st.number_input("Step %", min_value=0.5, max_value=10.0, value=st.session_state["step_pct"], step=0.5)
with c4:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("Run"):
        st.session_state["ticker"] = ticker_val
        st.session_state["side"] = side_val
        st.session_state["step_pct"] = step_val
        st.rerun()
