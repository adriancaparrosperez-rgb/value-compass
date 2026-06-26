from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from src.config import settings, universes
from src.services.screener import ScreenerService
from src.providers.yahoo import YahooProvider
from src.scoring.engine import score_snapshot
from src.valuation.dcf import dcf_value

st.set_page_config(page_title="Value Compass", page_icon="🧭", layout="wide")
CFG = settings(); UNIVERSES = universes()

st.title("🧭 Value Compass")
st.caption("Cribado diario de índices + análisis fundamental y valoración por empresa")

with st.sidebar:
    page = st.radio("Módulo", ["Radar del índice", "Análisis individual", "Valoración DCF", "Metodología y datos"])
    st.divider()
    st.info("Las señales automáticas son preliminares. Verifica las cifras materiales en informes oficiales antes de invertir.")

if page == "Radar del índice":
    st.header("Radar diario del universo")
    universe_name = st.selectbox("Universo", list(UNIVERSES.keys()), format_func=lambda x: UNIVERSES[x].get("label", x))
    raw = st.text_area("Tickers (uno por línea o separados por comas)", value="\n".join(UNIVERSES[universe_name].get("tickers", [])), height=180)
    tickers = [x.strip().upper() for x in raw.replace(",", "\n").splitlines() if x.strip()]
    c1, c2 = st.columns([1,3])
    with c1:
        run = st.button("Ejecutar cribado ahora", type="primary", use_container_width=True)
    with c2:
        st.caption("La ejecución programada usa la misma lógica y guarda CSV, Excel, JSON y el histórico en SQLite.")
    if run:
        with st.spinner(f"Analizando {len(tickers)} compañías..."):
            df = ScreenerService(CFG).run(universe_name, tickers)
            st.session_state["screen_df"] = df
    df = st.session_state.get("screen_df")
    if df is None:
        files = sorted(Path("data/exports").glob(f"{universe_name}_screening_*.csv"), reverse=True)
        if files:
            df = pd.read_csv(files[0])
    if df is not None and not df.empty:
        entries = df[df["recommendation"].isin(["ENTRADA CLARA", "ENTRADA / COMPRA PARCIAL"])]
        a,b,c,d = st.columns(4)
        a.metric("Compañías", len(df)); b.metric("Entradas", len(entries)); c.metric("Score medio", f"{df.global_score.mean():.1f}"); d.metric("Confianza media", f"{df.confidence.mean():.0f}%")
        display_cols = ["ticker","name","price","global_score","valuation","quality","cash","balance","growth","risk","confidence","recommendation"]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        import numpy as np
import pandas as pd

# Asegurar columnas numéricas
numeric_columns = ["valuation", "quality", "market_cap", "global_score"]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

# El gráfico necesita valoración y calidad válidas
radar_df = df.dropna(subset=["valuation", "quality"]).copy()

# Plotly no admite NaN ni valores negativos en el tamaño
valid_market_caps = radar_df.loc[
    radar_df["market_cap"].notna() & (radar_df["market_cap"] > 0),
    "market_cap",
]

fallback_market_cap = (
    valid_market_caps.median()
    if not valid_market_caps.empty
    else 1.0
)

radar_df["market_cap"] = (
    radar_df["market_cap"]
    .replace([np.inf, -np.inf], np.nan)
    .fillna(fallback_market_cap)
    .clip(lower=1.0)
)

if radar_df.empty:
    st.warning("No hay suficientes datos válidos para mostrar el mapa valoración–calidad.")
else:
    fig = px.scatter(
        radar_df,
        x="valuation",
        y="quality",
        size="market_cap",
        size_max=45,
        hover_name="ticker",
        color="global_score",
        title="Mapa valoración–calidad",
    )

if radar_df.empty:
    st.warning(
        "No hay suficientes datos válidos para mostrar "
        "el mapa valoración–calidad."
    )
