"""Page 1: Upload Plans.

Upload PDF strategic plan and run analysis pipeline.
"""

import tempfile
from pathlib import Path

import streamlit as st

from core import (
    AlignmentScorer,
    BenchmarkingAgent,
    CompletenessAnalyzer,
    DocumentIngestion,
    KnowledgeGraph,
    PipelineState,
    StructuredExtractor,
    setup_cache,
)
from core.metrics import compute_all_metrics
import pandas as pd

# Enable LLM caching globally
setup_cache()


def render():
    """Render the upload page with wizard flow."""
    # Initialize wizard step
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1

    st.markdown('<h1 class="main-header">📤 Upload Strategic & Action Plans</h1>', unsafe_allow_html=True)

    # Wizard flow based on current step
    if st.session_state.wizard_step == 1:
        render_step1_upload()
    elif st.session_state.wizard_step == 2:
        render_step2_review()
    elif st.session_state.wizard_step == 3:
        render_step3_analysis()
    elif st.session_state.wizard_step == 4:
        render_step4_completed()


def render_step1_upload():
    """Step 1: Upload files and extract Layer 1."""

    st.markdown(
        """
        Upload your strategic and action plan PDFs. The system will:
        1. **Extract** strategic goals and task groups (Layer 1)
        2. **Review** extracted data (you confirm before proceeding)
        3. **Score** alignment between strategy and actions (Layer 2)
        4. **Analyze** completeness and gaps (Layer 3)
        5. **Assess** strategy-to-action alignment (Layer 4)
        """
    )

    # Read LLM config from sidebar
    api_key = st.session_state.get("llm_api_key", "")
    llm_provider = st.session_state.get("llm_provider", "Anthropic")
    llm_model = st.session_state.get("llm_model", "claude-sonnet-4-5-20250929")

    if not api_key:
        st.warning("⚠️ Please enter your API key in the sidebar to proceed.")
        return

    # Upload files
    st.markdown("### Upload Files")

    # Strategic plan upload
    strategic_file = st.file_uploader(
        "📄 Strategic Plan PDF",
        type=["pdf"],
        key="strategic_pdf",
        help="Upload your strategic plan PDF",
    )

    # Action plan uploads
    action_files = st.file_uploader(
        "📋 Action Plan PDF(s)",
        type=["pdf"],
        accept_multiple_files=True,
        key="action_pdfs",
        help="Upload one or more action plan PDFs",
    )

    if not strategic_file:
        st.info("👆 Upload a strategic plan PDF to begin.")
        return

    if not action_files:
        st.info("👆 Upload at least one action plan PDF to continue.")
        return

    # Display uploaded files
    st.markdown("#### 📁 Uploaded Files:")
    st.write(f"✅ Strategic Plan: **{strategic_file.name}**")
    for i, action_file in enumerate(action_files, 1):
        st.write(f"✅ Action Plan {i}: **{action_file.name}**")

    # Run analysis button
    if st.button("🚀 Run Layer 1 Extraction", type="primary", width="stretch"):
        # Store uploaded data in session state
        st.session_state.uploaded_strategic_file = strategic_file
        st.session_state.uploaded_action_files = action_files
        st.session_state.uploaded_api_key = api_key
        st.session_state.uploaded_llm_provider = llm_provider
        st.session_state.uploaded_llm_model = llm_model
        # Run Layer 1 extraction
        run_layer1_extraction(strategic_file, action_files, api_key)


