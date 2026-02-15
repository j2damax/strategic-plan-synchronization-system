"""Page 3: Strategy Matrix.

Displays alignment heatmap, X-Matrix visualization, and detailed alignment table.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.metrics import RELEVANCE_MAP


def render():
    """Render the strategy matrix page."""
    st.markdown(
        '<h1 class="main-header">🔄 Strategy Matrix</h1>', unsafe_allow_html=True
    )

    if st.session_state.kg is None:
        st.warning(
            "⚠️ Please upload and analyze a strategic plan first (Upload Plans page)."
        )
        return

    kg = st.session_state.kg
    goals = st.session_state.strategic_goals
    task_groups = st.session_state.task_groups

    # Extract alignment data
    alignment_data = extract_alignment_data(kg, goals, task_groups)

    metrics = st.session_state.metrics

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔥 Alignment Heatmap", "📊 Detailed Table", "🎯 Priority Matrix", "📈 KIPGA Matrix"]
    )

    with tab1:
        render_heatmap(alignment_data, goals, task_groups)

    with tab2:
        render_alignment_table(alignment_data)

    with tab3:
        render_priority_matrix(kg, goals, task_groups)

    with tab4:
        render_kipga_matrix(metrics)


def _lookup_parent_goal(kg, obj_id):
    """Look up parent goal for an objective. Returns (goal_id, goal_name)."""
    parent_query = f"""
    PREFIX bita: <http://bita-system.org/ontology#>
    SELECT ?goal WHERE {{ ?goal bita:hasObjective bita:{obj_id} . }}
    """
    rows = kg.query_sparql(parent_query)
    if rows:
        goal_id = str(rows[0]["goal"]).split("#")[-1]
        goal_props = kg.get_entity_properties(goal_id)
        return goal_id, goal_props.get("label", goal_id)
    return "", ""


def extract_alignment_data(kg, goals, task_groups):
    """Extract alignment data from Knowledge Graph at objective level."""
    alignment_data = []

    # Get all task groups
    tg_query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?tg WHERE {
        ?tg rdf:type bita:TaskGroup .
    }
    """
    tg_results = kg.query_sparql(tg_query)

    for tg_row in tg_results:
        tg_uri = str(tg_row["tg"])
        tg_id = tg_uri.split("#")[-1]
        tg_props = kg.get_entity_properties(tg_id)

        # Find all alignment properties
        for prop_name, prop_value in tg_props.items():
            if "_relevance" in prop_name and "alignment_" in prop_name:
                # Extract objective ID from property name
                obj_id = prop_name.split("alignment_")[1].split("_relevance")[0]

                relevance = prop_value
                strength_key = f"alignment_{obj_id}_strength"
                reasoning_key = f"alignment_{obj_id}_reasoning"

                strength = tg_props.get(strength_key, "N/A")
                reasoning = tg_props.get(reasoning_key, "N/A")

                # Get objective and task group names
                obj_props = kg.get_entity_properties(obj_id)
                obj_name = obj_props.get("label", obj_id)
                tg_name = tg_props.get("label", tg_props.get("groupName", tg_id))

                # Look up parent goal
                goal_id, goal_name = _lookup_parent_goal(kg, obj_id)

                alignment_data.append(
                    {
                        "obj_id": obj_id,
                        "obj_name": obj_name,
                        "goal_id": goal_id,
                        "goal_name": goal_name,
                        "task_group_id": tg_id,
                        "task_group_name": tg_name,
                        "relevance": relevance,
                        "contribution_strength": strength,
                        "reasoning": reasoning,
                        "score": RELEVANCE_MAP.get(relevance, 0),
                    }
                )

    return alignment_data


