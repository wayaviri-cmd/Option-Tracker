import datetime as dt
from datetime import timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Options Tracker", layout="centered")
st.title("📈 Option Premium Tracker")

with st.form("input_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        ticker_input = st.text_input("Ticker Symbol", value="GOOG").strip().upper()
    with col2:
        side_choice = st.selectbox("Type", ["Call", "Put"], index=0)

    col3, col4 = st.columns(2)
    with col3:
        pct_step = st.number_input("Step %", min_value=0.5, max_value=10.0, value=2.0, step=0.5) / 100.0
    with col4:
        max_days = st.slider("Max Days Ahead", min_value=7, max_value=90, value=45, step=7)

    submitted = st.form_submit_button("Run Analysis", use_container_width=True)

if submitted or "first_load" not in st.session_state:
    st.session_state["first_load"] = True

    run_time_utc = dt.datetime.now(timezone.utc)
    run_timestamp_str = run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    try:
        ticker = yf.Ticker(ticker_input)
        hist = ticker.history(period="1d")
        if hist.empty:
            st.error(f"Could not load data for {ticker_input}. Please check the symbol.")
            st.stop()

        current_price = float(hist["Close"].iloc[-1])
        side = side_choice.lower()

        direction = 1 if side == "call" else -1
        strikes = sorted([
            round(current_price * (1 + direction * pct_step * i), 1)
            for i in range(4)
        ])

        today = run_time_utc.date()
        expirations = [
            dt.datetime.strptime(s, "%Y-%m-%d").date()
            for s in ticker.options
            if 0 <= (dt.datetime.strptime(s, "%Y-%m-%d").date() - today).days <= max_days
        ]
        expirations.sort()

        if not expirations:
            st.warning("No expirations found in this time window.")
            st.stop()

        data = {s: [] for s in strikes}
        for d in expirations:
            chain = ticker.option_chain(d.strftime("%Y-%m-%d"))
            df = chain.calls if side == "call" else chain.puts

            for s in strikes:
                if df.empty or "strike" not in df.columns:
                    data[s].append(None)
                    continue
                idx = (df["strike"] - s).abs().idxmin()
                val = df.loc[idx].get("lastPrice")
                data[s].append(float(val) if pd.notna(val) else None)

        fig = go.Figure()
        date_strings = [d.strftime("%b %d, %Y") for d in expirations]

        for strike, vals in data.items():
            p_pct_vals = [(v / strike * 100) if (v is not None and strike > 0) else None for v in vals]
            fig.add_trace(go.Scatter(
                x=date_strings,
                y=vals,
                customdata=p_pct_vals,
                mode="lines+markers",
                name=f"Strike {strike}",
                hovertemplate=f"<b>Strike:</b> {strike}<br><b>Last:</b> %{{y:.2f}}<br><b>P%:</b> %{{customdata:.2f}}%<extra></extra>"
            ))

        fig.update_layout(
            title={
                'text': f"<b>{ticker_input}</b> {side.upper()}s (Last Price)<br><sup>Spot: {current_price:.2f} | <b>Run:</b> {run_timestamp_str}</sup>",
                'x': 0.05,
                'xanchor': 'left'
            },
            xaxis_title="Expiration Date",
            yaxis_title="Last Premium",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=-0.45, xanchor="center", x=0.5),
            margin=dict(l=10, r=10, t=70, b=90),
            annotations=[
                dict(
                    text=f"Note: Model executed on {run_timestamp_str}. Option premiums valid strictly at this snapshot.",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=-0.55,
                    xanchor="center",
                    yanchor="top",
                    font=dict(size=9, color="gray")
                )
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
