"""Page 2: Overall Sync.

Displays gauges, alerts, and BSC radar chart.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px


def render():
    """Render the overall sync page."""
    st.markdown('<h1 class="main-header">📊 Overall Sync Dashboard</h1>', unsafe_allow_html=True)

    # Check if analysis has been run
    if st.session_state.kg is None:
        st.warning("⚠️ Please upload and analyze a strategic plan first (Upload Plans page).")
        return

    metrics = st.session_state.metrics
    completeness = st.session_state.completeness_results
    benchmarking = st.session_state.benchmarking_results

    # Calculate overall score
    overall_score = (
        metrics["sai"]
        + metrics["coverage"]
        + metrics["avg_priority"]
        + metrics["avg_kpi_utility"]
        + metrics["avg_catchball"]
        + (100 - metrics["egi"])
    ) / 6

    # Header metrics
    st.markdown("### Key Performance Indicators")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Overall Alignment",
            f"{overall_score:.1f}/100",
            delta=None,
            help="Average of all 6 composite metrics",
        )

    with col2:
        st.metric(
            "Strategic Alignment (SAI)",
            f"{metrics['sai']:.1f}/100",
            help="Average alignment score across all strategy-action pairs",
        )

    with col3:
        st.metric(
            "Coverage",
            f"{metrics['coverage']:.1f}%",
            help="Percentage of objectives with at least one supporting task",
        )

    with col4:
        gap_severity = completeness["gap_analysis"]["overall_severity"]
        severity_color = {
            "low": "🟢",
            "moderate": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }.get(gap_severity, "⚪")
        st.metric(
            "Gap Severity",
            f"{severity_color} {gap_severity.title()}",
            help="Overall execution gap severity",
        )

    st.markdown("---")

    # Gauges row
    st.markdown("### 📊 Composite Metrics Gauges")

    col1, col2, col3 = st.columns(3)

    with col1:
        fig_sai = create_gauge(
            metrics["sai"], "Strategic Alignment Index (SAI)", "SAI"
        )
        st.plotly_chart(fig_sai, width="stretch")
        st.caption("How strongly each action plan links to a strategic goal. Higher means tighter strategy-action fit.")

    with col2:
        fig_priority = create_gauge(
            metrics["avg_priority"], "Avg Weighted Priority", "Priority"
        )
        st.plotly_chart(fig_priority, width="stretch")
        st.caption("Whether high-importance goals receive proportionally more resources. Higher means better prioritization.")

    with col3:
        fig_kpi = create_gauge(
            metrics["avg_kpi_utility"], "Avg KPI Utility", "KPI Utility"
        )
        st.plotly_chart(fig_kpi, width="stretch")
        st.caption("How well-defined and measurable the KPIs are. Higher means clearer success criteria.")

    col4, col5, col6 = st.columns(3)

    with col4:
        fig_catchball = create_gauge(
            metrics["avg_catchball"], "Avg Catchball", "Catchball"
        )
        st.plotly_chart(fig_catchball, width="stretch")
        st.caption("How well goals cascade down through the organization. Higher means smoother top-to-bottom flow.")

    with col5:
        fig_coverage = create_gauge(metrics["coverage"], "Coverage %", "Coverage")
        st.plotly_chart(fig_coverage, width="stretch")
        st.caption("Percentage of strategic goals that have at least one supporting action plan. 100% means no orphan goals.")

    with col6:
        # EGI: Lower is better, so invert for display
        egi_inverted = 100 - metrics["egi"]
        fig_egi = create_gauge(
            egi_inverted, "Execution Gap (inverted)", "EGI", inverted=True
        )
        st.plotly_chart(fig_egi, width="stretch")
        st.caption("Mismatch between strategic importance and resource allocation. Higher (inverted) means fewer gaps.")

    # CLD gauge (if available)
    cld_data = metrics.get("cld")
    if cld_data:
        st.markdown("### BSC Strategy Map — Causal Linkage Density")

        col_cld1, col_cld2 = st.columns([1, 2])

        with col_cld1:
            cld_score_pct = cld_data["cld_score"] * 100
            fig_cld = create_gauge(
                cld_score_pct, "Causal Linkage Density", "CLD"
            )
            st.plotly_chart(fig_cld, width="stretch")

        with col_cld2:
            st.markdown("**Perspective Pair Densities:**")
            for pair, score in cld_data.get("perspective_pair_scores", {}).items():
                complete = cld_data.get("chain_completeness", {}).get(pair, False)
                icon = "✅" if complete else "❌"
                st.markdown(f"- {icon} {pair}: **{score:.2%}**")

            missing = cld_data.get("missing_chains", [])
            if missing:
                st.warning(f"Missing causal chains: {', '.join(missing)}")

    st.markdown("---")

    # Prioritization misalignment alerts
    misalignments = metrics.get("prioritization_misalignments", [])
    if misalignments:
        st.markdown("### Prioritization Misalignment Alerts")
        for m in misalignments:
            if m["type"] == "under-resourced":
                st.markdown(
                    f'<div class="danger-box">🔴 <strong>Under-Resourced:</strong> '
                    f'Objective <code>{m["objective_id"]}</code> has <strong>{m["importance"]}</strong> importance '
                    f'but only <strong>{m["allocation"]}</strong> resource allocation '
                    f'(Task Group: {m["task_group_id"]})</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="warning-box">🟠 <strong>Over-Resourced:</strong> '
                    f'Objective <code>{m["objective_id"]}</code> has <strong>{m["importance"]}</strong> importance '
                    f'but <strong>{m["allocation"]}</strong> resource allocation '
                    f'(Task Group: {m["task_group_id"]})</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("---")

    # BSC structural gaps
    bsc_gaps = metrics.get("bsc_structural_gaps", [])
    if bsc_gaps:
        st.markdown("### BSC Structural Gaps")
        for gap in bsc_gaps:
            st.markdown(
                f'<div class="warning-box">⚠️ {gap}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("---")

    # BSC Radar Chart
    st.markdown("### 🎯 Balanced Scorecard Coverage")

    bsc_coverage = completeness["bsc_analysis"]["coverage"]
    fig_bsc = create_bsc_radar(bsc_coverage)
    st.plotly_chart(fig_bsc, width="stretch")

    # Alerts section
    st.markdown("---")
    st.markdown("### ⚠️ Alerts & Recommendations")

    alerts = generate_alerts(metrics, completeness, benchmarking)

    if not alerts:
        st.success("✅ No critical alerts. Your strategic plan is well-aligned!")
    else:
        for alert in alerts:
            if alert["severity"] == "critical":
                st.markdown(
                    f'<div class="danger-box">🔴 <strong>Critical:</strong> {alert["message"]}</div>',
                    unsafe_allow_html=True,
                )
            elif alert["severity"] == "high":
                st.markdown(
                    f'<div class="warning-box">🟠 <strong>High:</strong> {alert["message"]}</div>',
                    unsafe_allow_html=True,
                )
            elif alert["severity"] == "medium":
                st.markdown(
                    f'<div class="warning-box">🟡 <strong>Medium:</strong> {alert["message"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="success-box">🟢 <strong>Info:</strong> {alert["message"]}</div>',
                    unsafe_allow_html=True,
                )

    # Metric details table
    st.markdown("---")
    st.markdown("### 📋 Detailed Metrics")

    import pandas as pd

    metrics_df = pd.DataFrame(
        {
            "Metric": [
                "Strategic Alignment Index (SAI)",
                "Coverage",
                "Avg Weighted Priority",
                "Avg KPI Utility",
                "Avg Catchball Consistency",
                "Execution Gap Index (EGI)",
            ],
            "Score": [
                f"{metrics['sai']:.2f}/100",
                f"{metrics['coverage']:.2f}%",
                f"{metrics['avg_priority']:.2f}/100",
                f"{metrics['avg_kpi_utility']:.2f}/100",
                f"{metrics['avg_catchball']:.2f}/100",
                f"{metrics['egi']:.2f}/100",
            ],
            "Status": [
                get_status(metrics["sai"]),
                get_status(metrics["coverage"]),
                get_status(metrics["avg_priority"]),
                get_status(metrics["avg_kpi_utility"]),
                get_status(metrics["avg_catchball"]),
                get_status(100 - metrics["egi"]),  # Inverted
            ],
        }
    )

    st.dataframe(metrics_df, width="stretch", hide_index=True)


def create_gauge(value, title, short_title, inverted=False):
    """Create a gauge chart for a metric."""
    # Determine color based on value
    if inverted:
        # For EGI, lower original value (higher inverted) is better
        if value >= 80:
            color = "green"
        elif value >= 60:
            color = "yellow"
        elif value >= 40:
            color = "orange"
        else:
            color = "red"
    else:
        if value >= 80:
            color = "green"
        elif value >= 60:
            color = "yellow"
        elif value >= 40:
            color = "orange"
        else:
            color = "red"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": short_title, "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 40], "color": "lightgray"},
                    {"range": [40, 60], "color": "gray"},
                    {"range": [60, 80], "color": "lightblue"},
                    {"range": [80, 100], "color": "lightgreen"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 4},
                    "thickness": 0.75,
                    "value": value,
                },
            },
        )
    )

    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


def create_bsc_radar(bsc_coverage):
    """Create a radar chart for BSC perspective coverage."""
    categories = ["Financial", "Customer", "Internal Process", "Learning & Growth"]
    values = [
        bsc_coverage.get("Financial", 0),
        bsc_coverage.get("Customer", 0),
        bsc_coverage.get("Internal Process", 0),
        bsc_coverage.get("Learning & Growth", 0),
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name="Goals per Perspective",
            line_color="rgb(31, 119, 180)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(values) + 1 if values else 1],
            )
        ),
        showlegend=False,
        height=400,
        title="BSC Perspective Distribution",
    )

    return fig


def generate_alerts(metrics, completeness, benchmarking):
    """Generate alerts based on analysis results."""
    alerts = []

    # Check orphan objectives
    orphan_objectives = completeness.get("orphan_objectives", [])
    if len(orphan_objectives) > 0:
        alerts.append(
            {
                "severity": "critical" if len(orphan_objectives) > 2 else "high",
                "message": f"{len(orphan_objectives)} objective(s) have no supporting tasks: {', '.join(orphan_objectives[:3])}{'...' if len(orphan_objectives) > 3 else ''}",
            }
        )

    # Check orphan tasks
    orphan_tasks = completeness.get("orphan_tasks", [])
    if len(orphan_tasks) > 0:
        alerts.append(
            {
                "severity": "medium",
                "message": f"{len(orphan_tasks)} task group(s) have no strategic alignment and may need justification or removal",
            }
        )

    # Check BSC balance
    bsc = completeness.get("bsc_analysis", {})
    missing = bsc.get("missing_perspectives", [])
    if missing:
        alerts.append(
            {
                "severity": "high",
                "message": f"Missing BSC perspectives: {', '.join(missing)}. Consider adding goals for balanced strategy.",
            }
        )

    # Check gap severity
    gap_severity = completeness.get("gap_analysis", {}).get("overall_severity", "low")
    if gap_severity in ["critical", "high"]:
        alerts.append(
            {
                "severity": gap_severity,
                "message": f"Execution gap severity is {gap_severity}. Resource allocation doesn't match strategic importance.",
            }
        )

    # Check SAI
    if metrics["sai"] < 50:
        alerts.append(
            {
                "severity": "critical",
                "message": f"Low Strategic Alignment Index ({metrics['sai']:.1f}/100). Many tasks don't align well with strategic goals.",
            }
        )

    # Check coverage
    if metrics["coverage"] < 80:
        alerts.append(
            {
                "severity": "high" if metrics["coverage"] < 60 else "medium",
                "message": f"Coverage is {metrics['coverage']:.1f}%. {100 - metrics['coverage']:.0f}% of goals lack supporting tasks.",
            }
        )

    # Alignment assessment issues
    assessment = benchmarking.get("alignment_assessment", {})
    weak_dimensions = [
        k
        for k, v in assessment.items()
        if isinstance(v, dict) and v.get("verdict") in ("weak", "critical")
    ]
    if weak_dimensions:
        labels = [k.replace("_", " ").title() for k in weak_dimensions]
        alerts.append(
            {
                "severity": "high" if any(
                    assessment[k].get("verdict") == "critical" for k in weak_dimensions
                ) else "medium",
                "message": f"Alignment dimensions need attention: {', '.join(labels)}",
            }
        )

    # CLD alerts
    cld_data = metrics.get("cld")
    if cld_data and cld_data.get("cld_score", 1.0) < 0.3:
        missing_chains = cld_data.get("missing_chains", [])
        alerts.append(
            {
                "severity": "high",
                "message": f"Low Causal Linkage Density ({cld_data['cld_score']:.2f}). "
                + (f"Missing chains: {', '.join(missing_chains)}." if missing_chains else "BSC causal links are weak."),
            }
        )

    # Prioritization misalignment alerts
    misalignments = metrics.get("prioritization_misalignments", [])
    under = [m for m in misalignments if m["type"] == "under-resourced"]
    if under:
        alerts.append(
            {
                "severity": "critical" if len(under) >= 2 else "high",
                "message": f"{len(under)} objective(s) are under-resourced (high importance + low allocation).",
            }
        )

    return sorted(alerts, key=lambda x: ["critical", "high", "medium", "low"].index(x["severity"]))


def get_status(value):
    """Get status emoji based on value."""
    if value >= 80:
        return "✅ Excellent"
    elif value >= 60:
        return "👍 Good"
    elif value >= 40:
        return "⚠️ Fair"
    else:
        return "❌ Poor"