def render_heatmap(alignment_data, goals, task_groups):
    """Render alignment heatmap."""
    st.markdown("### Alignment Heatmap")
    st.markdown(
        "Color intensity shows alignment strength (direct=100, partial=60, indirect=30, none=0)"
    )

    if not alignment_data:
        st.warning("No alignment data available.")
        return

    # Create pivot table
    df = pd.DataFrame(alignment_data)

    # Get unique objectives and task groups
    obj_ids = sorted(df["obj_id"].unique())
    tg_ids = sorted(df["task_group_id"].unique())

    # Create matrix
    matrix = []
    for tg_id in tg_ids:
        row = []
        for obj_id in obj_ids:
            match = df[
                (df["obj_id"] == obj_id) & (df["task_group_id"] == tg_id)
            ]
            if not match.empty:
                row.append(match.iloc[0]["score"])
            else:
                row.append(0)
        matrix.append(row)

    # Get display names
    obj_names = []
    obj_goal_names = []
    for obj_id in obj_ids:
        match = df[df["obj_id"] == obj_id]
        if not match.empty:
            obj_names.append(match.iloc[0]["obj_name"])
            obj_goal_names.append(match.iloc[0]["goal_name"])
        else:
            obj_names.append(obj_id)
            obj_goal_names.append("")

    tg_names = []
    for tg_id in tg_ids:
        match = df[df["task_group_id"] == tg_id]
        if not match.empty:
            tg_names.append(match.iloc[0]["task_group_name"])
        else:
            tg_names.append(tg_id)

    # Build customdata for tooltip: [obj_name, goal_name, tg_name] per cell
    customdata = []
    for i, tg_name in enumerate(tg_names):
        row_custom = []
        for j, obj_name in enumerate(obj_names):
            row_custom.append([obj_name, obj_goal_names[j], tg_name])
        customdata.append(row_custom)

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=obj_names,
            y=tg_names,
            customdata=customdata,
            colorscale="RdYlGn",
            colorbar=dict(title="Score"),
            text=matrix,
            texttemplate="%{text}",
            textfont={"size": 12},
            hovertemplate=(
                "<b>Objective:</b> %{customdata[0]}<br>"
                "<b>Goal:</b> %{customdata[1]}<br>"
                "<b>Action:</b> %{customdata[2]}<br>"
                "<b>Score:</b> %{z}"
                "<extra></extra>"
            ),
        )
    )

    cell_height = 50
    fig.update_layout(
        title=dict(text="Strategic Objectives ↔ Task Groups Alignment", font=dict(size=14)),
        xaxis_title="Strategic Objectives",
        yaxis_title="Task Groups",
        height=max(450, len(tg_ids) * cell_height + 150),
        xaxis=dict(
            side="bottom",
            tickangle=-45,
            tickfont=dict(size=11),
            automargin=True,
        ),
        yaxis=dict(
            tickfont=dict(size=11),
            automargin=True,
        ),
        margin=dict(b=120),
    )

    st.plotly_chart(fig, width="stretch")

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        strong_alignments = len(df[df["relevance"] == "direct"])
        st.metric("Direct Alignments", strong_alignments)

    with col2:
        partial_alignments = len(df[df["relevance"] == "partial"])
        st.metric("Partial Alignments", partial_alignments)

    with col3:
        weak_alignments = len(df[df["relevance"] == "indirect"])
        st.metric("Indirect Alignments", weak_alignments)

    with col4:
        avg_score = df["score"].mean()
        st.metric("Avg Alignment Score", f"{avg_score:.1f}/100")