def run_layer1_extraction(strategic_file, action_files, api_key):
    """Run Layer 1 extraction only."""

    # Save uploaded files temporarily
    tmp_files = []

    try:
        # Save strategic PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix="_strategic.pdf") as tmp_file:
            tmp_file.write(strategic_file.read())
            strategic_path = tmp_file.name
            tmp_files.append(strategic_path)

        # Save action PDFs
        action_paths = []
        for i, action_file in enumerate(action_files):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_action_{i}.pdf") as tmp_file:
                tmp_file.write(action_file.read())
                action_path = tmp_file.name
                action_paths.append(action_path)
                tmp_files.append(action_path)

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Layer 1: Extraction
        status_text.markdown("### 🔄 Layer 1: Extracting Structured Data...")
        progress_bar.progress(10)

        with st.spinner("Parsing PDFs..."):
            strategic_text, action_text = DocumentIngestion.extract_from_separate_pdfs(
                strategic_pdf=strategic_path,
                action_pdfs=action_paths,
            )

        st.success(
            f"✓ Extracted {len(strategic_text)} characters (strategic) + {len(action_text)} characters (actions)"
        )
        progress_bar.progress(20)

        llm_provider = st.session_state.get("uploaded_llm_provider", "Anthropic")
        llm_model = st.session_state.get("uploaded_llm_model")

        with st.spinner(f"Extracting strategic goals with {llm_model}..."):
            extractor = StructuredExtractor(api_key=api_key, model=llm_model, provider=llm_provider)
            strategic_goals = extractor.extract_strategic_plan(strategic_text)

        st.success(f"✓ Extracted {len(strategic_goals)} strategic goals")
        progress_bar.progress(35)

        with st.spinner(f"Extracting action plan task groups with {llm_model}..."):
            task_groups = extractor.extract_action_plan(action_text)

        st.success(f"✓ Extracted {len(task_groups)} task groups")
        progress_bar.progress(50)

        # Store extracted data in session state
        st.session_state.extracted_strategic_goals = strategic_goals
        st.session_state.extracted_task_groups = task_groups

        # Move to step 2 (review)
        status_text.markdown("### ✅ Layer 1 Complete!")
        st.session_state.wizard_step = 2
        st.rerun()

    except Exception as e:
        st.error(f"❌ Error during analysis: {str(e)}")
        st.exception(e)

    finally:
        # Clean up temporary files
        for tmp_file in tmp_files:
            Path(tmp_file).unlink(missing_ok=True)


def render_step2_review():
    """Step 2: Review extracted data."""

    st.markdown("## 📋 Review Extracted Data")
    st.markdown("Please review the extracted information below. Click **Confirm & Continue** to proceed with alignment analysis (Layers 2-4).")

    # Retrieve extracted data from session state
    strategic_goals = st.session_state.extracted_strategic_goals
    task_groups = st.session_state.extracted_task_groups

    # Display Strategic Goals
    st.markdown("### 🎯 Strategic Goals")
    if strategic_goals:
        for i, goal in enumerate(strategic_goals, 1):
            with st.expander(f"**Goal {i}:** {goal.get('goal_name', 'N/A')}", expanded=(i == 1)):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {goal.get('goal_id', 'N/A')}")
                    st.write(f"**Importance:** {goal.get('strategic_importance', 'N/A')}")
                    st.write(f"**BSC Perspective:** {goal.get('bsc_perspective', 'N/A')}")
                    st.write(f"**Timeline:** {goal.get('timeline', 'N/A')}")
                with col2:
                    st.write(f"**Description:** {goal.get('description', 'N/A')}")
                    if goal.get('objectives'):
                        st.write(f"**Objectives ({len(goal['objectives'])}):**")
                        for objective in goal['objectives'][:3]:  # Show first 3
                            st.write(f"  • {objective}")
                    if goal.get('kpis'):
                        st.write(f"**KPIs ({len(goal['kpis'])}):** {', '.join([k.get('name', 'N/A') for k in goal['kpis'][:3]])}")
    else:
        st.warning("No strategic goals extracted.")

    # Display Task Groups
    st.markdown("### 📋 Task Groups")
    if task_groups:
        for i, tg in enumerate(task_groups, 1):
            with st.expander(f"**Task Group {i}:** {tg.get('task_group_name', 'N/A')}", expanded=(i == 1)):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {tg.get('task_group_id', 'N/A')}")
                    st.write(f"**Phase:** {tg.get('phase', 'N/A')}")
                    st.write(f"**Resource Allocation:** {tg.get('resource_allocation', 'N/A')}")
                with col2:
                    st.write(f"**Intended Purpose:** {tg.get('intended_strategic_purpose', 'N/A')}")
                    if tg.get('tasks'):
                        st.write(f"**Tasks ({len(tg['tasks'])}):**")
                        for task in tg['tasks']:
                            st.write(f"  • {task.get('name', 'N/A')}")
    else:
        st.warning("No task groups extracted.")

    # Summary statistics
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Strategic Goals", len(strategic_goals))
    with col2:
        st.metric("Task Groups", len(task_groups))
    with col3:
        total_tasks = sum(len(tg.get('tasks', [])) for tg in task_groups)
        st.metric("Total Tasks", total_tasks)

    # Confirmation buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col2:
        if st.button("❌ Cancel & Start Over", width="stretch"):
            # Reset to step 1
            st.session_state.wizard_step = 1
            st.rerun()

    with col3:
        if st.button("✅ Confirm & Continue", type="primary", width="stretch"):
            # Move to step 3 (run Layers 2-4)
            st.session_state.wizard_step = 3
            st.rerun()


