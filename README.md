# BITA — Business-IT Alignment Intelligent System

**Complete AI-powered system for analyzing strategic plan alignment using GPT-4o, RDFLib, and Streamlit.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30+-red.svg)](https://streamlit.io)
[![OpenAI GPT-4o](https://img.shields.io/badge/OpenAI-GPT--4o-green.svg)](https://openai.com)

---

## Overview

BITA analyzes strategic plans and action plans to measure alignment, detect gaps, and generate improvement suggestions. It uses a **4-layer pipeline** with categorical LLM outputs and programmatic scoring.

### Key Features

✅ **PDF Ingestion** - Extract strategic and action plan sections
✅ **Structured Extraction** - GPT-4o extracts objectives and tasks with categorical labels
✅ **Alignment Scoring** - LLM-as-Judge evaluates strategy-action alignment
✅ **Completeness Analysis** - SPARQL-based orphan detection + LLM gap analysis
✅ **Benchmarking** - COBIT 2019 and ISO 38500 validation
✅ **Agent-Driven Suggestions** - ReAct agent with tools generates recommendations
✅ **Interactive Dashboard** - 5-page Streamlit UI with visualizations
✅ **Knowledge Graph** - RDF-based central data store with SPARQL queries

---

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

**Note**: Your API keys are already configured in `.env` if you're continuing work on this project.

### Run Dashboard

```bash
# Launch Streamlit dashboard
./run_dashboard.sh

# Or directly
streamlit run dashboard/app.py
```

**Access at:** http://localhost:8501

---

## Architecture

### 4-Layer Pipeline

```
Layer 1: Structured Extraction (GPT-4o)
  ↓ Categorical labels (importance, allocation, BSC perspective)
Layer 2: Alignment Scoring (LLM-as-Judge)
  ↓ Relevance (direct/partial/indirect/none)
Layer 3: Completeness Analysis (SPARQL + LLM)
  ↓ Orphans, gaps, cascade strength, resource sufficiency
Layer 4: Benchmarking & Suggestions (COBIT/ISO + Agent)
  ↓ Governance validation, improvement recommendations
Metrics: 6 Composite Scores
  ↓ SAI, Coverage, Priority, KPI Utility, Catchball, EGI
Dashboard: Interactive Visualization
```

### Technology Stack

- **Python 3.11+** - Core language
- **GPT-4o** - LLM for extraction, scoring, and analysis
- **LangChain** - Agent orchestration
- **RDFLib** - Knowledge Graph (RDF triples)
- **NetworkX** - Graph algorithms
- **Streamlit** - Interactive dashboard
- **Plotly** - Charts and visualizations
- **Pyvis** - Network graph visualization
- **pdfplumber** - PDF parsing

---

## Dashboard

### 5 Pages

#### 📤 Page 1: Upload Plans
- Upload PDF strategic plan
- Configure section page ranges
- Run complete 4-layer analysis
- Real-time progress tracking
- Quick summary with overall score

#### 📊 Page 2: Overall Sync
- 6 composite metric gauges (SAI, Coverage, Priority, KPI Utility, Catchball, EGI)
- BSC radar chart (4 perspectives)
- Alert system (critical/high/medium/low)
- Detailed metrics table

#### 🔄 Page 3: Strategy Matrix
- Alignment heatmap (objectives × task groups)
- Detailed alignment table with reasoning
- Priority matrix (importance vs allocation)
- Resource allocation gap detection

#### ⚠️ Page 4: Gap Analysis
- Orphan detection (objectives without tasks, tasks without objectives)
- BSC balance (missing perspectives)
- Execution gaps (importance-allocation mismatches)
- COBIT/ISO validation results
- AI-generated improvement suggestions

#### 🕸️ Page 5: Knowledge Graph
- Interactive network visualization (pyvis)
- Filterable node types
- Physics-based layout
- Export to Turtle (.ttl) or RDF/XML (.rdf)
- Graph statistics

---

## Core Modules

### `core/ingestion.py`
PDF parsing and section detection using pdfplumber.

### `core/extractor.py` (Layer 1)
Structured extraction with GPT-4o:
- Strategic objectives: importance, BSC perspective, KPIs, goals
- Task groups: resource allocation, tasks, deadlines, assignees

### `core/knowledge_graph.py`
RDF Knowledge Graph with:
- Pre-loaded BSC perspectives (4)
- Pre-loaded COBIT goals (26)
- SPARQL query interface
- NetworkX export

### `core/alignment.py` (Layer 2)
LLM-as-Judge alignment scoring:
- Relevance: none/indirect/partial/direct
- Contribution strength: tangential/supporting/primary
- Reasoning extraction

### `core/completeness.py` (Layer 3)
Gap detection and analysis:
- SPARQL orphan detection
- BSC chain verification
- Goal cascade analysis (strong/moderate/weak/none)
- Resource sufficiency (fully_sufficient/adequate/insufficient/severely_lacking)
- Execution gap severity

### `core/benchmarking.py` (Layer 4)
Governance benchmarking:
- IT context detection (keyword-based)
- COBIT 2019 EG mapping (conditional)
- ISO 38500 validation (6 principles)
- ReAct agent with tools for suggestions

### `core/metrics.py`
Score computation from categorical labels:
- SAI (Strategic Alignment Index)
- Coverage (% of objectives with tasks)
- Weighted Priority Score
- KPI Utility Score
- Catchball Consistency
- EGI (Execution Gap Index)

---

## 6 Composite Metrics

| Metric | Formula | Range | Description |
|--------|---------|-------|-------------|
| **SAI** | Avg(alignment_scores) | 0-100 | Average alignment across all pairs |
| **Coverage** | (supported_objs / total_objs) × 100 | 0-100% | % of objectives with supporting tasks |
| **Priority** | 0.50×importance + 0.30×allocation + 0.20×risk | 0-100 | Weighted priority score |
| **KPI Utility** | 0.4×baseline + 0.4×measurable + 0.2×owner | 0-100 | KPI quality score |
| **Catchball** | (cascade × sufficiency) / 100 | 0-100 | Goal cascade consistency |
| **EGI** | Avg gap severity | 0-100 | Execution gap severity (lower is better) |

**Overall Score:** Average of all 6 metrics (with EGI inverted)

---

## Categorical Design Principle

**Why categorical?**
- LLMs excel at classification (better than regression)
- Categorical labels are interpretable and auditable
- Deterministic mapping ensures consistency
- Easy to adjust scoring weights

**Mapping Tables:**
```python
IMPORTANCE_MAP = {"critical": 100, "high": 75, "moderate": 50, "low": 25, "negligible": 0}
ALLOCATION_MAP = {"heavy": 100, "moderate": 70, "light": 40, "minimal": 10}
RELEVANCE_MAP = {"direct": 100, "partial": 60, "indirect": 30, "none": 0}
```

---

## Example Usage

### Command Line

```python
from core import (
    DocumentIngestion,
    StructuredExtractor,
    KnowledgeGraph,
    AlignmentScorer,
    CompletenessAnalyzer,
    BenchmarkingAgent,
)
from core.metrics import compute_all_metrics

# 1. Ingest PDF
doc = DocumentIngestion("strategic_plan.pdf")
strategic_text, action_text = doc.extract_sections(
    strategic_start=1, strategic_end=10,
    action_start=11, action_end=None
)

# 2. Extract (Layer 1)
extractor = StructuredExtractor(api_key="sk-...")
objectives = extractor.extract_strategic_plan(strategic_text)
task_groups = extractor.extract_action_plan(action_text)

# 3. Build Knowledge Graph
kg = KnowledgeGraph()
extractor.write_to_knowledge_graph(kg, objectives, task_groups)

# 4. Score Alignment (Layer 2)
scorer = AlignmentScorer(api_key="sk-...")
scorer.score_all_alignments(kg)

# 5. Analyze Completeness (Layer 3)
analyzer = CompletenessAnalyzer(api_key="sk-...")
completeness_results = analyzer.analyze_completeness(kg)

# 6. Benchmark (Layer 4)
agent = BenchmarkingAgent(api_key="sk-...")
benchmarking_results = agent.run_benchmarking(kg, completeness_results)

# 7. Compute Metrics
metrics = compute_all_metrics(kg)
print(f"SAI: {metrics['sai']:.2f}/100")
print(f"Coverage: {metrics['coverage']:.2f}%")
```

---

## Project Structure

```
strategic-plan-synchronization-system/
├── core/                       # Core analysis modules
│   ├── __init__.py
│   ├── README.md              # Core modules guide
│   ├── ingestion.py           # PDF parsing
│   ├── knowledge_graph.py     # RDF Knowledge Graph
│   ├── extractor.py           # Layer 1: Extraction
│   ├── alignment.py           # Layer 2: Alignment
│   ├── completeness.py        # Layer 3: Completeness
│   ├── benchmarking.py        # Layer 4: Benchmarking
│   ├── metrics.py             # Score computation
│   ├── llm_factory.py         # Multi-provider LLM support
│   ├── llm_cache.py           # LLM response caching
│   ├── llm_logger.py          # LLM call logging
│   └── pipeline_state.py      # Pipeline state management
├── dashboard/                  # Streamlit dashboard
│   ├── app.py                 # Main application
│   └── pages/                 # Individual pages
│       ├── page_upload.py
│       ├── page_overall_sync.py
│       ├── page_strategy_matrix.py
│       ├── page_gap_analysis.py
│       └── page_knowledge_graph.py
├── lib/                       # Frontend libraries
│   ├── bindings/              # JS bindings
│   ├── tom-select/            # Select dropdown library
│   └── vis-9.1.2/             # Network visualization library
├── run_dashboard.sh           # Dashboard launcher script
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## Documentation

- **core/README.md** - Core modules documentation

---

## Performance

### Analysis Time

| Plan Size | Objectives | Tasks | LLM Calls | Time (GPT-4o) |
|-----------|------------|-------|-----------|---------------|
| Small | 3-5 | 5-10 | 30-70 | 1-2 min |
| Medium | 5-10 | 10-20 | 70-250 | 2-5 min |
| Large | 10-15 | 20-30 | 250-500 | 5-10 min |
| Very Large | 15+ | 30+ | 500+ | 10-20 min |

**LLM Call Formula:** 2 + 2(n×m) + n + 2 + agent

---

## Deployment

### Local

```bash
./run_dashboard.sh
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501"]
```

```bash
docker build -t bita .
docker run -p 8501:8501 -e OPENAI_API_KEY="sk-..." bita
```

---

## Sample Case

The system is designed for **IT strategic plans** but works for any strategic-action plan pairing.

**Example:** Rate Management System for Travel Agency
- **Strategic Plan**: IT modernization objectives (security, scalability, integration)
- **Action Plan**: Development tasks, infrastructure upgrades, security implementations
- **COBIT Mapping**: EG08 (Process Optimization), EG12 (Digital Transformation)
- **ISO 38500**: Strategy, Performance, Conformance validation

---

**Status:** ✅ **Production Ready**
**Version:** 0.1.0
**Last Updated:** 2026-02-15

---

**Ready to analyze your strategic plans? 🚀**

```bash
./run_dashboard.sh
```
