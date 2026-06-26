from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import settings, universes
from src.providers.yahoo import YahooProvider
from src.scoring.engine import score_snapshot
from src.services.screener import ScreenerService
from src.valuation.dcf import dcf_value


st.set_page_config(
    page_title="Value Compass",
    page_icon="🧭",
    layout="wide",
)

CFG = settings()
UNIVERSES = universes()


st.title("🧭 Value Compass")
st.caption(
    "Cribado diario de índices + análisis fundamental "
    "y valoración por empresa"
)


with st.sidebar:
    page = st.radio(
        "Módulo",
        [
            "Radar del índice",
            "Análisis individual",
            "Valoración DCF",
            "Metodología y datos",
        ],
    )

    st.divider()

    st.info(
        "Las señales automáticas son preliminares. "
        "Verifica las cifras materiales en informes oficiales "
        "antes de invertir."
    )


if page == "Radar del índice":
    st.header("Radar diario del universo")

    universe_name = st.selectbox(
        "Universo",
        list(UNIVERSES.keys()),
        format_func=lambda x: UNIVERSES[x].get("label", x),
    )

    default_tickers = UNIVERSES[universe_name].get("tickers", [])

    raw = st.text_area(
        "Tickers (uno por línea o separados por comas)",
        value="\n".join(default_tickers),
        height=180,
    )

    tickers = [
        item.strip().upper()
        for item in raw.replace(",", "\n").splitlines()
        if item.strip()
    ]

    c1, c2 = st.columns([1, 3])

    with c1:
        run = st.button(
            "Ejecutar cribado ahora",
            type="primary",
            use_container_width=True,
        )

    with c2:
        st.caption(
            "La ejecución programada usa la misma lógica y guarda "
            "CSV, Excel, JSON y el histórico en SQLite."
        )

    if run:
        if not tickers:
            st.warning("Introduce al menos un ticker.")
        else:
            with st.spinner(
                f"Analizando {len(tickers)} compañías..."
            ):
                try:
                    df_result = ScreenerService(CFG).run(
                        universe_name,
                        tickers,
                    )
                    st.session_state["screen_df"] = df_result
                    st.session_state["screen_universe"] = universe_name
                except Exception as exc:
                    st.error(
                        "No se pudo completar el cribado: "
                        f"{exc}"
                    )

    df = None

    stored_universe = st.session_state.get("screen_universe")

    if stored_universe == universe_name:
        df = st.session_state.get("screen_df")

    if df is None:
        export_path = Path("data/exports")

        files = sorted(
            export_path.glob(
                f"{universe_name}_screening_*.csv"
            ),
            reverse=True,
        )

        if files:
            try:
                df = pd.read_csv(files[0])
            except Exception as exc:
                st.warning(
                    "No se pudo cargar el último archivo guardado: "
                    f"{exc}"
                )

    if df is None or df.empty:
        st.info(
            "Ejecuta el cribado para generar el radar del índice."
        )

    else:
        df = df.copy()

        numeric_columns = [
            "price",
            "global_score",
            "valuation",
            "quality",
            "cash",
            "balance",
            "growth",
            "risk",
            "confidence",
            "market_cap",
        ]

        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        if "recommendation" not in df.columns:
            df["recommendation"] = "SIN CLASIFICAR"

        entries = df[
            df["recommendation"].isin(
                [
                    "ENTRADA CLARA",
                    "ENTRADA / COMPRA PARCIAL",
                ]
            )
        ]

        metric_1, metric_2, metric_3, metric_4 = st.columns(4)

        metric_1.metric(
            "Compañías",
            len(df),
        )

        metric_2.metric(
            "Entradas",
            len(entries),
        )

        global_score_mean = (
            df["global_score"].mean()
            if "global_score" in df.columns
            else np.nan
        )

        confidence_mean = (
            df["confidence"].mean()
            if "confidence" in df.columns
            else np.nan
        )

        metric_3.metric(
            "Score medio",
            (
                f"{global_score_mean:.1f}"
                if pd.notna(global_score_mean)
                else "n.d."
            ),
        )

        metric_4.metric(
            "Confianza media",
            (
                f"{confidence_mean:.0f}%"
                if pd.notna(confidence_mean)
                else "n.d."
            ),
        )

        desired_display_columns = [
            "ticker",
            "name",
            "price",
            "global_score",
            "valuation",
            "quality",
            "cash",
            "balance",
            "growth",
            "risk",
            "confidence",
            "recommendation",
        ]

        display_columns = [
            column
            for column in desired_display_columns
            if column in df.columns
        ]

        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True,
        )

        required_chart_columns = {
            "ticker",
            "valuation",
            "quality",
            "global_score",
        }

        if not required_chart_columns.issubset(df.columns):
            missing_columns = sorted(
                required_chart_columns.difference(df.columns)
            )

            st.warning(
                "No se puede generar el mapa porque faltan "
                f"estas columnas: {', '.join(missing_columns)}."
            )

        else:
            radar_df = df.dropna(
                subset=[
                    "valuation",
                    "quality",
                    "global_score",
                ]
            ).copy()

            if radar_df.empty:
                st.warning(
                    "No hay suficientes datos válidos para mostrar "
                    "el mapa valoración–calidad."
                )

            else:
                if "market_cap" not in radar_df.columns:
                    radar_df["market_cap"] = np.nan

                radar_df["market_cap"] = (
                    pd.to_numeric(
                        radar_df["market_cap"],
                        errors="coerce",
                    )
                    .replace([np.inf, -np.inf], np.nan)
                )

                valid_market_caps = radar_df.loc[
                    radar_df["market_cap"].notna()
                    & (radar_df["market_cap"] > 0),
                    "market_cap",
                ]

                fallback_market_cap = (
                    float(valid_market_caps.median())
                    if not valid_market_caps.empty
                    else 1.0
                )

                radar_df["market_cap"] = (
                    radar_df["market_cap"]
                    .fillna(fallback_market_cap)
                    .clip(lower=1.0)
                )

                minimum_cap = radar_df["market_cap"].min()
                maximum_cap = radar_df["market_cap"].max()

                if maximum_cap > minimum_cap:
                    radar_df["marker_size"] = (
                        10
                        + 40
                        * (
                            np.log10(radar_df["market_cap"])
                            - np.log10(minimum_cap)
                        )
                        / (
                            np.log10(maximum_cap)
                            - np.log10(minimum_cap)
                        )
                    )
                else:
                    radar_df["marker_size"] = 20.0

                fig = px.scatter(
                    radar_df,
                    x="valuation",
                    y="quality",
                    size="marker_size",
                    size_max=45,
                    hover_name="ticker",
                    color="global_score",
                    custom_data=[
                        "market_cap",
                        "global_score",
                    ],
                    title="Mapa valoración–calidad",
                    labels={
                        "valuation": "Valoración",
                        "quality": "Calidad",
                        "global_score": "Score global",
                    },
                )

                fig.update_traces(
                    hovertemplate=(
                        "<b>%{hovertext}</b><br>"
                        "Valoración: %{x:.1f}<br>"
                        "Calidad: %{y:.1f}<br>"
                        "Score global: %{customdata[1]:.1f}<br>"
                        "Capitalización: "
                        "%{customdata[0]:,.0f}"
                        "<extra></extra>"
                    )
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

        download_col_1, download_col_2 = st.columns(2)

        with download_col_1:
            st.download_button(
                label="Descargar CSV",
                data=df.to_csv(
                    index=False,
                ).encode("utf-8"),
                file_name=f"{universe_name}_radar.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with download_col_2:
            st.download_button(
                label="Descargar JSON",
                data=df.to_json(
                    orient="records",
                    force_ascii=False,
                    indent=2,
                ),
                file_name=f"{universe_name}_radar.json",
                mime="application/json",
                use_container_width=True,
            )


elif page == "Análisis individual":
    st.header("Ficha individual")

    ticker = st.text_input(
        "Ticker",
        "ITX.MC",
    ).strip().upper()

    if st.button(
        "Cargar empresa",
        type="primary",
    ):
        if not ticker:
            st.warning("Introduce un ticker.")
        else:
            try:
                with st.spinner(
                    f"Cargando información de {ticker}..."
                ):
                    snap = YahooProvider().get_snapshot(ticker)

                    score = score_snapshot(
                        snap,
                        CFG["weights"],
                        CFG["screening"][
                            "recommendation_thresholds"
                        ],
                        CFG["app"][
                            "min_confidence_for_entry"
                        ],
                    )

                    st.session_state["snap"] = snap.to_dict()
                    st.session_state["score"] = score.to_dict()

            except Exception as exc:
                st.error(
                    "No se pudo cargar la empresa: "
                    f"{exc}"
                )

    if (
        "snap" in st.session_state
        and "score" in st.session_state
    ):
        snapshot = st.session_state["snap"]
        company_score = st.session_state["score"]

        company_name = snapshot.get(
            "name",
            snapshot.get("ticker", "Empresa"),
        )

        company_ticker = snapshot.get(
            "ticker",
            ticker,
        )

        st.subheader(
            f"{company_name} · {company_ticker}"
        )

        x1, x2, x3, x4 = st.columns(4)

        price = snapshot.get("price")

        x1.metric(
            "Precio",
            price if price is not None else "n.d.",
        )

        x2.metric(
            "Score global",
            company_score.get(
                "global_score",
                "n.d.",
            ),
        )

        confidence = company_score.get("confidence")

        x3.metric(
            "Confianza",
            (
                f"{confidence}%"
                if confidence is not None
                else "n.d."
            ),
        )

        x4.metric(
            "Decisión preliminar",
            company_score.get(
                "recommendation",
                "n.d.",
            ),
        )

        rationale = company_score.get("rationale")

        if rationale:
            st.write(rationale)

        score_dimensions = {
            "Valoración": company_score.get("valuation"),
            "Calidad": company_score.get("quality"),
            "Caja": company_score.get("cash"),
            "Balance": company_score.get("balance"),
            "Crecimiento": company_score.get("growth"),
            "Capital allocation": company_score.get(
                "capital_allocation"
            ),
            "Momentum fundamental": company_score.get(
                "momentum_fundamental"
            ),
            "Riesgo": company_score.get("risk"),
        }

        score_df = pd.DataFrame(
            {
                "Dimensión": list(score_dimensions.keys()),
                "Score": list(score_dimensions.values()),
            }
        )

        score_df["Score"] = pd.to_numeric(
            score_df["Score"],
            errors="coerce",
        )

        score_df = score_df.dropna(
            subset=["Score"]
        )

        if not score_df.empty:
            score_figure = px.bar(
                score_df,
                x="Dimensión",
                y="Score",
                range_y=[0, 100],
                title="Puntuación por dimensión",
            )

            st.plotly_chart(
                score_figure,
                use_container_width=True,
            )

        st.dataframe(
            pd.DataFrame([snapshot])
            .T
            .rename(columns={0: "Valor"}),
            use_container_width=True,
        )


elif page == "Valoración DCF":
    st.header("DCF configurable")

    c1, c2, c3 = st.columns(3)

    fcf0 = c1.number_input(
        "FCF normalizado inicial",
        value=1000.0,
    )

    growth = (
        c2.number_input(
            "Crecimiento anual",
            value=6.0,
            step=0.5,
        )
        / 100
    )

    years = c3.slider(
        "Años explícitos",
        3,
        10,
        5,
    )

    c4, c5, c6 = st.columns(3)

    wacc = (
        c4.number_input(
            "WACC",
            value=9.0,
            step=0.25,
        )
        / 100
    )

    terminal = (
        c5.number_input(
            "Crecimiento terminal",
            value=2.5,
            step=0.25,
        )
        / 100
    )

    net_debt = c6.number_input(
        "Deuda neta",
        value=0.0,
    )

    shares = st.number_input(
        "Acciones diluidas",
        value=100.0,
        min_value=0.000001,
    )

    if st.button(
        "Calcular valor intrínseco",
        type="primary",
    ):
        try:
            result = dcf_value(
                fcf0,
                growth,
                years,
                wacc,
                terminal,
                net_debt,
                shares,
            )

            a, b, c = st.columns(3)

            a.metric(
                "Enterprise value",
                f"{result.enterprise_value:,.0f}",
            )

            b.metric(
                "Equity value",
                f"{result.equity_value:,.0f}",
            )

            value_per_share = result.value_per_share

            c.metric(
                "Valor por acción",
                (
                    f"{value_per_share:,.2f}"
                    if value_per_share is not None
                    else "n.d."
                ),
            )

            projected_fcf_df = pd.DataFrame(
                {
                    "Año": range(
                        1,
                        len(result.projected_fcfs) + 1,
                    ),
                    "FCF proyectado": result.projected_fcfs,
                }
            ).set_index("Año")

            st.line_chart(
                projected_fcf_df,
            )

        except ValueError as exc:
            st.error(str(exc))

        except Exception as exc:
            st.error(
                "No se pudo completar la valoración: "
                f"{exc}"
            )


else:
    st.header("Metodología")

    st.markdown(
        """
**Dos niveles de análisis**

1. El radar diario recorre el universo completo con una
   precarga homogénea y un scoring provisional.
2. La ficha individual permite validar fuentes oficiales,
   normalizar la caja y ejecutar una valoración detallada.

**Principios:** separación entre calidad y precio, creación
de valor por acción, normalización del FCF, prudencia ante
datos incompletos, trazabilidad y versionado.
"""
    )

    st.code(
        "streamlit run app.py",
        language="bash",
    )
