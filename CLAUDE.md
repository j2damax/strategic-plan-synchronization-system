# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BITA (Business-IT Alignment Intelligent System) is an AI-powered system for analyzing strategic plan alignment. It uses a **4-layer pipeline** that processes PDF documents through structured extraction, alignment scoring, completeness analysis, and benchmarking to produce 6 composite metrics measuring business-IT alignment.

## Development Commands

### Running the Application

```bash
source .venv/bin/activate
# Launch the Streamlit dashboard (primary interface)
./run_dashboard.sh
# or
streamlit run dashboard/app.py

# Run example pipeline (Layer 1-2)
python example_layer1_2.py
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_metrics.py

# Run with verbose output
pytest -v tests/
```

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys

# Or set environment variables directly
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Architecture

### 4-Layer Pipeline

The system processes strategic plans through four sequential layers:

```
Layer 1: Structured Extraction (extractor.py)
  - Extracts objectives and task groups from PDF with categorical labels
  - Labels: strategic_importance, bsc_perspective, resource_allocation
  - Writes extracted entities to Knowledge Graph

Layer 2: Alignment Scoring (alignment.py)
  - LLM-as-Judge evaluates (objective, task_group) pairs
  - Categorical outputs: relevance (none/indirect/partial/direct)
  - Creates alignment edges in Knowledge Graph

Layer 3: Completeness Analysis (completeness.py)
  - SPARQL-based orphan detection (objectives without tasks, etc.)
  - LLM-based cascade analysis and resource sufficiency evaluation
  - Execution gap detection (importance vs allocation mismatches)

Layer 4: Benchmarking (benchmarking.py)
  - COBIT 2019 mapping (conditional on IT context detection)
  - ISO 38500 validation (6 principles)
  - ReAct agent generates improvement suggestions

Final: Metrics Computation (metrics.py)
  - 6 composite scores: SAI, Coverage, Priority, KPI Utility, Catchball, EGI
  - Deterministic mapping from categorical labels to numeric scores
```

### Central Knowledge Graph

The **KnowledgeGraph** (RDF-based with RDFLib) is the central data store:

- All extracted data, relationships, and scores flow through the KG
- Pre-loaded with BSC perspectives and COBIT/ISO frameworks
- Queried with SPARQL for analysis
- Exported to NetworkX for visualization
- Serialized to Turtle/RDF-XML for persistence

**Key pattern**: Each layer reads from KG, processes, and writes results back to KG. This enables:
- State inspection between layers (via PipelineState)
- SPARQL-based analysis queries
- Unified data model across all components

### Module Structure

```
core/
├── ingestion.py         # PDF parsing with pdfplumber
├── extractor.py         # Layer 1: GPT-4o structured extraction
├── knowledge_graph.py   # Central RDF graph (RDFLib + SPARQL)
├── alignment.py         # Layer 2: LLM-as-Judge alignment scoring
├── completeness.py      # Layer 3: Gap detection and analysis
├── benchmarking.py      # Layer 4: COBIT/ISO + ReAct agent
├── metrics.py           # Score computation from categorical labels
├── pipeline_state.py    # KG snapshots and SHACL validation
├── llm_factory.py       # Multi-provider LLM abstraction
├── llm_cache.py         # SQLite-based LLM response caching
└── llm_logger.py        # LLM call logging and debugging

dashboard/
├── app.py               # Main Streamlit app with navigation
└── pages/               # 5 dashboard pages (upload, sync, matrix, gaps, graph)
```

### LLM Abstraction

**Multi-provider support** via `llm_factory.py`:
- Supports Anthropic (Claude) and OpenAI (GPT)
- Default: Anthropic Claude Sonnet 4.5
- All modules accept `api_key`, `model`, and `provider` parameters
- Use `create_llm(provider, model, api_key)` to instantiate models

**Caching**: LLM responses are cached in SQLite (`setup_cache()` in `llm_cache.py`)
**Logging**: All LLM calls logged via `log_llm_call()` for debugging

