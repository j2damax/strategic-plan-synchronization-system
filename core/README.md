# BITA Core Modules

Implementation of Layer 1 (Structured Extraction) and Layer 2 (Alignment Scoring) for the BITA system.

## Modules

### `ingestion.py`
**PDF Document Parsing**

- `DocumentIngestion` class for extracting text from PDF files
- Supports **separate PDFs** (recommended) or **combined PDFs**
- Uses pdfplumber for reliable PDF parsing

**Option 1: Separate PDFs (Recommended)**
```python
from core.ingestion import DocumentIngestion

# Extract from separate strategic and action plan PDFs
strategic_text, action_text = DocumentIngestion.extract_from_separate_pdfs(
    strategic_pdf="strategic_plan.pdf",
    action_pdfs=["action_plan_1.pdf", "action_plan_2.pdf"]
)
```

**Option 2: Combined PDF**
```python
# Extract from a single PDF with both plans
strategic_text, action_text = DocumentIngestion.extract_from_combined_pdf(
    pdf_path="combined_plan.pdf",
    strategic_start=1,
    strategic_end=10,
    action_start=11
)
```

### `extractor.py`
**Layer 1 — Structured Extraction**

- `StructuredExtractor` class using GPT-4o for extraction
- Extracts strategic objectives with categorical labels:
  - `strategic_importance`: critical/high/moderate/low/negligible
  - `bsc_perspective`: financial/customer/internal_process/learning_growth
  - KPIs with metadata (baseline, measurability, owner)
- Extracts action plan task groups with categorical labels:
  - `resource_allocation`: heavy/moderate/light/minimal
  - Tasks with assignees, deadlines, status
- Writes extracted data to Knowledge Graph

```python
from core.extractor import StructuredExtractor
from core.knowledge_graph import KnowledgeGraph

extractor = StructuredExtractor(api_key="sk-...")
objectives = extractor.extract_strategic_plan(strategic_text)
task_groups = extractor.extract_action_plan(action_text)

kg = KnowledgeGraph()
extractor.write_to_knowledge_graph(kg, objectives, task_groups)
```

### `knowledge_graph.py`
**Central RDF Knowledge Graph**

- `KnowledgeGraph` class wrapping RDFLib
- Pre-loaded static instances:
  - 4 BSC Perspectives (Financial, Customer, Internal Process, Learning & Growth)
  - 13 COBIT Enterprise Goals (EG01-EG13)
  - 13 COBIT Alignment Goals (AG01-AG13)
  - EG→AG mappings
- Methods for adding entities, relationships, SPARQL queries
- Export to NetworkX for graph analysis
- Serialization to Turtle/RDF-XML

```python
from core.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()
kg.add_entity("S1", "StrategicObjective", {
    "objectiveName": "Modernize IT Infrastructure",
    "strategicImportance": "critical"
})
kg.add_relationship("S1", "bscPerspective", "BSC_InternalProcess")

# Query with SPARQL
results = kg.query_sparql("""
    SELECT ?obj WHERE {
        ?obj rdf:type bita:StrategicObjective .
    }
""")

# Export
kg.save("output/graph.ttl", format="turtle")
G = kg.export_to_networkx()
```

### `alignment.py`
**Layer 2 — LLM-as-Judge Alignment Scoring**

- `AlignmentScorer` class for evaluating strategic-action alignment
- For each (objective, task_group) pair, classifies:
  - `relevance`: none/indirect/partial/direct
  - `contribution_strength`: tangential/supporting/primary
  - `reasoning`: Brief explanation
- Writes alignment relationships to Knowledge Graph
- Only creates edges for meaningful alignments (relevance ≠ "none")

```python
from core.alignment import AlignmentScorer

scorer = AlignmentScorer(api_key="sk-...")
scorer.score_all_alignments(kg)
```

### `metrics.py`
**Score Computation from Categorical Labels**

- Mapping tables: `IMPORTANCE_MAP`, `ALLOCATION_MAP`, `RELEVANCE_MAP`, etc.
- Functions for computing 6 composite metrics:
  1. **SAI (Strategic Alignment Index)**: Average alignment score across all pairs
  2. **Coverage**: % of objectives with at least one supporting task
  3. **Weighted Priority Score**: 0.50×importance + 0.30×allocation + 0.20×risk
  4. **KPI Utility**: Baseline×0.4 + Measurable×0.4 + Owner×0.2
  5. **Catchball Consistency**: cascade × sufficiency / 100
  6. **EGI (Execution Gap Index)**: Gap severity score
- `compute_all_metrics(kg)` returns all 6 metrics from Knowledge Graph