else:
    fig = px.scatter(
        radar_df,
        x="valuation",
        y="quality",
        size="marker_size",
        size_max=45,
        hover_name="ticker",
        color="global_score",
        custom_data=["market_cap"],
        title="Mapa valoración–calidad",
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Valoración: %{x:.1f}<br>"
            "Calidad: %{y:.1f}<br>"
            "Capitalización: %{customdata[0]:,.0f}"
            "<extra></extra>"
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        label="Descargar CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{universe_name}_radar.csv",
        mime="text/csv",
    )

    st.download_button(
        label="Descargar JSON",
        data=df.to_json(
            orient="records",
            force_ascii=False,
            indent=2,
        ),
        file_name=f"{universe_name}_radar.json",
        mime="application/json",
    )
    
    fig = px.scatter(
        radar_df,
        x="valuation",
        y="quality",
        size="marker_size",
        size_max=45,
        hover_name="ticker",
        color="global_score",
        custom_data=["market_cap"],
        title="Mapa valoración–calidad",
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Valoración: %{x:.1f}<br>"
            "Calidad: %{y:.1f}<br>"
            "Capitalización: %{customdata[0]:,.0f}"
            "<extra></extra>"
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Descargar CSV",
        df.to_csv(index=False).encode("utf-8"),
        f"{universe_name}_radar.csv",
        "text/csv",
    )

    st.download_button(
        "Descargar JSON",
        df.to_json(
            orient="records",
            force_ascii=False,
            indent=2,
        ),
        f"{universe_name}_radar.json",
        "application/json",
    )

        st.download_button("Descargar CSV", df.to_csv(index=False).encode("utf-8"), f"{universe_name}_radar.csv", "text/csv")
        st.download_button("Descargar JSON", df.to_json(orient="records", force_ascii=False, indent=2), f"{universe_name}_radar.json", "application/json")

elif page == "Análisis individual":
    st.header("Ficha individual")
    ticker = st.text_input("Ticker", "ITX.MC").strip().upper()
    if st.button("Cargar empresa", type="primary"):
        snap = YahooProvider().get_snapshot(ticker)
        score = score_snapshot(snap, CFG["weights"], CFG["screening"]["recommendation_thresholds"], CFG["app"]["min_confidence_for_entry"])
        st.session_state["snap"] = snap.to_dict(); st.session_state["score"] = score.to_dict()
    if "snap" in st.session_state:
        s = st.session_state["snap"]; sc = st.session_state["score"]
        st.subheader(f"{s['name']} · {s['ticker']}")
        x1,x2,x3,x4 = st.columns(4)
        x1.metric("Precio", s.get("price") or "n.d."); x2.metric("Score global", sc["global_score"]); x3.metric("Confianza", f"{sc['confidence']}%"); x4.metric("Decisión preliminar", sc["recommendation"])
        st.write(sc["rationale"])
        score_df = pd.DataFrame({"Dimensión":["Valoración","Calidad","Caja","Balance","Crecimiento","Capital allocation","Momentum fundamental","Riesgo"],"Score":[sc["valuation"],sc["quality"],sc["cash"],sc["balance"],sc["growth"],sc["capital_allocation"],sc["momentum_fundamental"],sc["risk"]]})
        st.plotly_chart(px.bar(score_df, x="Dimensión", y="Score", range_y=[0,100]), use_container_width=True)
        st.dataframe(pd.DataFrame([s]).T.rename(columns={0:"Valor"}), use_container_width=True)

elif page == "Valoración DCF":
    st.header("DCF configurable")
    c1,c2,c3 = st.columns(3)
    fcf0 = c1.number_input("FCF normalizado inicial", value=1000.0)
    growth = c2.number_input("Crecimiento anual", value=6.0, step=0.5) / 100
    years = c3.slider("Años explícitos", 3, 10, 5)
    c4,c5,c6 = st.columns(3)
    wacc = c4.number_input("WACC", value=9.0, step=0.25) / 100
    terminal = c5.number_input("Crecimiento terminal", value=2.5, step=0.25) / 100
    net_debt = c6.number_input("Deuda neta", value=0.0)
    shares = st.number_input("Acciones diluidas", value=100.0)
    if st.button("Calcular valor intrínseco", type="primary"):
        try:
            r = dcf_value(fcf0,growth,years,wacc,terminal,net_debt,shares)
            a,b,c = st.columns(3)
            a.metric("Enterprise value", f"{r.enterprise_value:,.0f}"); b.metric("Equity value", f"{r.equity_value:,.0f}"); c.metric("Valor por acción", f"{r.value_per_share:,.2f}" if r.value_per_share else "n.d.")
            st.line_chart(pd.DataFrame({"FCF proyectado":r.projected_fcfs}, index=range(1,years+1)))
        except ValueError as exc:
            st.error(str(exc))

else:
    st.header("Metodología")
    st.markdown("""
    **Dos niveles de análisis**
    1. El radar diario recorre el universo completo con una precarga homogénea y scoring provisional.
    2. La ficha individual permite validar fuentes oficiales, normalizar caja y ejecutar valoración detallada.

    **Principios**: separación entre calidad y precio, creación de valor por acción, normalización del FCF, prudencia ante datos incompletos, trazabilidad y versionado.
    """)
    st.code("streamlit run app.py", language="bash")