def render_step3_analysis():
    """Step 3: Run Layers 2-4 analysis."""

    st.markdown("## 🔄 Running Analysis (Layers 2-4)")

    # Retrieve data from session state
    strategic_goals = st.session_state.extracted_strategic_goals
    task_groups = st.session_state.extracted_task_groups
    api_key = st.session_state.uploaded_api_key
    llm_provider = st.session_state.get("uploaded_llm_provider", "Anthropic")
    llm_model = st.session_state.get("uploaded_llm_model")

    # Progress tracking
    progress_bar = st.progress(50)
    status_text = st.empty()

    try:
        # Build Knowledge Graph
        status_text.markdown("### 🔄 Building Knowledge Graph...")
        with st.spinner("Populating Knowledge Graph..."):
            kg = KnowledgeGraph()
            pipeline_state = PipelineState()

            # Capture initial KG state (before Layer 1 writes)
            pipeline_state.capture_snapshot(kg, layer=0, label="Initial (BSC static data)")

            extractor = StructuredExtractor(api_key=api_key, model=llm_model, provider=llm_provider)
            extractor.write_to_knowledge_graph(
                kg=kg,
                strategic_goals=strategic_goals,
                task_groups=task_groups,
            )

        # Capture post-Layer 1 snapshot and run SHACL
        pipeline_state.capture_snapshot(kg, layer=1, label="After Layer 1: Structured Extraction")
        pipeline_state.run_shacl_validation(kg, layer=1)

        st.success(f"✓ Knowledge Graph created with {len(kg.graph)} triples")
        progress_bar.progress(55)

        # Continue with Layers 2-4
        run_layers_2_to_4(kg, strategic_goals, task_groups, api_key, progress_bar, status_text, pipeline_state, llm_provider, llm_model)

    except Exception as e:
        st.error(f"❌ Error during analysis: {str(e)}")
        st.exception(e)
        if st.button("🔄 Start Over", type="secondary"):
            st.session_state.wizard_step = 1
            st.rerun()


def run_layers_2_to_4(kg, strategic_goals, task_groups, api_key, progress_bar, status_text, pipeline_state, llm_provider="Anthropic", llm_model=None):
    """Run Layers 2-4 after user confirmation."""

    try:
        # Layer 2: Alignment
        status_text.markdown("### 🔄 Layer 2: Scoring Alignment...")
        with st.spinner(
            f"Evaluating {len(strategic_goals) * len(task_groups)} alignment pairs with {llm_model}..."
        ):
            alignment_scorer = AlignmentScorer(api_key=api_key, model=llm_model, provider=llm_provider)
            alignment_scorer.score_all_alignments(kg)

        pipeline_state.capture_snapshot(kg, layer=2, label="After Layer 2: Alignment Scoring")
        pipeline_state.run_shacl_validation(kg, layer=2)

        st.success("✓ Alignment scoring complete")
        progress_bar.progress(70)

        # Layer 3: Completeness
        status_text.markdown("### 🔄 Layer 3: Analyzing Completeness...")
        with st.spinner("Detecting gaps, analyzing cascades, and building causal links..."):
            completeness_analyzer = CompletenessAnalyzer(api_key=api_key, model=llm_model, provider=llm_provider)
            completeness_results = completeness_analyzer.analyze_completeness(kg)

        pipeline_state.capture_snapshot(kg, layer=3, label="After Layer 3: Completeness & Gap Analysis")
        pipeline_state.run_shacl_validation(kg, layer=3)

        st.success(
            f"✓ Completeness analysis complete ({len(completeness_results['orphan_objectives'])} orphan objectives, "
            f"{len(completeness_results['orphan_tasks'])} orphan tasks, "
            f"{len(completeness_results.get('causal_links', []))} causal links)"
        )
        progress_bar.progress(85)

        # Layer 4: Benchmarking
        status_text.markdown("### 🔄 Layer 4: Benchmarking & Recommendations...")
        with st.spinner("Assessing alignment and generating recommendations..."):
            benchmarking_agent = BenchmarkingAgent(api_key=api_key, model=llm_model, provider=llm_provider)
            benchmarking_results = benchmarking_agent.run_benchmarking(
                kg, completeness_results
            )

        pipeline_state.capture_snapshot(kg, layer=4, label="After Layer 4: Benchmarking & Suggestions")
        pipeline_state.run_shacl_validation(kg, layer=4)

        st.success(
            f"✓ Benchmarking complete ({len(benchmarking_results.get('recommendations', []))} recommendations)"
        )
        progress_bar.progress(95)

        # Compute metrics
        status_text.markdown("### 🔄 Computing Final Metrics...")
        with st.spinner("Calculating composite scores..."):
            metrics = compute_all_metrics(kg)

        progress_bar.progress(100)
        status_text.markdown("### ✅ Analysis Complete!")

        # Store in session state
        st.session_state.kg = kg
        st.session_state.metrics = metrics
        st.session_state.completeness_results = completeness_results
        st.session_state.benchmarking_results = benchmarking_results
        st.session_state.strategic_goals = strategic_goals
        st.session_state.task_groups = task_groups
        st.session_state.pipeline_state = pipeline_state

        # Move to completed step
        st.session_state.wizard_step = 4
        st.rerun()

    except Exception as e:
        st.error(f"❌ Error during analysis: {str(e)}")
        st.exception(e)