```python
from core.metrics import compute_all_metrics, compute_alignment_score

metrics = compute_all_metrics(kg)
print(f"SAI: {metrics['sai']:.2f}/100")
print(f"Coverage: {metrics['coverage']:.2f}%")

# Individual score computation
score = compute_alignment_score("direct")  # Returns 100
```

## Data Flow

```
PDF File
  ↓
[DocumentIngestion] → strategic_text, action_text
  ↓
[StructuredExtractor] → objectives[], task_groups[]
  ↓
[KnowledgeGraph] ← write entities & relationships
  ↓
[AlignmentScorer] ← read pairs from KG, evaluate alignment → write back to KG
  ↓
[compute_all_metrics] ← read from KG → return 6 metrics
```

## Categorical Design

**Why Categorical?**
- LLMs are better at classification than regression
- Categorical labels are interpretable and auditable
- Deterministic mapping to numbers ensures consistency
- Allows for easy adjustment of scoring weights

**Mapping Tables** (PROJECT_PLAN.md Section 2):
```python
IMPORTANCE_MAP = {"critical": 100, "high": 75, "moderate": 50, "low": 25, "negligible": 0}
ALLOCATION_MAP = {"heavy": 100, "moderate": 70, "light": 40, "minimal": 10}
RELEVANCE_MAP = {"direct": 100, "partial": 60, "indirect": 30, "none": 0}
RANGE_WIDTH = 30  # Gap between score levels
```

## Example Usage

See `example_layer1_2.py` in the project root for a complete pipeline demonstration.

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# Run the example
python example_layer1_2.py
```

## Dependencies

- `langchain-openai`: LLM integration (GPT-4o)
- `rdflib`: RDF graph storage and SPARQL queries
- `networkx`: Graph analysis and algorithms
- `pdfplumber`: PDF text extraction

See `requirements.txt` for complete dependency list.

### `completeness.py`
**Layer 3 — Completeness Analysis**

- `CompletenessAnalyzer` class for gap detection and constraint validation
- SPARQL-based orphan detection (objectives without tasks, tasks without objectives)
- BSC causal chain coverage verification
- LLM-based goal cascade analysis (strong/moderate/weak/none)
- LLM-based resource sufficiency evaluation (fully_sufficient/adequate/insufficient/severely_lacking)
- Execution gap analysis (compares importance vs allocation)
- Writes cascade and sufficiency data back to Knowledge Graph

```python
from core.completeness import CompletenessAnalyzer

analyzer = CompletenessAnalyzer(api_key="sk-...")
results = analyzer.analyze_completeness(kg)

print(f"Orphan Objectives: {results['orphan_objectives']}")
print(f"BSC Balanced: {results['bsc_analysis']['balanced']}")
print(f"Gap Severity: {results['gap_analysis']['overall_severity']}")
```

### `benchmarking.py`
**Layer 4 — Benchmarking & Agent-Driven Suggestions**

- `BenchmarkingAgent` class for COBIT/ISO validation and improvement suggestions
- IT context detection (keyword-based, determines COBIT applicability)
- COBIT 2019 Enterprise Goal mapping (conditional, LLM-based)
- ISO 38500 principles validation (6 principles: Responsibility, Strategy, Acquisition, Performance, Conformance, Human Behavior)
- ReAct agent with specialized tools for generating improvement suggestions
- Fallback to rule-based suggestions if agent fails
- Writes COBIT mappings to Knowledge Graph

```python
from core.benchmarking import BenchmarkingAgent

agent = BenchmarkingAgent(api_key="sk-...")
results = agent.run_benchmarking(kg, completeness_results)

print(f"IT-Focused: {results['is_it_focused']}")
print(f"COBIT Mappings: {results['cobit_mappings']}")
print(f"ISO Validation: {results['iso_validation']}")
print(f"Suggestions: {results['suggestions']}")
```

## Complete Pipeline

All 4 layers are now implemented. See `example_full_pipeline.py` for a complete demonstration.

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export OPENAI_API_KEY="sk-..."

# Run complete pipeline
python example_full_pipeline.py
```

**Pipeline Flow:**
```
Layer 1: PDF → Extract → Objectives + Task Groups → KG
Layer 2: KG → Evaluate Alignment → Relevance + Strength → KG
Layer 3: KG → Detect Gaps → Cascade + Sufficiency → KG
Layer 4: KG → Benchmark → COBIT/ISO + Suggestions
Metrics: KG → Compute All 6 Metrics → Final Scores
```

See `PROJECT_PLAN.md` for complete architecture details and `IMPLEMENTATION_LAYER3_4.md` for Layer 3 & 4 implementation summary.
