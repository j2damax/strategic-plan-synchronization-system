"""BITA Dashboard - Main Application.

Streamlit dashboard for Business-IT Alignment analysis.
"""

import sys
from pathlib import Path

# Add parent directory to Python path to import core modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import streamlit as st

# Configure page
st.set_page_config(
    page_title="BITA - Business-IT Alignment System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
    <style>
    /* Hide Streamlit's auto-generated page list in sidebar */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 1rem;
        letter-spacing: -0.02em;
    }
    .metric-card {
        background-color: #F8FAFC;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #E2E8F0;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #F0FDF4;
        border-left: 4px solid #16A34A;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 0.375rem 0.375rem 0;
    }
    .warning-box {
        background-color: #FFFBEB;
        border-left: 4px solid #D97706;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 0.375rem 0.375rem 0;
    }
    .danger-box {
        background-color: #FEF3C7;
        border-left: 4px solid #B45309;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 0.375rem 0.375rem 0;
    }
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC;
    }
    /* Radio button labels */
    [data-testid="stSidebar"] .stRadio > label {
        color: #334155;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

from core import LLM_PROVIDERS, DEFAULT_PROVIDER

# Initialize session state
if "kg" not in st.session_state:
    st.session_state.kg = None
if "metrics" not in st.session_state:
    st.session_state.metrics = None
if "completeness_results" not in st.session_state:
    st.session_state.completeness_results = None
if "benchmarking_results" not in st.session_state:
    st.session_state.benchmarking_results = None
if "strategic_objectives" not in st.session_state:
    st.session_state.strategic_objectives = []
if "task_groups" not in st.session_state:
    st.session_state.task_groups = []
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = None

# Sidebar navigation
st.sidebar.markdown("## 🎯 BITA System")
st.sidebar.markdown("Business-IT Alignment Analysis")
st.sidebar.markdown("---")

# LLM Configuration
st.sidebar.markdown("### LLM Configuration")

provider_names = list(LLM_PROVIDERS.keys())
default_idx = provider_names.index(DEFAULT_PROVIDER)
llm_provider = st.sidebar.selectbox(
    "Provider",
    provider_names,
    index=default_idx,
    key="llm_provider",
)

provider_config = LLM_PROVIDERS[llm_provider]
llm_model = st.sidebar.selectbox(
    "Model",
    provider_config["models"],
    index=0,
    key="llm_model",
)

llm_api_key = st.sidebar.text_input(
    provider_config["key_label"],
    type="password",
    placeholder=provider_config["key_placeholder"],
    key="llm_api_key",
    help="Your API key is not stored and only used for this session.",
)

st.sidebar.markdown("---")

# User-facing pages
pages = [
    "📤 Upload Plans",
    "📊 Overall Sync",
    "🔄 Strategy Matrix",
    "⚠️ Gap Analysis",
    "🕸️ Knowledge Graph",
]

# Developer pages toggle
show_dev = st.sidebar.checkbox("Show Developer Pages", value=False)
if show_dev:
    pages.append("🐛 LLM Debug")

page = st.sidebar.radio("Navigation", pages)

# Import pages
from pages import (
    page_upload,
    page_overall_sync,
    page_strategy_matrix,
    page_gap_analysis,
    page_knowledge_graph,
    page_llm_debug,
)

# Route to selected page
if page == "📤 Upload Plans":
    page_upload.render()
elif page == "📊 Overall Sync":
    page_overall_sync.render()
elif page == "🔄 Strategy Matrix":
    page_strategy_matrix.render()
elif page == "⚠️ Gap Analysis":
    page_gap_analysis.render()
elif page == "🕸️ Knowledge Graph":
    page_knowledge_graph.render()
elif page == "🐛 LLM Debug":
    page_llm_debug.render()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**BITA v0.1.0**")
st.sidebar.markdown(f"Powered by {llm_model} & RDFLib")