## Key Design Principles

### Categorical Design

**Critical**: This system uses **categorical labels** instead of numeric scores from LLMs.

- LLMs classify into predefined categories (e.g., "critical"/"high"/"moderate")
- Deterministic mapping tables convert categories to numbers
- Rationale: LLMs excel at classification vs regression; categorical is auditable

**When modifying extraction/scoring**:
- Always use categorical outputs in prompts
- Define clear mapping tables in `metrics.py`
- Never ask LLMs to directly output numeric scores

Example mapping:
```python
IMPORTANCE_MAP = {"critical": 100, "high": 75, "moderate": 50, "low": 25, "negligible": 0}
RELEVANCE_MAP = {"direct": 100, "partial": 60, "indirect": 30, "none": 0}
```

### SPARQL-First Analysis

For queries about the knowledge graph state, prefer SPARQL over programmatic iteration:

```python
# Good: SPARQL query
query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    SELECT ?obj WHERE {
        ?obj rdf:type bita:Objective .
        ?obj bita:strategicImportance "critical" .
    }
"""
results = kg.query_sparql(query)

# Avoid: Manual iteration when SPARQL suffices
```

### Session State in Dashboard

The Streamlit dashboard stores pipeline results in `st.session_state`:
- `kg`: KnowledgeGraph instance
- `metrics`: Computed metrics dict
- `completeness_results`: Layer 3 results
- `benchmarking_results`: Layer 4 results

**When adding new pages**: Always check for `st.session_state.kg` existence first.

## Common Development Patterns

### Adding a New Metric

1. Define categorical labels and mapping in `metrics.py`
2. Ensure LLM outputs match categories in extraction/scoring modules
3. Add computation function to `metrics.py`
4. Update `compute_all_metrics()` to include new metric
5. Add visualization to dashboard pages

### Adding a New LLM Provider

1. Update `LLM_PROVIDERS` dict in `llm_factory.py`
2. Add provider-specific model instantiation in `create_llm()`
3. Install provider's LangChain integration package
4. Test with example scripts

### Debugging LLM Calls

1. Check `.cache/llm_logs/` directory for logged calls
2. Use `log_llm_call()` to inspect prompts and responses
3. Enable verbose logging in LangChain if needed
4. Clear cache with `clear_cache()` to force re-execution

## Testing Notes

- Tests use pytest without fixtures (simple function-based tests)
- No pytest.ini or pyproject.toml configuration
- Test files mirror module names: `test_metrics.py` tests `metrics.py`
- Run individual tests: `pytest tests/test_metrics.py::test_function_name`

## Important Constraints

### API Keys

- API keys are stored in `.env` file (gitignored)
- `.env.example` provides a template for required keys
- The dashboard loads keys from `.env` via `run_dashboard.sh`
- Dashboard also accepts keys via UI (not persisted to disk)
- Example scripts use environment variables from `.env` or shell exports

### PDF Processing

- Strategic and action plans can be separate PDFs or combined
- Page ranges are configurable for combined PDFs
- Large PDFs (50+ pages) may take 2-5 minutes to process
- Uses `pdfplumber` for reliable text extraction

### Performance Considerations

- Alignment scoring is O(n×m) for n objectives and m task groups
- Large plans may require hundreds of LLM calls
- Caching is essential for development iteration
- Dashboard uses session state to avoid recomputation

## File Naming Conventions

- Core modules: lowercase with underscores (`knowledge_graph.py`)
- Dashboard pages: `page_*.py` prefix
- Example scripts: `example_*.py` prefix
- Tests: `test_*.py` prefix

## Common Pitfalls

1. **Don't bypass the Knowledge Graph**: All data should flow through KG, not passed directly between modules
2. **Don't use numeric prompts**: Always use categorical labels in LLM prompts
3. **Don't modify KG schema without updating SHACL shapes** in `pipeline_state.py`
4. **Don't assume KG state**: Always query to verify expected entities exist
5. **Check session state**: Dashboard pages fail if `st.session_state.kg` is None
