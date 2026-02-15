"""Page 4: Gap Analysis & Recommendations.

Displays coverage gaps, BSC balance, resource alignment, alignment assessment,
and deep entity-specific recommendations.
"""

import pandas as pd
import streamlit as st


def render():
    """Render the gap analysis page."""
    st.markdown(
        '<h1 class="main-header">⚠️ Gap Analysis & Recommendations</h1>',
        unsafe_allow_html=True,
    )

    if st.session_state.kg is None:
        st.warning(
            "⚠️ Please upload and analyze a strategic plan first (Upload Plans page)."
        )
        return

    kg = st.session_state.kg
    completeness = st.session_state.completeness_results
    benchmarking = st.session_state.benchmarking_results

    # Tabs for different gap types
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🔍 Coverage Gaps",
            "⚖️ BSC Balance",
            "📉 Resource Alignment",
            "🎯 Alignment Assessment",
            "💡 Recommendations",
        ]
    )

    with tab1:
        render_coverage_gaps(kg, completeness, benchmarking)

    with tab2:
        render_bsc_balance(completeness, st.session_state.metrics)

    with tab3:
        render_resource_alignment(kg, completeness, benchmarking)

    with tab4:
        render_alignment_assessment(benchmarking)

    with tab5:
        render_recommendations(benchmarking, kg=kg)


def _get_recommendations_for_entity(benchmarking, entity_id):
    """Get recommendations that affect a specific entity."""
    recommendations = benchmarking.get("recommendations", [])
    return [
        r for r in recommendations
        if entity_id in r.get("affected_entities", [])
    ]


def _render_inline_recommendation(rec):
    """Render a compact recommendation inline within another section."""
    priority_emoji = {
        "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢",
    }.get(rec.get("priority", "medium"), "⚪")

    st.markdown(f"**{priority_emoji} Recommendation:** {rec.get('title', 'N/A')}")
    if rec.get("recommended_actions"):
        for i, action in enumerate(rec["recommended_actions"], 1):
            st.markdown(f"  {i}. {action}")