def render_alignment_table(alignment_data):
    """Render detailed alignment table."""
    st.markdown("### Detailed Alignment Table")

    if not alignment_data:
        st.warning("No alignment data available.")
        return

    df = pd.DataFrame(alignment_data)

    # Add filters
    col1, col2 = st.columns(2)

    with col1:
        relevance_filter = st.multiselect(
            "Filter by Relevance",
            options=["direct", "partial", "indirect", "none"],
            default=["direct", "partial", "indirect"],
        )

    with col2:
        min_score = st.slider("Minimum Alignment Score", 0, 100, 0)

    # Apply filters
    filtered_df = df[
        (df["relevance"].isin(relevance_filter)) & (df["score"] >= min_score)
    ]

    # Sort by score descending
    filtered_df = filtered_df.sort_values("score", ascending=False)

    # Display table
    display_df = filtered_df[
        [
            "obj_name",
            "goal_name",
            "task_group_name",
            "relevance",
            "contribution_strength",
            "score",
        ]
    ].copy()

    display_df.columns = [
        "Objective",
        "Goal",
        "Task Group",
        "Relevance",
        "Strength",
        "Score",
    ]

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score",
                help="Alignment score (0-100)",
                format="%d",
                min_value=0,
                max_value=100,
            ),
        },
    )

    # Expandable reasoning
    st.markdown("### View Alignment Reasoning")

    selected_idx = st.selectbox(
        "Select an alignment to view reasoning",
        options=range(len(filtered_df)),
        format_func=lambda i: f"{filtered_df.iloc[i]['obj_name']} ↔ {filtered_df.iloc[i]['task_group_name']} ({filtered_df.iloc[i]['relevance']})",
    )

    if selected_idx is not None:
        selected = filtered_df.iloc[selected_idx]
        st.markdown(f"**Objective**: {selected['obj_name']}")
        st.markdown(f"**Goal**: {selected['goal_name']}")
        st.markdown(f"**Task Group**: {selected['task_group_name']}")
        st.markdown(f"**Relevance**: {selected['relevance']}")
        st.markdown(f"**Strength**: {selected['contribution_strength']}")
        st.markdown(f"**Reasoning**: {selected['reasoning']}")


