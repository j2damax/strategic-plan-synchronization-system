"""Page: LLM Debug View.

Inspect all LLM prompts, responses, parse results, and aggregate statistics.
"""

import json

import streamlit as st

from core.llm_logger import clear_llm_logs, get_llm_logs, get_llm_stats


def render():
    """Render the LLM debug page."""
    st.header("LLM Debug View")

    logs = get_llm_logs()
    stats = get_llm_stats()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{len(logs)}** LLM call(s) recorded this session")
    with col2:
        if st.button("Clear logs"):
            clear_llm_logs()
            st.rerun()

    if not logs:
        st.info("No LLM calls recorded yet. Upload plans and run extraction to see calls here.")
        return

    # Aggregate Statistics section
    st.markdown("---")
    st.markdown("### Aggregate Statistics")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Calls", stats["total_calls"])
    with col2:
        st.metric("Cached", stats["cached_calls"])
    with col3:
        st.metric("Total Tokens", f"{stats['total_tokens']:,}")
    with col4:
        st.metric("Est. Cost", f"${stats['estimated_cost_usd']:.4f}")
    with col5:
        st.metric("Avg Latency", f"{stats['avg_latency_ms']:.0f}ms")

    # Per-layer breakdown
    per_layer = stats.get("per_layer", {})
    if per_layer:
        st.markdown("#### Per-Layer Breakdown")

        import pandas as pd

        layer_rows = []
        for layer_num in sorted(per_layer.keys()):
            layer_data = per_layer[layer_num]
            layer_rows.append({
                "Layer": f"Layer {layer_num}",
                "Calls": layer_data["calls"],
                "Input Tokens": layer_data["input_tokens"],
                "Output Tokens": layer_data["output_tokens"],
                "Latency (ms)": layer_data["latency_ms"],
                "Errors": layer_data["errors"],
            })

        layer_df = pd.DataFrame(layer_rows)
        st.dataframe(layer_df, width="stretch", hide_index=True)

    # Per-model breakdown
    per_model = stats.get("per_model", {})
    if per_model:
        st.markdown("#### Per-Model Breakdown")

        import pandas as pd

        model_rows = []
        for model_name, model_data in per_model.items():
            model_rows.append({
                "Model": model_name,
                "Calls": model_data["calls"],
                "Input Tokens": model_data["input_tokens"],
                "Output Tokens": model_data["output_tokens"],
            })

        model_df = pd.DataFrame(model_rows)
        st.dataframe(model_df, width="stretch", hide_index=True)

    # Token distribution chart
    if stats["total_tokens"] > 0:
        st.markdown("#### Token Distribution")

        import plotly.graph_objects as go

        fig = go.Figure(data=[
            go.Bar(
                name="Input Tokens",
                x=["Input", "Output"],
                y=[stats["total_input_tokens"], stats["total_output_tokens"]],
                marker_color=["#1f77b4", "#ff7f0e"],
            )
        ])
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, width="stretch")

    # Call log
    st.markdown("---")
    st.markdown("### Call Log")

    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        layer_filter = st.selectbox(
            "Filter by Layer",
            options=["All"] + sorted(set(
                str(log.get("layer", "N/A")) for log in logs if log.get("layer") is not None
            )),
        )
    with filter_col2:
        show_cached = st.checkbox("Show cached calls", value=True)

    filtered_logs = logs
    if layer_filter != "All":
        filtered_logs = [log for log in filtered_logs if str(log.get("layer")) == layer_filter]
    if not show_cached:
        filtered_logs = [log for log in filtered_logs if not log.get("cached")]

    st.markdown(f"Showing **{len(filtered_logs)}** of {len(logs)} calls")

    for i, entry in enumerate(filtered_logs):
        # Build label with metadata
        parts = [f"#{i+1}", entry['caller']]

        if entry.get("layer") is not None:
            parts.append(f"L{entry['layer']}")
        if entry.get("model"):
            parts.append(entry["model"])
        if entry.get("input_tokens") is not None:
            total_tok = (entry.get("input_tokens") or 0) + (entry.get("output_tokens") or 0)
            parts.append(f"{total_tok} tok")
        if entry.get("latency_ms") is not None:
            parts.append(f"{entry['latency_ms']}ms")
        if entry.get("cached"):
            parts.append("CACHED")

        parts.append(entry['timestamp'])

        if entry.get("error"):
            parts.append("ERROR")

        label = " | ".join(parts)

        with st.expander(label, expanded=False):
            # Metadata row
            meta_cols = st.columns(6)
            with meta_cols[0]:
                st.markdown(f"**Caller:** `{entry['caller']}`")
            with meta_cols[1]:
                st.markdown(f"**Layer:** {entry.get('layer', 'N/A')}")
            with meta_cols[2]:
                st.markdown(f"**Model:** {entry.get('model', 'N/A')}")
            with meta_cols[3]:
                st.markdown(f"**Tokens:** {entry.get('input_tokens', '?')}/{entry.get('output_tokens', '?')}")
            with meta_cols[4]:
                st.markdown(f"**Latency:** {entry.get('latency_ms', 'N/A')}ms")
            with meta_cols[5]:
                st.markdown(f"**Cached:** {'Yes' if entry.get('cached') else 'No'}")

            st.markdown("**Prompt:**")
            st.code(entry["prompt"], language="text")

            if entry.get("response") is not None:
                st.markdown("**Response:**")
                st.code(entry["response"], language="json")

            if entry.get("parsed_result") is not None:
                st.markdown("**Parsed Result:**")
                try:
                    st.json(entry["parsed_result"])
                except Exception:
                    st.code(str(entry["parsed_result"]), language="text")

            if entry.get("error"):
                st.error(f"**Parse Error:** {entry['error']}")