def render_coverage_gaps(kg, completeness, benchmarking):
    """Render orphan objectives and tasks with entity-specific context and recommendations."""
    st.markdown("### 🔍 Coverage Gaps")
    st.markdown(
        "Orphan objectives have no supporting action plans. "
        "Orphan task groups have no strategic justification."
    )

    orphan_objectives = completeness.get("orphan_objectives", [])
    orphan_tasks = completeness.get("orphan_tasks", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Orphan Objectives")
        if not orphan_objectives:
            st.success("✅ All objectives have supporting tasks!")
        else:
            st.error(f"❌ Found {len(orphan_objectives)} orphan objective(s)")

            for obj_id in orphan_objectives:
                props = kg.get_entity_properties(obj_id)
                # Find parent goal for context
                parent_query = f"""
                PREFIX bita: <http://bita-system.org/ontology#>
                SELECT ?g WHERE {{ ?g bita:hasObjective bita:{obj_id} . }}
                """
                parent_rows = kg.query_sparql(parent_query)
                parent_id = str(parent_rows[0]["g"]).split("#")[-1] if parent_rows else None
                parent_props = kg.get_entity_properties(parent_id) if parent_id else {}

                obj_label = props.get('label', obj_id)
                with st.expander(f"**{obj_label}** ({obj_id})"):
                    st.markdown(f"**Objective:** {obj_label}")
                    if parent_id:
                        st.markdown(f"**Parent Goal:** {parent_props.get('label', parent_id)} ({parent_id})")
                        st.markdown(f"**BSC Perspective:** {parent_props.get('bscPerspective', 'N/A')}")
                    importance = props.get("strategicImportance", parent_props.get("strategicImportance", "N/A"))
                    st.markdown(f"**Importance:** {importance}")

                    # Show matching recommendations
                    recs = _get_recommendations_for_entity(benchmarking, obj_id)
                    if recs:
                        st.markdown("---")
                        for rec in recs:
                            _render_inline_recommendation(rec)
                    else:
                        st.warning(
                            "⚠️ This objective needs action plans to ensure execution."
                        )

    with col2:
        st.markdown("#### Orphan Task Groups")
        if not orphan_tasks:
            st.success("✅ All task groups are strategically aligned!")
        else:
            st.warning(f"⚠️ Found {len(orphan_tasks)} orphan task group(s)")

            for tg_id in orphan_tasks:
                props = kg.get_entity_properties(tg_id)
                tg_label = props.get('label', tg_id)
                with st.expander(f"**{tg_label}** ({tg_id})"):
                    st.markdown(
                        f"**Intended Purpose:** {props.get('intendedPurpose', 'N/A')}"
                    )
                    st.markdown(
                        f"**Resources:** {props.get('resourceAllocation', 'N/A')}"
                    )

                    # Show matching recommendations
                    recs = _get_recommendations_for_entity(benchmarking, tg_id)
                    if recs:
                        st.markdown("---")
                        for rec in recs:
                            _render_inline_recommendation(rec)
                    else:
                        st.info(
                            "ℹ️ This task group should be linked to a strategic goal or removed if not strategically relevant."
                        )


def render_bsc_balance(completeness, metrics=None):
    """Render BSC balance analysis."""
    st.markdown("### ⚖️ Balanced Scorecard Coverage")
    st.markdown(
        """
        A balanced strategic plan should have goals across all four BSC perspectives:
        Financial, Customer, Internal Process, and Learning & Growth.
        """
    )

    bsc = completeness.get("bsc_analysis", {})
    coverage = bsc.get("coverage", {})
    missing = bsc.get("missing_perspectives", [])
    balanced = bsc.get("balanced", False)

    # Summary
    if balanced:
        st.success("✅ Strategic plan is balanced across all BSC perspectives!")
    else:
        st.error(f"❌ Missing perspectives: {', '.join(missing)}")

    # Coverage table
    st.markdown("#### Coverage by Perspective")

    df = pd.DataFrame(
        {
            "Perspective": ["Financial", "Customer", "Internal Process", "Learning & Growth"],
            "Objectives": [
                coverage.get("Financial", 0),
                coverage.get("Customer", 0),
                coverage.get("Internal Process", 0),
                coverage.get("Learning & Growth", 0),
            ],
            "Status": [
                "✅ Covered" if coverage.get(p, 0) > 0 else "❌ Missing"
                for p in ["Financial", "Customer", "Internal Process", "Learning & Growth"]
            ],
        }
    )

    st.dataframe(df, width="stretch", hide_index=True)

    # BSC Causal Chain Links
    causal_links = completeness.get("causal_links", [])
    if causal_links:
        st.markdown("---")
        st.markdown("#### BSC Causal Chain Links")
        st.markdown(
            "Identified cause-and-effect relationships between objectives in adjacent BSC perspectives "
            "(Learning & Growth → Internal Process → Customer → Financial)."
        )

        strength_colors = {
            "strong": "🟢",
            "moderate": "🟡",
            "weak": "🟠",
        }

        for link in causal_links:
            icon = strength_colors.get(link["strength"], "⚪")
            with st.expander(
                f"{icon} {link['source_name']} ({link['source_perspective']}) → "
                f"{link['target_name']} ({link['target_perspective']}) — {link['strength']}"
            ):
                st.markdown(f"**Source:** {link['source_name']} ({link['source_id']}) — {link['source_perspective']}")
                st.markdown(f"**Target:** {link['target_name']} ({link['target_id']}) — {link['target_perspective']}")
                st.markdown(f"**Strength:** {link['strength']}")
                st.markdown(f"**Reasoning:** {link['reasoning']}")

    # BSC Structural Gaps
    if metrics:
        bsc_gaps = metrics.get("bsc_structural_gaps", [])
        if bsc_gaps:
            st.markdown("---")
            st.markdown("#### BSC Structural Gaps")
            for gap in bsc_gaps:
                st.warning(gap)

    # Recommendations
    if missing:
        st.markdown("---")
        st.markdown("#### 💡 Recommendations")
        for perspective in missing:
            st.warning(
                f"Add strategic goals for **{perspective}** perspective to ensure balanced strategy"
            )


def render_resource_alignment(kg, completeness, benchmarking):
    """Render execution gap analysis with entity names and recommendations."""
    st.markdown("### 📉 Resource Alignment")
    st.markdown(
        "Resource alignment gaps occur when resource allocation doesn't match strategic importance. "
        "High-importance goals should have heavy resource allocation."
    )

    gap_analysis = completeness.get("gap_analysis", {})
    overall_severity = gap_analysis.get("overall_severity", "low")
    gaps = gap_analysis.get("gaps", [])
    total_gaps = gap_analysis.get("total_gaps", 0)

    # Summary
    severity_color = {
        "low": "🟢",
        "moderate": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }.get(overall_severity, "⚪")

    st.markdown(f"### {severity_color} Overall Severity: {overall_severity.title()}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Gaps", total_gaps)

    with col2:
        critical_gaps = len([g for g in gaps if g["severity"] == "critical"])
        st.metric("Critical Gaps", critical_gaps)

    with col3:
        high_gaps = len([g for g in gaps if g["severity"] == "high"])
        st.metric("High Priority Gaps", high_gaps)

    # Gap details
    if not gaps:
        st.success("✅ No significant resource alignment gaps detected!")
    else:
        st.markdown("#### Gap Details")

        # Severity filter
        severity_filter = st.multiselect(
            "Filter by Severity",
            options=["critical", "high", "moderate", "low"],
            default=["critical", "high", "moderate"],
            key="resource_severity_filter",
        )

        filtered_gaps = [g for g in gaps if g["severity"] in severity_filter]

        if not filtered_gaps:
            st.info("No gaps match the selected severity levels.")
        else:
            # Add entity names to the table
            rows = []
            for g in filtered_gaps:
                obj_props = kg.get_entity_properties(g["objective_id"])
                tg_props = kg.get_entity_properties(g["task_group_id"])
                goal_id = g.get("goal_id", "")
                goal_props = kg.get_entity_properties(goal_id) if goal_id else {}
                goal_label = goal_props.get("label", goal_id or "N/A")
                rows.append({
                    "Objective": f"{obj_props.get('label', g['objective_id'])} ({g['objective_id']})",
                    "Goal": f"{goal_label} ({goal_id})" if goal_id else goal_label,
                    "Task Group": f"{tg_props.get('label', g['task_group_id'])} ({g['task_group_id']})",
                    "Importance": g["importance"],
                    "Allocation": g["allocation"],
                    "Gap Score": g["gap_score"],
                    "Severity": g["severity"],
                })

            display_df = pd.DataFrame(rows).sort_values("Gap Score", ascending=False)

            st.dataframe(
                display_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Gap Score": st.column_config.ProgressColumn(
                        "Gap Score",
                        help="Difference between importance and allocation",
                        format="%d",
                        min_value=0,
                        max_value=100,
                    ),
                },
            )

        # Show resource-related recommendations below the table
        resource_recs = [
            r for r in benchmarking.get("recommendations", [])
            if r.get("category") == "resource_gap"
        ]
        if resource_recs:
            st.markdown("---")
            st.markdown("#### 💡 Resource Reallocation Recommendations")
            for rec in resource_recs:
                _render_recommendation_card(rec, kg=kg)


