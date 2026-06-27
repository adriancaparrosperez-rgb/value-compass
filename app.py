from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from src.config import settings, universes
from src.decision.service import execute_master_decision
from src.providers.yahoo import YahooProvider
from src.scoring.engine import score_snapshot
from src.services.master_analysis_builder import (
    build_master_analysis,
)
from src.services.screener import ScreenerService
from src.services.universe_loader import load_universe
from src.ui.streamlit_decision_renderer import (
    StreamlitDecisionRendererError,
    render_decision_response,
)
from src.valuation.dcf import dcf_value
st.set_page_config(
    page_title="Value Compass",
    page_icon="🧭",
    layout="wide",
)
CFG = settings()
UNIVERSES = universes()
SNAPSHOT_SERVICE = SnapshotService()
INDIVIDUAL_RESULT_STATE_KEY = (
    "value_compass_individual_result"
)
INDIVIDUAL_ERROR_STATE_KEY = (
    "value_compass_individual_error"
)
def _normalize_ticker(
    value: Any,
) -> str:
    if value is None:
        return ""
    return str(
        value
    ).strip().upper()
def _metric_display_value(
    value: Any,
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "n.d."
    if isinstance(
        value,
        (float, np.floating),
    ) and not np.isfinite(
        value
    ):
        return "n.d."
    return f"{value}{suffix}"
def _build_individual_result(
    ticker: str,
) -> dict[str, Any]:
    """
    Ejecuta la precarga, el scoring, la construcción del
    análisis maestro y el servicio de decisión.
    No modifica session_state. El resultado solo se almacena
    cuando el flujo completo ha terminado.
    """
    normalized_ticker = _normalize_ticker(
        ticker
    )
    if not normalized_ticker:
        raise ValueError(
            "El ticker no puede estar vacío."
        )
    snapshot_object = (
        SNAPSHOT_SERVICE.get_snapshot(
            normalized_ticker
        )
    )
    score_object = score_snapshot(
        snapshot_object,
        CFG["weights"],
        CFG["screening"][
            "recommendation_thresholds"
        ],
        CFG["app"][
            "min_confidence_for_entry"
        ],
    )
    master_analysis = build_master_analysis(
        snapshot_object,
        score_object,
    )
    decision_response = execute_master_decision(
        master_analysis
    )
    snapshot_data = snapshot_object.to_dict()
    score_data = score_object.to_dict()
    canonical_ticker = _normalize_ticker(
        snapshot_data.get(
            "ticker"
        )
    )
    return {
        "requested_ticker": normalized_ticker,
        "canonical_ticker": (
            canonical_ticker
            or normalized_ticker
        ),
        "snapshot": snapshot_data,
        "score": score_data,
        "decision_response": decision_response,
    }
def _store_individual_result(
    result: dict[str, Any],
) -> None:
    """
    Sustituye el resultado anterior de forma atómica.
    """
    st.session_state[
        INDIVIDUAL_RESULT_STATE_KEY
    ] = deepcopy(
        result
    )
    st.session_state.pop(
        INDIVIDUAL_ERROR_STATE_KEY,
        None,
    )
def _store_individual_error(
    ticker: str,
    message: str,
) -> None:
    st.session_state[
        INDIVIDUAL_ERROR_STATE_KEY
    ] = {
        "ticker": _normalize_ticker(
            ticker
        ),
        "message": str(
            message
        ).strip(),
    }
def _is_valid_individual_result(
    value: Any,
) -> bool:
    return (
        isinstance(
            value,
            dict,
        )
        and isinstance(
            value.get(
                "snapshot"
            ),
            dict,
        )
        and isinstance(
            value.get(
                "score"
            ),
            dict,
        )
        and isinstance(
            value.get(
                "decision_response"
            ),
            dict,
        )
    )
def _decision_response_json(
    response: dict[str, Any],
) -> str:
    try:
        return json.dumps(
            response,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except (
        TypeError,
        ValueError,
    ):
        return json.dumps(
            {
                "success": False,
                "error": {
                    "type": "SERIALIZATION_ERROR",
                    "message": (
                        "No se pudo serializar la respuesta "
                        "completa."
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
@st.cache_data(
    ttl=86400,
    show_spinner=False,
)
def get_universe_tickers(
    universe_key: str,
) -> tuple[list[str], str]:
    """Carga los componentes del universo y los conserva 24 horas."""
    definition = UNIVERSES[
        universe_key
    ]
    return load_universe(
        definition
    )
st.title(
    "🧭 Value Compass"
)
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
# ============================================================
# RADAR DEL ÍNDICE
# ============================================================
if page == "Radar del índice":
    st.header(
        "Radar diario del universo"
    )
    universe_name = st.selectbox(
        "Universo",
        list(
            UNIVERSES.keys()
        ),
        format_func=lambda key: (
            UNIVERSES[
                key
            ].get(
                "label",
                key,
            )
        ),
    )
    try:
        (
            default_tickers,
            universe_source,
        ) = get_universe_tickers(
            universe_name
        )
    except Exception as exc:
        default_tickers = []
        universe_source = "error"
        st.error(
            "No se pudo cargar el universo seleccionado: "
            f"{exc}"
        )
    source_labels = {
        "remote": (
            "componentes actualizados automáticamente"
        ),
        "static": (
            "lista configurada en el proyecto"
        ),
        "fallback": (
            "lista de respaldo"
        ),
        "error": (
            "universo no disponible"
        ),
    }
    st.caption(
        f"{len(default_tickers)} valores · "
        f"{source_labels.get(universe_source, universe_source)}"
    )
    raw = st.text_area(
        "Tickers (uno por línea o separados por comas)",
        value="\n".join(
            default_tickers
        ),
        height=220,
    )
    tickers = list(
        dict.fromkeys(
            item.strip().upper()
            for item in raw.replace(
                ",",
                "\n",
            ).splitlines()
            if item.strip()
        )
    )
    st.subheader(
        "Configuración de ejecución"
    )
    (
        batch_col_1,
        batch_col_2,
    ) = st.columns(
        2
    )
    with batch_col_1:
        batch_size = st.selectbox(
            "Compañías por lote",
            options=[
                25,
                50,
                75,
                100,
                150,
                200,
            ],
            index=1,
            help=(
                "Para índices grandes es recomendable ejecutar "
                "lotes de 25 o 50 compañías."
            ),
        )
    maximum_start = max(
        len(
            tickers
        ) - 1,
        0,
    )
    with batch_col_2:
        batch_start = st.number_input(
            "Empezar desde la posición",
            min_value=0,
            max_value=maximum_start,
            value=0,
            step=batch_size,
        )
    batch_start_int = int(
        batch_start
    )
    batch_size_int = int(
        batch_size
    )
    selected_tickers = tickers[
        batch_start_int:
        batch_start_int
        + batch_size_int
    ]
    batch_end = min(
        batch_start_int
        + len(
            selected_tickers
        ),
        len(
            tickers
        ),
    )
    if tickers:
        st.caption(
            f"Se analizarán las posiciones "
            f"{batch_start_int + 1}–{batch_end} "
            f"de {len(tickers)}."
        )
    else:
        st.caption(
            "No hay tickers disponibles en el universo "
            "seleccionado."
        )
    (
        button_col,
        info_col,
    ) = st.columns(
        [
            1,
            3,
        ]
    )
    with button_col:
        run = st.button(
            "Ejecutar cribado ahora",
            type="primary",
            use_container_width=True,
        )
    with info_col:
        st.caption(
            "La ejecución programada usa la misma lógica y guarda "
            "CSV, Excel, JSON y el histórico en SQLite."
        )
    if run:
        if not selected_tickers:
            st.warning(
                "No hay compañías en el lote seleccionado."
            )
        else:
            with st.spinner(
                f"Analizando {len(selected_tickers)} compañías..."
            ):
                try:
                    df_result = ScreenerService(
                        CFG
                    ).run(
                        universe_name,
                        selected_tickers,
                    )
                    st.session_state[
                        "screen_df"
                    ] = df_result
                    st.session_state[
                        "screen_universe"
                    ] = universe_name
                    st.session_state[
                        "screen_batch_start"
                    ] = batch_start_int
                except Exception as exc:
                    st.error(
                        "No se pudo completar el cribado: "
                        f"{exc}"
                    )
    df = None
    stored_universe = (
        st.session_state.get(
            "screen_universe"
        )
    )
    if (
        stored_universe
        == universe_name
    ):
        df = st.session_state.get(
            "screen_df"
        )
    if df is None:
        export_path = Path(
            "data/exports"
        )
        files = sorted(
            export_path.glob(
                f"{universe_name}_screening_*.csv"
            ),
            reverse=True,
        )
        if files:
            try:
                df = pd.read_csv(
                    files[
                        0
                    ]
                )
            except Exception as exc:
                st.warning(
                    "No se pudo cargar el último archivo guardado: "
                    f"{exc}"
                )
    if (
        df is None
        or df.empty
    ):
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
                df[
                    column
                ] = pd.to_numeric(
                    df[
                        column
                    ],
                    errors="coerce",
                )
        if (
            "recommendation"
            not in df.columns
        ):
            df[
                "recommendation"
            ] = "SIN CLASIFICAR"
        entries = df[
            df[
                "recommendation"
            ].isin(
                [
                    "ENTRADA CLARA",
                    (
                        "ENTRADA / "
                        "COMPRA PARCIAL"
                    ),
                ]
            )
        ]
        (
            metric_1,
            metric_2,
            metric_3,
            metric_4,
        ) = st.columns(
            4
        )
        metric_1.metric(
            "Compañías analizadas",
            len(
                df
            ),
        )
        metric_2.metric(
            "Entradas",
            len(
                entries
            ),
        )
        global_score_mean = (
            df[
                "global_score"
            ].mean()
            if (
                "global_score"
                in df.columns
            )
            else np.nan
        )
        confidence_mean = (
            df[
                "confidence"
            ].mean()
            if (
                "confidence"
                in df.columns
            )
            else np.nan
        )
        metric_3.metric(
            "Score medio",
            (
                f"{global_score_mean:.1f}"
                if pd.notna(
                    global_score_mean
                )
                else "n.d."
            ),
        )
        metric_4.metric(
            "Confianza media",
            (
                f"{confidence_mean:.0f}%"
                if pd.notna(
                    confidence_mean
                )
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
            for column
            in desired_display_columns
            if column in df.columns
        ]
        if display_columns:
            st.dataframe(
                df[
                    display_columns
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning(
                "El resultado no contiene columnas disponibles "
                "para mostrar."
            )
        required_chart_columns = {
            "ticker",
            "valuation",
            "quality",
            "global_score",
        }
        if not (
            required_chart_columns.issubset(
                df.columns
            )
        ):
            missing_columns = sorted(
                required_chart_columns.difference(
                    df.columns
                )
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
                if (
                    "market_cap"
                    not in radar_df.columns
                ):
                    radar_df[
                        "market_cap"
                    ] = np.nan
                radar_df[
                    "market_cap"
                ] = (
                    pd.to_numeric(
                        radar_df[
                            "market_cap"
                        ],
                        errors="coerce",
                    )
                    .replace(
                        [
                            np.inf,
                            -np.inf,
                        ],
                        np.nan,
                    )
                )
                valid_market_caps = radar_df.loc[
                    (
                        radar_df[
                            "market_cap"
                        ].notna()
                    )
                    & (
                        radar_df[
                            "market_cap"
                        ]
                        > 0
                    ),
                    "market_cap",
                ]
                fallback_market_cap = (
                    float(
                        valid_market_caps.median()
                    )
                    if not (
                        valid_market_caps.empty
                    )
                    else 1.0
                )
                radar_df[
                    "market_cap"
                ] = (
                    radar_df[
                        "market_cap"
                    ]
                    .fillna(
                        fallback_market_cap
                    )
                    .clip(
                        lower=1.0
                    )
                )
                minimum_cap = float(
                    radar_df[
                        "market_cap"
                    ].min()
                )
                maximum_cap = float(
                    radar_df[
                        "market_cap"
                    ].max()
                )
                if (
                    maximum_cap
                    > minimum_cap
                ):
                    log_minimum = np.log10(
                        minimum_cap
                    )
                    log_maximum = np.log10(
                        maximum_cap
                    )
                    radar_df[
                        "marker_size"
                    ] = (
                        10
                        + 40
                        * (
                            np.log10(
                                radar_df[
                                    "market_cap"
                                ]
                            )
                            - log_minimum
                        )
                        / (
                            log_maximum
                            - log_minimum
                        )
                    )
                else:
                    radar_df[
                        "marker_size"
                    ] = 20.0
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
                    title=(
                        "Mapa valoración–calidad"
                    ),
                    labels={
                        "valuation": (
                            "Valoración"
                        ),
                        "quality": (
                            "Calidad"
                        ),
                        "global_score": (
                            "Score global"
                        ),
                    },
                )
                fig.update_traces(
                    hovertemplate=(
                        "<b>%{hovertext}</b><br>"
                        "Valoración: %{x:.1f}<br>"
                        "Calidad: %{y:.1f}<br>"
                        "Score global: "
                        "%{customdata[1]:.1f}<br>"
                        "Capitalización: "
                        "%{customdata[0]:,.0f}"
                        "<extra></extra>"
                    )
                )
                fig.update_layout(
                    legend_title_text=(
                        "Score global"
                    ),
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )
        (
            download_col_1,
            download_col_2,
        ) = st.columns(
            2
        )
        with download_col_1:
            st.download_button(
                label="Descargar CSV",
                data=df.to_csv(
                    index=False,
                ).encode(
                    "utf-8"
                ),
                file_name=(
                    f"{universe_name}_radar_"
                    f"{batch_start_int + 1}_{batch_end}.csv"
                ),
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
                file_name=(
                    f"{universe_name}_radar_"
                    f"{batch_start_int + 1}_{batch_end}.json"
                ),
                mime="application/json",
                use_container_width=True,
            )
# ============================================================
# ANÁLISIS INDIVIDUAL
# ============================================================
elif page == "Análisis individual":
    st.header(
        "Análisis individual"
    )
    st.caption(
        "El radar realiza una primera clasificación. "
        "La decisión maestra aplica después los controles "
        "de calidad de datos, los gates y las reglas "
        "de prudencia."
    )
    stored_result = (
        st.session_state.get(
            INDIVIDUAL_RESULT_STATE_KEY
        )
    )
    default_ticker = "ITX.MC"
    if _is_valid_individual_result(
        stored_result
    ):
        stored_requested_ticker = (
            _normalize_ticker(
                stored_result.get(
                    "requested_ticker"
                )
            )
        )
        if stored_requested_ticker:
            default_ticker = (
                stored_requested_ticker
            )
    with st.form(
        "individual_analysis_form",
        clear_on_submit=False,
    ):
        ticker_input = st.text_input(
            "Ticker",
            value=default_ticker,
            help=(
                "Introduce el símbolo utilizado por Yahoo "
                "Finance, por ejemplo ITX.MC, META o ALV.DE."
            ),
        )
        submitted = (
            st.form_submit_button(
                "Ejecutar análisis completo",
                type="primary",
                use_container_width=True,
            )
        )
    requested_ticker = (
        _normalize_ticker(
            ticker_input
        )
    )
    if submitted:
        if not requested_ticker:
            _store_individual_error(
                requested_ticker,
                "Introduce un ticker.",
            )
        else:
            try:
                with st.spinner(
                    "Descargando, puntuando y aplicando "
                    f"el análisis maestro a {requested_ticker}..."
                ):
                    new_result = (
                        _build_individual_result(
                            requested_ticker
                        )
                    )
                _store_individual_result(
                    new_result
                )
                stored_result = deepcopy(
                    new_result
                )
            except ValueError as exc:
                _store_individual_error(
                    requested_ticker,
                    str(
                        exc
                    ),
                )
            except Exception as exc:
                _store_individual_error(
                    requested_ticker,
                    (
                        "No se pudo completar la descarga o "
                        f"el análisis de {requested_ticker}: {exc}"
                    ),
                )
    stored_error = (
        st.session_state.get(
            INDIVIDUAL_ERROR_STATE_KEY
        )
    )
    if isinstance(
        stored_error,
        dict,
    ):
        error_ticker = (
            _normalize_ticker(
                stored_error.get(
                    "ticker"
                )
            )
        )
        error_message = str(
            stored_error.get(
                "message",
                "",
            )
        ).strip()
        if (
            error_message
            and (
                not error_ticker
                or error_ticker
                == requested_ticker
            )
        ):
            st.error(
                error_message
            )
    valid_stored_result = (
        _is_valid_individual_result(
            stored_result
        )
    )
    if not valid_stored_result:
        st.info(
            "Introduce un ticker y pulsa "
            "«Ejecutar análisis completo»."
        )
    else:
        stored_requested_ticker = (
            _normalize_ticker(
                stored_result.get(
                    "requested_ticker"
                )
            )
        )
        stored_canonical_ticker = (
            _normalize_ticker(
                stored_result.get(
                    "canonical_ticker"
                )
            )
        )
        result_matches_input = (
            bool(
                requested_ticker
            )
            and requested_ticker
            in {
                stored_requested_ticker,
                stored_canonical_ticker,
            }
        )
        if not result_matches_input:
            stored_label = (
                stored_requested_ticker
                or stored_canonical_ticker
                or "otro ticker"
            )
            requested_label = (
                requested_ticker
                or "otro ticker"
            )
            st.info(
                "El último resultado guardado corresponde a "
                f"{stored_label}. Pulsa "
                "«Ejecutar análisis completo» para analizar "
                f"{requested_label}."
            )
        else:
            snapshot = deepcopy(
                stored_result[
                    "snapshot"
                ]
            )
            company_score = deepcopy(
                stored_result[
                    "score"
                ]
            )
            decision_response = deepcopy(
                stored_result[
                    "decision_response"
                ]
            )
            company_name = str(
                snapshot.get(
                    "name"
                )
                or stored_canonical_ticker
                or stored_requested_ticker
                or "Empresa"
            ).strip()
            company_ticker = (
                _normalize_ticker(
                    snapshot.get(
                        "ticker"
                    )
                )
                or stored_canonical_ticker
                or stored_requested_ticker
            )
            st.divider()
            (
                master_tab,
                radar_tab,
                data_tab,
            ) = st.tabs(
                [
                    "Decisión maestra",
                    "Radar preliminar",
                    "Datos y trazabilidad",
                ]
            )
            # -----------------------------------------------
            # DECISIÓN MAESTRA
            # -----------------------------------------------
            with master_tab:
                st.caption(
                    "Resultado de los controles maestros. "
                    "Una valoración no evaluada o datos "
                    "insuficientes impiden emitir una compra "
                    "automática."
                )
                debug_mode = st.checkbox(
                    "Mostrar información técnica",
                    value=False,
                    key=(
                        "individual_master_debug"
                    ),
                    help=(
                        "Muestra la respuesta estructurada "
                        "del servicio para auditoría y "
                        "depuración."
                    ),
                )
                try:
                    render_decision_response(
                        decision_response,
                        streamlit_module=st,
                        show_debug=debug_mode,
                    )
                except (
                    StreamlitDecisionRendererError
                ) as exc:
                    st.error(
                        "No se pudo representar la decisión "
                        f"maestra: {exc}"
                    )
                except Exception as exc:
                    st.error(
                        "Se produjo un error inesperado al "
                        "mostrar la decisión maestra: "
                        f"{exc}"
                    )
            # -----------------------------------------------
            # RADAR PRELIMINAR
            # -----------------------------------------------
            with radar_tab:
                st.subheader(
                    f"{company_name} · {company_ticker}"
                )
                st.warning(
                    "Este bloque es un cribado preliminar. "
                    "No sustituye la decisión maestra."
                )
                metric_columns = st.columns(
                    4
                )
                price = snapshot.get(
                    "price"
                )
                currency = str(
                    snapshot.get(
                        "currency"
                    )
                    or ""
                ).strip()
                price_display = (
                    _metric_display_value(
                        price
                    )
                )
                if (
                    price_display
                    != "n.d."
                    and currency
                ):
                    price_display = (
                        f"{price_display} {currency}"
                    )
                metric_columns[
                    0
                ].metric(
                    "Precio",
                    price_display,
                )
                metric_columns[
                    1
                ].metric(
                    "Score global",
                    _metric_display_value(
                        company_score.get(
                            "global_score"
                        )
                    ),
                )
                confidence = (
                    company_score.get(
                        "confidence"
                    )
                )
                confidence_suffix = (
                    "%"
                    if confidence is not None
                    else ""
                )
                metric_columns[
                    2
                ].metric(
                    "Confianza del radar",
                    _metric_display_value(
                        confidence,
                        suffix=(
                            confidence_suffix
                        ),
                    ),
                )
                metric_columns[
                    3
                ].metric(
                    "Clasificación del radar",
                    _metric_display_value(
                        company_score.get(
                            "recommendation"
                        )
                    ),
                    help=(
                        "Clasificación auxiliar de cribado. "
                        "No equivale a una orden de compra "
                        "ni a la decisión maestra."
                    ),
                )
                rationale = (
                    company_score.get(
                        "rationale"
                    )
                )
                if rationale:
                    st.write(
                        str(
                            rationale
                        )
                    )
                score_dimensions = {
                    "Valoración": (
                        company_score.get(
                            "valuation"
                        )
                    ),
                    "Calidad": (
                        company_score.get(
                            "quality"
                        )
                    ),
                    "Caja": (
                        company_score.get(
                            "cash"
                        )
                    ),
                    "Balance": (
                        company_score.get(
                            "balance"
                        )
                    ),
                    "Crecimiento": (
                        company_score.get(
                            "growth"
                        )
                    ),
                    "Capital allocation": (
                        company_score.get(
                            "capital_allocation"
                        )
                    ),
                    "Momentum fundamental": (
                        company_score.get(
                            "momentum_fundamental"
                        )
                    ),
                    "Riesgo": (
                        company_score.get(
                            "risk"
                        )
                    ),
                }
                score_df = pd.DataFrame(
                    {
                        "Dimensión": list(
                            score_dimensions.keys()
                        ),
                        "Score": list(
                            score_dimensions.values()
                        ),
                    }
                )
                score_df[
                    "Score"
                ] = pd.to_numeric(
                    score_df[
                        "Score"
                    ],
                    errors="coerce",
                )
                score_df = (
                    score_df.replace(
                        [
                            np.inf,
                            -np.inf,
                        ],
                        np.nan,
                    )
                    .dropna(
                        subset=[
                            "Score",
                        ]
                    )
                )
                score_df[
                    "Score"
                ] = score_df[
                    "Score"
                ].clip(
                    lower=0.0,
                    upper=100.0,
                )
                if score_df.empty:
                    st.info(
                        "No hay puntuaciones suficientes "
                        "para generar el gráfico."
                    )
                else:
                    score_figure = px.bar(
                        score_df,
                        x="Dimensión",
                        y="Score",
                        range_y=[
                            0,
                            100,
                        ],
                        title=(
                            "Puntuación preliminar "
                            "por dimensión"
                        ),
                    )
                    score_figure.update_layout(
                        showlegend=False,
                    )
                    st.plotly_chart(
                        score_figure,
                        use_container_width=True,
                    )
            # -----------------------------------------------
            # DATOS Y TRAZABILIDAD
            # -----------------------------------------------
            with data_tab:
                st.subheader(
                    "Datos utilizados en la precarga"
                )
                source_name = str(
                    snapshot.get(
                        "source"
                    )
                    or "No disponible"
                )
                fetched_at = str(
                    snapshot.get(
                        "fetched_at"
                    )
                    or "No disponible"
                )
                (
                    source_col,
                    date_col,
                ) = st.columns(
                    2
                )
                source_col.metric(
                    "Fuente de precarga",
                    source_name,
                )
                date_col.metric(
                    "Fecha de obtención",
                    fetched_at,
                )
                snapshot_warnings = (
                    snapshot.get(
                        "warnings"
                    )
                )
                if (
                    isinstance(
                        snapshot_warnings,
                        list,
                    )
                    and snapshot_warnings
                ):
                    st.warning(
                        "La precarga contiene advertencias."
                    )
                    for warning in snapshot_warnings:
                        st.write(
                            f"• {warning}"
                        )
                critical_missing_fields = (
                    snapshot.get(
                        "critical_missing_fields"
                    )
                )
                if (
                    isinstance(
                        critical_missing_fields,
                        list,
                    )
                    and critical_missing_fields
                ):
                    st.error(
                        "Faltan campos críticos en la precarga."
                    )
                    for field_name in (
                        critical_missing_fields
                    ):
                        st.write(
                            f"• {field_name}"
                        )
                st.dataframe(
                    pd.DataFrame(
                        [
                            snapshot,
                        ]
                    )
                    .T
                    .rename(
                        columns={
                            0: "Valor",
                        }
                    ),
                    use_container_width=True,
                )
                st.download_button(
                    label=(
                        "Descargar respuesta de la "
                        "decisión maestra"
                    ),
                    data=_decision_response_json(
                        decision_response
                    ),
                    file_name=(
                        f"{company_ticker}_"
                        "master_decision.json"
                    ),
                    mime="application/json",
                    use_container_width=True,
                )
# ============================================================
# VALORACIÓN DCF
# ============================================================
elif page == "Valoración DCF":
    st.header(
        "DCF configurable"
    )
    (
        c1,
        c2,
        c3,
    ) = st.columns(
        3
    )
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
    (
        c4,
        c5,
        c6,
    ) = st.columns(
        3
    )
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
            (
                result_col_1,
                result_col_2,
                result_col_3,
            ) = st.columns(
                3
            )
            result_col_1.metric(
                "Enterprise value",
                f"{result.enterprise_value:,.0f}",
            )
            result_col_2.metric(
                "Equity value",
                f"{result.equity_value:,.0f}",
            )
            value_per_share = (
                result.value_per_share
            )
            result_col_3.metric(
                "Valor por acción",
                (
                    f"{value_per_share:,.2f}"
                    if (
                        value_per_share
                        is not None
                    )
                    else "n.d."
                ),
            )
            projected_fcf_df = (
                pd.DataFrame(
                    {
                        "Año": range(
                            1,
                            len(
                                result.projected_fcfs
                            )
                            + 1,
                        ),
                        "FCF proyectado": (
                            result.projected_fcfs
                        ),
                    }
                ).set_index(
                    "Año"
                )
            )
            st.line_chart(
                projected_fcf_df,
            )
        except ValueError as exc:
            st.error(
                str(
                    exc
                )
            )
        except Exception as exc:
            st.error(
                "No se pudo completar la valoración: "
                f"{exc}"
            )
# ============================================================
# METODOLOGÍA
# ============================================================
else:
    st.header(
        "Metodología y datos"
    )
    st.markdown(
        """
### Dos niveles de análisis
1. El radar diario recorre el universo seleccionado mediante
   una precarga homogénea y un scoring provisional.
2. El análisis individual transforma esa precarga en una
   entrada estructurada para el motor de decisión maestro.
3. La decisión maestra aplica controles de calidad de datos,
   gates, valoración, moat y reglas de prudencia.
4. La valoración detallada debe completarse con fuentes
   oficiales antes de considerar una entrada.
### Principios metodológicos
- Separación entre calidad empresarial y precio.
- Separación entre radar preliminar y decisión maestra.
- Evaluación de la creación de valor por acción.
- Normalización del flujo de caja libre.
- Prudencia ante datos incompletos.
- Trazabilidad y versionado de resultados.
- Reducción automática de la confianza cuando faltan datos.
- Ausencia de recomendación automática cuando la valoración
  o los elementos esenciales no han sido evaluados.
- Revisión de cifras materiales en fuentes oficiales.
"""
    )
    st.code(
        "streamlit run app.py",
        language="bash",
    )
