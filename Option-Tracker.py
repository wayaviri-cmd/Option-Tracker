import datetime as dt
import pytz
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# App Configuration
st.set_page_config(page_title="Option Strike vs Premium", layout="centered", initial_sidebar_state="collapsed")

# Mobile CSS: Lock entire app background to pure black (#000000 / #0e1117)
st.markdown("""
<style>
    /* Force root and app background to dark on iOS Safari/Chrome */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {
        background-color: #0b0f19 !important;
        color: #ffffff !important;
    }

    .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        max-width: 100% !important;
        background-color: #0b0f19 !important;
    }
    
    #MainMenu, footer, header, [data-testid="stStatusWidget"], 
    .viewerBadge_container, [data-testid="stDecoration"],
    div[class*="viewerBadge"], iframe[title*="streamlit"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    /* Input styling */
    .stTextInput > label, .stSelectbox > label, .stNumberInput > label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-bottom: 2px !important;
        color: #9ca3af !important;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        min-height: 36px !important;
        height: 36px !important;
        font-size: 0.90rem !important;
        padding: 0 8px !important;
        border-radius: 6px !important;
        background-color: #111827 !important;
        color: #ffffff !important;
        border: 1px solid #374151 !important;
    }

    /* Full-Width Green Run Button */
    div.stButton {
        margin-top: 0.4rem !important;
    }
    div.stButton > button {
        background-color: #15803d !important;
        color: #ffffff !important;
        border: 1px solid #166534 !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        height: 38px !important;
        width: 100% !important;
        border-radius: 6px !important;
    }
    div.stButton > button:hover {
        background-color: #166534 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "ticker" not in st.session_state:
    st.session_state["ticker"] = "INTC"
if "side" not in st.session_state:
    st.session_state["side"] = "Put"
if "step_pct" not in st.session_state:
    st.session_state["step_pct"] = 2.0

MAX_DAYS_AHEAD = 30

# New York Market Time (EDT/EST)
ny_tz = pytz.timezone("America/New_York")
run_time_ny = dt.datetime.now(ny_tz)
run_timestamp_str = run_time_ny.strftime("%Y-%m-%d %H:%M:%S %Z")

# ----------------- 1. CHART DISPLAY (TOP) -----------------
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
        today = run_time_ny.date()
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
            # 1. Centered Title (Font 22, White)
            st.markdown("<div style='text-align: center; color: #ffffff; font-size: 22px; font-weight: bold; line-height: 1.2;'>Option Strike vs Premium</div>", unsafe_allow_html=True)
            
            # 2. Date When Run in NY Time (Font 14, 80% White / #cccccc)
            st.markdown(f"<div style='text-align: center; color: #cccccc; font-size: 14px; margin-bottom: 4px;'>{run_timestamp_str}</div>", unsafe_allow_html=True)
            
            # 3. Centered Summary Header (Font 14, White)
            st.markdown(f"<div style='text-align: center; color: #ffffff; font-size: 14px; margin-bottom: 2px;'><b>Ticker:</b> {st.session_state['ticker']} &nbsp;|&nbsp; <b>Spot:</b> {current_price:.2f} &nbsp;|&nbsp; <b>Type:</b> {st.session_state['side']}</div>", unsafe_allow_html=True)

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
                height=360,
                paper_bgcolor='#0b0f19',
                plot_bgcolor='#0b0f19',
                xaxis=dict(
                    fixedrange=True,
                    tickfont=dict(size=12, color="#e5e7eb"),
                    showgrid=True,
                    gridcolor='#1e222d'
                ),
                yaxis=dict(
                    fixedrange=True,
                    title=dict(text="Premium - Last US / Stock", font=dict(size=16, color="#e5e7eb")),
                    tickfont=dict(size=14, color="#e5e7eb"),
                    showgrid=True,
                    gridcolor='#1e222d'
                ),
                template="plotly_dark",
                hovermode="x unified",
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
                margin=dict(l=8, r=5, t=10, b=20)
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

# ----------------- 2. MULTI-ROW DATA ENTRY (BOTTOM) -----------------
# Row 1: Ticker and Option Type
r1_col1, r1_col2 = st.columns(2)
with r1_col1:
    ticker_val = st.text_input("Ticker", value=st.session_state["ticker"]).strip().upper()
with r1_col2:
    side_val = st.selectbox("Option Type", ["Put", "Call"], index=0 if st.session_state["side"] == "Put" else 1)

# Row 2: Strike Step %
step_val = st.number_input("Strike Step %", min_value=0.5, max_value=10.0, value=st.session_state["step_pct"], step=0.5)

# Row 3: Run Button
if st.button("Run"):
    st.session_state["ticker"] = ticker_val
    st.session_state["side"] = side_val
    st.session_state["step_pct"] = step_val
    st.rerun()