def render_priority_matrix(kg, goals, task_groups):
    """Render priority matrix (importance vs allocation) at objective level."""
    st.markdown("### Are Resources Matching Priorities?")
    st.markdown(
        "Each dot is a strategic objective paired with an action plan. "
        "Ideally every dot sits on or near the diagonal line — that means "
        "the resources you're investing match how important the objective is. "
        "Dots far from the line signal a mismatch."
    )

    # Extract data for priority matrix
    priority_data = []

    alignment_query = """
    PREFIX bita: <http://bita-system.org/ontology#>

    SELECT ?tg ?obj WHERE {
        ?tg bita:supportsObjective ?obj .
    }
    """
    results = kg.query_sparql(alignment_query)

    importance_map = {
        "critical": 100,
        "high": 75,
        "moderate": 50,
        "low": 25,
        "negligible": 0,
    }
    allocation_map = {"heavy": 100, "moderate": 70, "light": 40, "minimal": 10}

    importance_display = {
        "critical": "Critical",
        "high": "High",
        "moderate": "Moderate",
        "low": "Low",
        "negligible": "Negligible",
    }
    allocation_display = {
        "heavy": "Heavy",
        "moderate": "Moderate",
        "light": "Light",
        "minimal": "Minimal",
    }

    for row in results:
        obj_id = str(row["obj"]).split("#")[-1]
        tg_id = str(row["tg"]).split("#")[-1]

        obj_props = kg.get_entity_properties(obj_id)
        tg_props = kg.get_entity_properties(tg_id)

        # Look up parent goal for strategicImportance
        goal_id, goal_name = _lookup_parent_goal(kg, obj_id)
        if goal_id:
            goal_props = kg.get_entity_properties(goal_id)
            importance = goal_props.get("strategicImportance", "moderate")
        else:
            importance = "moderate"
            goal_name = ""

        allocation = tg_props.get("resourceAllocation", "moderate")

        importance_score = importance_map.get(importance, 50)
        allocation_score = allocation_map.get(allocation, 70)

        obj_name = obj_props.get("label", obj_id)
        tg_name = tg_props.get("label", tg_props.get("groupName", tg_id))

        priority_data.append(
            {
                "obj_name": obj_name,
                "goal_name": goal_name,
                "action_name": tg_name,
                "importance": importance_score,
                "allocation": allocation_score,
                "importance_label": importance_display.get(importance, importance),
                "allocation_label": allocation_display.get(allocation, allocation),
            }
        )

    if not priority_data:
        st.warning("No alignment data for priority matrix.")
        return

    df = pd.DataFrame(priority_data)

    # Classify each dot for color
    def classify(row):
        gap = row["importance"] - row["allocation"]
        if gap > 20:
            return "Needs more resources"
        elif gap < -20:
            return "May have excess resources"
        else:
            return "Well-matched"

    df["status"] = df.apply(classify, axis=1)

    color_map = {
        "Needs more resources": "#dc3545",
        "Well-matched": "#28a745",
        "May have excess resources": "#ffc107",
    }

    # Create scatter plot
    fig = px.scatter(
        df,
        x="importance",
        y="allocation",
        color="status",
        color_discrete_map=color_map,
        custom_data=["obj_name", "goal_name", "action_name", "importance_label", "allocation_label"],
        labels={
            "importance": "How Important Is the Objective?",
            "allocation": "How Much Resource Is Assigned?",
            "status": "Status",
        },
    )

    fig.update_traces(
        marker=dict(size=14, line=dict(width=1, color="white")),
        hovertemplate=(
            "<b>Objective:</b> %{customdata[0]}<br>"
            "<b>Goal:</b> %{customdata[1]}<br>"
            "<b>Action:</b> %{customdata[2]}<br>"
            "<b>Importance:</b> %{customdata[3]}<br>"
            "<b>Resources:</b> %{customdata[4]}"
            "<extra></extra>"
        ),
    )

    # Diagonal line — perfect balance
    fig.add_shape(
        type="line",
        x0=0, y0=0, x1=100, y1=100,
        line=dict(color="gray", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=90, y=95,
        text="Perfect balance",
        showarrow=False,
        font=dict(size=10, color="gray"),
    )

    # Quadrant labels
    fig.add_annotation(
        x=85, y=20,
        text="Needs more resources",
        showarrow=False,
        font=dict(size=11, color="#dc3545"),
    )
    fig.add_annotation(
        x=15, y=85,
        text="May have excess resources",
        showarrow=False,
        font=dict(size=11, color="#cc9a00"),
    )
    fig.add_annotation(
        x=85, y=85,
        text="Well-resourced,<br>high priority",
        showarrow=False,
        font=dict(size=11, color="#28a745"),
    )
    fig.add_annotation(
        x=15, y=20,
        text="Low priority,<br>low investment",
        showarrow=False,
        font=dict(size=11, color="gray"),
    )

    # Categorical tick labels on axes
    fig.update_layout(
        height=600,
        title=dict(text="Resource-Priority Balance", font=dict(size=14)),
        xaxis=dict(
            tickvals=[0, 25, 50, 75, 100],
            ticktext=["Negligible", "Low", "Moderate", "High", "Critical"],
            range=[-5, 110],
        ),
        yaxis=dict(
            tickvals=[10, 40, 70, 100],
            ticktext=["Minimal", "Light", "Moderate", "Heavy"],
            range=[-5, 110],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(fig, width="stretch")

    # Show mismatches
    mismatched = df[df["status"] != "Well-matched"].copy()

    if mismatched.empty:
        st.success("All objective-action pairs have well-matched resources!")
    else:
        st.markdown("### Mismatched Pairs")
        st.caption("These objective-action pairs have a significant gap between how important the objective is and how many resources are assigned to the action.")

        display = mismatched[
            ["obj_name", "goal_name", "action_name", "importance_label", "allocation_label", "status"]
        ].copy()
        display.columns = [
            "Objective",
            "Goal",
            "Action Plan",
            "Importance",
            "Resources",
            "Status",
        ]
        display = display.sort_values("Status")

        st.dataframe(display, width="stretch", hide_index=True)


def render_kipga_matrix(metrics):
    """Render importance vs performance matrix for strategic objectives."""
    st.markdown("### Which Objectives Need More Attention?")
    st.markdown(
        "Each dot is a strategic objective. The vertical axis shows how important it is "
        "(inherited from its parent goal), and the horizontal axis shows how well your "
        "action plans are delivering on it. "
        "Objectives in the top-left corner are the ones to worry about — they matter a lot "
        "but aren't being executed well."
    )

    kipga = metrics.get("kipga")
    if not kipga or not kipga.get("plot_data"):
        st.info("No data available. Run the full analysis pipeline first.")
        return

    plot_data = kipga["plot_data"]
    quadrants = kipga["quadrants"]

    df = pd.DataFrame(plot_data)

    # User-friendly status labels
    status_map = {
        "concentrate_here": "Needs attention",
        "keep_up": "On track",
        "low_priority": "Low priority",
        "possible_overkill": "May be over-invested",
    }

    color_map = {
        "Needs attention": "#dc3545",
        "On track": "#28a745",
        "Low priority": "#6c757d",
        "May be over-invested": "#ffc107",
    }

    df["status"] = df["quadrant"].map(status_map)

    # Percentage display for readability
    df["importance_pct"] = (df["importance"] * 100).round(0).astype(int)
    df["performance_pct"] = (df["performance"] * 100).round(0).astype(int)

    fig = px.scatter(
        df,
        x="performance",
        y="importance",
        color="status",
        color_discrete_map=color_map,
        custom_data=["name", "goal_name", "status", "importance_pct", "performance_pct"],
    )

    fig.update_traces(
        marker=dict(size=14, line=dict(width=1, color="white")),
        hovertemplate=(
            "<b>Objective:</b> %{customdata[0]}<br>"
            "<b>Goal:</b> %{customdata[1]}<br>"
            "Importance: %{customdata[3]}%<br>"
            "Execution: %{customdata[4]}%<br>"
            "Status: %{customdata[2]}"
            "<extra></extra>"
        ),
    )

    # Quadrant dividers
    fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=0.5, line_dash="dash", line_color="gray", opacity=0.5)

    # Quadrant labels — plain language
    fig.add_annotation(x=0.25, y=0.9, text="Needs attention",
                       showarrow=False, font=dict(size=11, color="#dc3545"))
    fig.add_annotation(x=0.75, y=0.9, text="On track",
                       showarrow=False, font=dict(size=11, color="#28a745"))
    fig.add_annotation(x=0.25, y=0.1, text="Low priority",
                       showarrow=False, font=dict(size=11, color="#6c757d"))
    fig.add_annotation(x=0.75, y=0.1, text="May be over-invested",
                       showarrow=False, font=dict(size=11, color="#cc9a00"))

    fig.update_layout(
        height=600,
        title=dict(text="Objective Importance vs Execution Quality", font=dict(size=14)),
        xaxis=dict(
            title="How well is it being executed?",
            range=[-0.05, 1.05],
            tickvals=[0, 0.25, 0.5, 0.75, 1.0],
            ticktext=["Not at all", "Poorly", "Partially", "Well", "Fully"],
        ),
        yaxis=dict(
            title="How important is this objective?",
            range=[-0.05, 1.05],
            tickvals=[0, 0.25, 0.5, 0.75, 1.0],
            ticktext=["Negligible", "Low", "Moderate", "High", "Critical"],
        ),
        legend=dict(
            title="",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(fig, width="stretch")

    # Summary counts with descriptions
    st.markdown("### Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        count = len(quadrants.get("concentrate_here", []))
        st.metric("Needs attention", count)
        st.caption("Important objectives with weak execution")
    with col2:
        count = len(quadrants.get("keep_up", []))
        st.metric("On track", count)
        st.caption("Important objectives being executed well")
    with col3:
        count = len(quadrants.get("low_priority", []))
        st.metric("Low priority", count)
        st.caption("Less important, less effort — acceptable")
    with col4:
        count = len(quadrants.get("possible_overkill", []))
        st.metric("May be over-invested", count)
        st.caption("Low importance but high effort")

    # Detail table
    if plot_data:
        st.markdown("### All Objectives")
        detail_df = df[["name", "goal_name", "importance_pct", "performance_pct", "status"]].copy()
        detail_df.columns = ["Objective", "Goal", "Importance %", "Execution %", "Status"]
        detail_df = detail_df.sort_values("Importance %", ascending=False)
        st.dataframe(detail_df, width="stretch", hide_index=True)
