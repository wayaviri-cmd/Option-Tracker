import datetime as dt
from datetime import timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Minimal Page Config
st.set_page_config(page_title="Option Premium Tracker", layout="centered")

# Custom CSS for compact inputs, hidden Streamlit chrome, and small green button
st.markdown("""
<style>
    /* Hide top padding and header lines */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 700px !important;
    }
    #MainMenu, footer, header {visibility: hidden;}

    /* Tighten input labels & form spacing */
    .stTextInput > label, .stSelectbox > label, .stNumberInput > label {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.1rem !important;
    }
    [data-testid="stForm"] {
        border: 1px solid #2d3748 !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        background-color: #0e1117;
    }

    /* Small Green Run Button */
    div.stButton > button {
        background-color: #2e7d32 !important;
        color: white !important;
        border: none !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 0.35rem 1.2rem !important;
        border-radius: 5px !important;
        height: auto !important;
        min-height: unset !important;
    }
    div.stButton > button:hover {
        background-color: #1b5e20 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Compact Single-Row Input Form
with st.form("scanner_form"):
    c1, c2, c3, c4 = st.columns([1.5, 1.2, 1.2, 1.2])
    with c1:
        ticker_input = st.text_input("Ticker", value="GOOG").strip().upper()
    with c2:
        side_choice = st.selectbox("Side", ["Call", "Put"], index=0)
    with c3:
        pct_step = st.number_input("Step %", min_value=0.5, max_value=10.0, value=2.0, step=0.5) / 100.0
    with c4:
        st.markdown("<div style='height: 1.6rem;'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Run")

MAX_DAYS_AHEAD = 30  # Fixed 30-day lookahead

if submitted or "first_load" not in st.session_state:
    st.session_state["first_load"] = True

    run_time_utc = dt.datetime.now(timezone.utc)
    run_timestamp_str = run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    try:
        ticker = yf.Ticker(ticker_input)
        
        # 1. Fetch current price
        hist = ticker.history(period="5d")
        if hist.empty:
            st.error(f"Could not load price for '{ticker_input}'.")
            st.stop()

        current_price = float(hist["Close"].iloc[-1])
        side = side_choice.lower()

        # 2. Expirations within 30 days
        all_options = ticker.options
        if not all_options:
            st.warning(f"No option chain returned for {ticker_input}.")
            st.stop()

        today = run_time_utc.date()
        expirations = []
        for s in all_options:
            try:
                d = dt.datetime.strptime(s, "%Y-%m-%d").date()
                if 0 <= (d - today).days <= MAX_DAYS_AHEAD:
                    expirations.append(d)
            except Exception:
                continue

        expirations.sort()

        # Fallback if no dates fall inside 30 days
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
            st.warning("No upcoming expiration dates found.")
            st.stop()

        # 3. Strike calculation (+2% calls, -2% puts)
        direction = 1 if side == "call" else -1
        strikes = sorted([
            round(current_price * (1 + direction * pct_step * i), 1)
            for i in range(4)
        ])

        # 4. Collect Last prices
        data = {s: [] for s in strikes}
        valid_dates = []

        with st.spinner("Fetching option chain..."):
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
            st.warning("No contracts available for the selected dates.")
            st.stop()

        # 5. Clean Plotly Figure
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
            title={
                'text': f"<b>{ticker_input}</b> {side.upper()}s &nbsp;|&nbsp; Spot: <b>{current_price:.2f}</b><br><sup>Run: {run_timestamp_str}</sup>",
                'x': 0.02,
                'xanchor': 'left',
                'font': {'size': 15}
            },
            xaxis_title=None,
            yaxis_title="Last Premium",
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.32,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=10, r=10, t=55, b=60),
            annotations=[
                dict(
                    text=f"Valid at snapshot: {run_timestamp_str}",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=-0.42,
                    xanchor="center",
                    yanchor="top",
                    font=dict(size=9, color="#718096")
                )
            ]
        )

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    except Exception as e:
        st.error(f"Error: {e}")