def render_step4_completed():
    """Step 4: Show results summary and extracted data for review."""

    metrics = st.session_state.metrics
    strategic_goals = st.session_state.strategic_goals
    task_groups = st.session_state.task_groups
    benchmarking_results = st.session_state.benchmarking_results

    st.markdown("## ✅ Analysis Complete")

    # Quick summary
    st.markdown("### 📊 Quick Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Strategic Goals", len(strategic_goals))
        st.metric("Task Groups", len(task_groups))

    with col2:
        st.metric("Strategic Alignment Index", f"{metrics['sai']:.1f}/100")
        st.metric("Coverage", f"{metrics['coverage']:.1f}%")

    with col3:
        st.metric("Execution Gap Index", f"{metrics['egi']:.1f}/100")
        st.metric(
            "Recommendations", len(benchmarking_results.get("recommendations", []))
        )

    # Overall score
    overall_score = (
        metrics["sai"]
        + metrics["coverage"]
        + metrics["avg_priority"]
        + metrics["avg_kpi_utility"]
        + metrics["avg_catchball"]
        + (100 - metrics["egi"])
    ) / 6

    st.markdown(f"### Overall Alignment Score: {overall_score:.1f}/100")

    if overall_score >= 80:
        st.success("Excellent alignment!")
    elif overall_score >= 60:
        st.info("Good alignment with room for improvement")
    elif overall_score >= 40:
        st.warning("Moderate alignment, significant gaps identified")
    else:
        st.error("Poor alignment, major improvements needed")

    st.info(
        "Use the sidebar to navigate to other pages and explore detailed analysis."
    )

    # --- Extracted data review ---
    st.markdown("---")
    st.markdown("### 📋 Extracted Data (Layer 1)")

    with st.expander("**Strategic Goals**", expanded=False):
        if strategic_goals:
            for i, goal in enumerate(strategic_goals, 1):
                st.markdown(f"#### Goal {i}: {goal.get('goal_name', 'N/A')}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {goal.get('goal_id', 'N/A')}")
                    st.write(f"**Importance:** {goal.get('strategic_importance', 'N/A')}")
                    st.write(f"**BSC Perspective:** {goal.get('bsc_perspective', 'N/A')}")
                    st.write(f"**Timeline:** {goal.get('timeline', 'N/A')}")
                with col2:
                    st.write(f"**Description:** {goal.get('description', 'N/A')}")
                    if goal.get('objectives'):
                        st.write(f"**Objectives ({len(goal['objectives'])}):**")
                        for objective in goal['objectives']:
                            st.write(f"  - {objective}")
                    if goal.get('kpis'):
                        st.write(f"**KPIs ({len(goal['kpis'])}):**")
                        for kpi in goal['kpis']:
                            st.write(f"  - {kpi.get('name', 'N/A')}")
                if i < len(strategic_goals):
                    st.markdown("---")
        else:
            st.warning("No strategic goals extracted.")

    with st.expander("**Task Groups**", expanded=False):
        if task_groups:
            for i, tg in enumerate(task_groups, 1):
                st.markdown(f"#### Task Group {i}: {tg.get('task_group_name', 'N/A')}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {tg.get('task_group_id', 'N/A')}")
                    st.write(f"**Phase:** {tg.get('phase', 'N/A')}")
                    st.write(f"**Resource Allocation:** {tg.get('resource_allocation', 'N/A')}")
                with col2:
                    st.write(f"**Intended Purpose:** {tg.get('intended_strategic_purpose', 'N/A')}")
                    if tg.get('tasks'):
                        st.write(f"**Tasks ({len(tg['tasks'])}):**")
                        for task in tg['tasks']:
                            st.write(f"  - {task.get('name', 'N/A')}")
                if i < len(task_groups):
                    st.markdown("---")
        else:
            st.warning("No task groups extracted.")

    # Start over button
    st.markdown("---")
    if st.button("🔄 Analyze Another Plan", type="secondary", width="stretch"):
        st.session_state.wizard_step = 1
        st.rerun()
