import datetime as dt
from datetime import timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Mobile Viewport & App Configuration
st.set_page_config(page_title="Options Tracker", layout="centered", initial_sidebar_state="collapsed")

# Mobile CSS: compact layout, 2x2 grid enforcement, small green button
st.markdown("""
<style>
    /* Remove padding around main container */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        max-width: 100% !important;
    }
    #MainMenu, footer, header { visibility: hidden; }

    /* Compact form container */
    [data-testid="stForm"] {
        border: 1px solid #262730 !important;
        padding: 0.5rem 0.6rem !important;
        border-radius: 8px !important;
        background-color: #0e1117;
        margin-bottom: 0.5rem;
    }

    /* Force horizontal column display on mobile */
    [data-testid="column"] {
        width: calc(50% - 0.3rem) !important;
        flex: 1 1 calc(50% - 0.3rem) !important;
        min-width: calc(50% - 0.3rem) !important;
    }

    /* Tighten labels and input heights */
    .stTextInput > label, .stSelectbox > label, .stNumberInput > label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-bottom: 0px !important;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        min-height: 34px !important;
        height: 34px !important;
        font-size: 0.85rem !important;
        padding: 0 6px !important;
    }

    /* Small Green Run Button */
    div.stButton > button {
        background-color: #2e7d32 !important;
        color: #ffffff !important;
        border: none !important;
        font-size: 0.85rem !important;
        font-weight: bold !important;
        padding: 0.3rem 0.6rem !important;
        height: 34px !important;
        width: 100% !important;
        border-radius: 6px !important;
        margin-top: 1.15rem !important;
    }
    div.stButton > button:hover {
        background-color: #1b5e20 !important;
    }
</style>
""", unsafe_allow_html=True)

# 2x2 Grid for Mobile
with st.form("compact_form"):
    r1_col1, r1_col2 = st.columns(2)
    with r1_col1:
        ticker_input = st.text_input("Ticker", value="GOOG").strip().upper()
    with r1_col2:
        side_choice = st.selectbox("Side", ["Call", "Put"], index=0)

    r2_col1, r2_col2 = st.columns(2)
    with r2_col1:
        pct_step = st.number_input("Step %", min_value=0.5, max_value=10.0, value=2.0, step=0.5) / 100.0
    with r2_col2:
        submitted = st.form_submit_button("Run")

MAX_DAYS_AHEAD = 30  # Default 30-day window

if submitted or "first_load" not in st.session_state:
    st.session_state["first_load"] = True

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
            st.warning(f"No option chain returned for {ticker_input}.")
            st.stop()

        today = run_time_utc.date()
        expirations = [
            dt.datetime.strptime(s, "%Y-%m-%d").date()
            for s in all_options
            if 0 <= (dt.datetime.strptime(s, "%Y-%m-%d").date() - today).days <= MAX_DAYS_AHEAD
        ]
        expirations.sort()

        # Fallback if 30d window has no weekly/monthly options
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

        # Generate strikes (+2% calls, -2% puts)
        direction = 1 if side == "call" else -1
        strikes = sorted([
            round(current_price * (1 + direction * pct_step * i), 1)
            for i in range(4)
        ])

        # Fetch option chain
        data = {s: [] for s in strikes}
        valid_dates = []

        with st.spinner("Loading..."):
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
            st.warning("No option chain contracts found.")
            st.stop()

        # Plotly chart configuration
        fig = go.Figure()
        date_strings = [d.strftime("%b %d") for d in valid_dates]

        for strike, vals in data.items():
            p_pct_vals = [(v / strike * 100) if (v is not None and strike > 0) else None for v in vals]
            fig.add_trace(go.Scatter(
                x=date_strings,
                y=vals,
                customdata=p_pct_vals,
                mode="lines+markers",
                name=f"{strike}",  # Numbers only, 'Strike' removed
                hovertemplate=f"<b>Strike:</b> {strike}<br><b>Last:</b> %{{y:.2f}}<br><b>P%:</b> %{{customdata:.2f}}%<extra></extra>"
            ))

        fig.update_layout(
            title={
                'text': f"<b>{ticker_input}</b> {side.upper()}s | Spot: <b>{current_price:.2f}</b>",
                'x': 0.02,
                'xanchor': 'left',
                'font': {'size': 13}
            },
            xaxis=dict(
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor='#1e222d'
            ),
            yaxis=dict(
                title=dict(text="Last Premium", font=dict(size=11)),
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor='#1e222d'
            ),
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.28,
                xanchor="center",
                x=0.5,
                font=dict(size=11)
            ),
            margin=dict(l=5, r=5, t=35, b=45),
            annotations=[
                dict(
                    text=f"Run: {run_timestamp_str}",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=-0.38,
                    xanchor="center",
                    yanchor="top",
                    font=dict(size=8, color="#718096")
                )
            ]
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={'displayModeBar': False, 'responsive': True}
        )

    except Exception as e:
        st.error(f"Error: {e}")