def render_alignment_assessment(benchmarking):
    """Render strategy-to-action alignment assessment results."""
    st.markdown("### 🎯 Strategy-to-Action Alignment Assessment")

    assessment = benchmarking.get("alignment_assessment", {})

    if not assessment:
        st.warning("No alignment assessment available.")
    else:
        from core.benchmarking import ALIGNMENT_DIMENSIONS

        # Summary counts
        strong_count = sum(
            1 for v in assessment.values()
            if isinstance(v, dict) and v.get("verdict") == "strong"
        )
        adequate_count = sum(
            1 for v in assessment.values()
            if isinstance(v, dict) and v.get("verdict") == "adequate"
        )
        needs_attention = sum(
            1 for v in assessment.values()
            if isinstance(v, dict) and v.get("verdict") in ("weak", "critical")
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Strong", strong_count)
        with col2:
            st.metric("Adequate", adequate_count)
        with col3:
            st.metric("Needs Attention", needs_attention)

        # Detailed results
        st.markdown("##### Dimension Assessment")

        verdict_emoji = {
            "strong": "\U0001f7e2",
            "adequate": "\U0001f7e1",
            "weak": "\U0001f7e0",
            "critical": "\U0001f534",
        }

        for key, label in ALIGNMENT_DIMENSIONS.items():
            if key in assessment:
                result = assessment[key]
                verdict = result.get("verdict", "unknown")
                reasoning = result.get("reasoning", "N/A")
                examples = result.get("examples", [])
                emoji = verdict_emoji.get(verdict, "\u26aa")

                with st.expander(f"{emoji} {label}"):
                    st.markdown(f"**Verdict**: {verdict.title()}")
                    st.markdown(f"**Assessment**: {reasoning}")
                    if examples:
                        st.markdown("**Evidence from your plan:**")
                        for example in examples:
                            st.markdown(f"- {example}")


def _resolve_entity_label(kg, entity_id):
    """Resolve an entity ID to 'Label (ID)' format. Returns ID if no label found."""
    if kg is None:
        return entity_id
    props = kg.get_entity_properties(entity_id)
    label = props.get("label", "")
    if label:
        return f"{label} ({entity_id})"
    return entity_id


def _render_recommendation_card(rec, kg=None):
    """Render a single recommendation as a rich card."""
    priority = rec.get("priority", "medium")
    priority_emoji = {
        "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢",
    }.get(priority, "⚪")
    category_label = rec.get("category", "general").replace("_", " ").title()

    with st.expander(f"{priority_emoji} **{rec.get('title', 'Recommendation')}**  —  `{category_label}` | {priority.title()} Priority"):
        # Gap description
        st.markdown(f"**Gap:** {rec.get('gap_description', 'N/A')}")

        # Business impact as callout
        impact = rec.get("business_impact", "")
        if impact:
            st.info(f"**Business Impact:** {impact}")

        # Priority reasoning
        if rec.get("priority_reasoning"):
            st.caption(f"Priority reasoning: {rec['priority_reasoning']}")

        # Action steps
        actions = rec.get("recommended_actions", [])
        if actions:
            st.markdown("**Recommended Actions:**")
            for i, action in enumerate(actions, 1):
                st.markdown(f"  {i}. {action}")

        # Affected entities as tags — resolve to readable names
        entities = rec.get("affected_entities", [])
        if entities:
            tags = "  ".join(f"`{_resolve_entity_label(kg, e)}`" for e in entities)
            st.markdown(f"**Affected Entities:** {tags}")


def render_recommendations(benchmarking, kg=None):
    """Render improvement recommendations with rich cards."""
    st.markdown("### 💡 Recommendations")
    st.markdown(
        "AI-generated recommendations to improve strategic plan alignment and completeness. "
        "Each recommendation references specific entities and provides actionable steps."
    )

    recommendations = benchmarking.get("recommendations", [])

    if not recommendations:
        st.success("✅ No critical improvement recommendations at this time!")
        return

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        category_options = sorted({r.get("category", "general") for r in recommendations})
        category_labels = [c.replace("_", " ").title() for c in category_options]
        category_filter = st.multiselect(
            "Filter by Category",
            options=category_options,
            format_func=lambda c: c.replace("_", " ").title(),
            default=category_options,
            key="rec_category_filter",
        )

    with col2:
        priority_filter = st.multiselect(
            "Filter by Priority",
            options=["critical", "high", "medium", "low"],
            default=["critical", "high", "medium"],
            key="rec_priority_filter",
        )

    filtered = [
        r for r in recommendations
        if r.get("priority", "medium") in priority_filter
        and r.get("category", "general") in category_filter
    ]

    # Sort by priority (critical first)
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    filtered.sort(key=lambda r: priority_order.get(r.get("priority", "medium"), 99))

    if not filtered:
        st.info("No recommendations match the selected filters.")
        return

    st.markdown(f"Showing **{len(filtered)}** of {len(recommendations)} recommendations")

    for rec in filtered:
        _render_recommendation_card(rec, kg=kg)
