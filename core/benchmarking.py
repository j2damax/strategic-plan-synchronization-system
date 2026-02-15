"""Layer 4 — Benchmarking & Recommendations.

Assesses strategy-to-action alignment, generates deep entity-specific recommendations.
"""

import json
from typing import Any

from .knowledge_graph import KnowledgeGraph
from .llm_factory import DEFAULT_PROVIDER, LLM_PROVIDERS, create_llm
from .llm_logger import log_llm_call


VALID_VERDICTS = {"strong", "adequate", "weak", "critical"}

ALIGNMENT_DIMENSIONS = {
    "strategic_coverage": "Strategic Coverage",
    "alignment_quality": "Alignment Quality",
    "resource_adequacy": "Resource Adequacy",
    "goal_cascade_coherence": "Goal Cascade Coherence",
    "bsc_balance": "BSC Strategic Balance",
    "execution_readiness": "Execution Readiness",
}


class BenchmarkingAgent:
    """Agent for alignment assessment and improvement recommendations."""

    def __init__(self, api_key: str, model: str | None = None, provider: str = DEFAULT_PROVIDER):
        """Initialize benchmarking agent.

        Args:
            api_key: API key for the LLM provider
            model: Model to use (defaults to provider's default)
            provider: LLM provider name
        """
        if model is None:
            model = LLM_PROVIDERS[provider]["default_model"]
        self.llm = create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=0.3,  # Slightly creative for recommendations
        )
        self.kg = None

    def _build_alignment_context(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> str:
        """Build a text summary of alignment data for the LLM prompt.

        Queries the KG and reads completeness_results to collect goals,
        task groups, orphans, alignment distribution, execution gaps,
        cascade/sufficiency data, BSC balance, and KPI quality.
        Names are presented first for readability.
        """
        sections = []

        # 1. Goals summary
        goal_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?obj WHERE { ?obj rdf:type bita:Goal . }
        """
        goal_rows = kg.query_sparql(goal_query)
        goal_lines = []
        for row in goal_rows:
            obj_id = str(row["obj"]).split("#")[-1]
            props = kg.get_entity_properties(obj_id)
            support_count = sum(
                1 for k in props if k.startswith("alignment_") and k.endswith("_relevance")
            )
            bsc = props.get("bscPerspective", "N/A")
            label = props.get("label", obj_id)
            goal_lines.append(
                f"- {label} | importance={props.get('strategicImportance', 'N/A')} | bsc={bsc} | supporting_task_groups={support_count}"
            )
        sections.append(f"GOALS ({len(goal_lines)}):\n" + "\n".join(goal_lines) if goal_lines else "GOALS: None found")

        # 2. Task groups summary
        tg_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?tg WHERE { ?tg rdf:type bita:TaskGroup . }
        """
        tg_rows = kg.query_sparql(tg_query)
        tg_lines = []
        for row in tg_rows:
            tg_id = str(row["tg"]).split("#")[-1]
            props = kg.get_entity_properties(tg_id)
            tg_label = props.get("label", tg_id)
            # Resolve supported objective names
            supported_names = []
            for k in props:
                if k.startswith("alignment_") and k.endswith("_relevance"):
                    o_id = k.replace("alignment_", "").replace("_relevance", "")
                    o_props = kg.get_entity_properties(o_id)
                    supported_names.append(o_props.get("label", o_id))
            tg_lines.append(
                f"- {tg_label} | allocation={props.get('resourceAllocation', 'N/A')} | supports={', '.join(supported_names) if supported_names else 'none'}"
            )
        sections.append(f"TASK GROUPS ({len(tg_lines)}):\n" + "\n".join(tg_lines) if tg_lines else "TASK GROUPS: None found")

        # 3. Orphans (resolve names)
        orphan_objs = completeness_results.get("orphan_objectives", [])
        orphan_tasks = completeness_results.get("orphan_tasks", [])
        orphan_obj_names = [kg.get_entity_properties(oid).get("label", oid) for oid in orphan_objs[:5]]
        orphan_tg_names = [kg.get_entity_properties(tid).get("label", tid) for tid in orphan_tasks[:5]]
        sections.append(
            f"ORPHANS: {len(orphan_objs)} orphan objectives ({', '.join(orphan_obj_names)}), "
            f"{len(orphan_tasks)} orphan tasks ({', '.join(orphan_tg_names)})"
        )

        # 4. Alignment distribution
        relevance_counts = {"direct": 0, "partial": 0, "indirect": 0, "none": 0}
        for row in tg_rows:
            tg_id = str(row["tg"]).split("#")[-1]
            props = kg.get_entity_properties(tg_id)
            for k, v in props.items():
                if k.startswith("alignment_") and k.endswith("_relevance"):
                    relevance_counts[v] = relevance_counts.get(v, 0) + 1
        sections.append(f"ALIGNMENT DISTRIBUTION: {relevance_counts}")

        # 5. Execution gaps (with entity names)
        gap_analysis = completeness_results.get("gap_analysis", {})
        overall_severity = gap_analysis.get("overall_severity", "low")
        total_gaps = gap_analysis.get("total_gaps", 0)
        gaps = gap_analysis.get("gaps", [])
        top_gaps = "; ".join(
            f"{kg.get_entity_properties(g['objective_id']).get('label', g['objective_id'])}→"
            f"{kg.get_entity_properties(g['task_group_id']).get('label', g['task_group_id'])} "
            f"gap={g['gap_score']:.0f} ({g['severity']})"
            for g in gaps[:5]
        )
        sections.append(f"EXECUTION GAPS: severity={overall_severity}, total={total_gaps}, top: {top_gaps or 'none'}")

        # 6. Cascade / sufficiency from KG
        cascade_strengths = {"strong": 0, "moderate": 0, "weak": 0}
        sufficiency_levels = {"fully_sufficient": 0, "partially_sufficient": 0, "insufficient": 0}
        for row in tg_rows:
            tg_id = str(row["tg"]).split("#")[-1]
            props = kg.get_entity_properties(tg_id)
            for k, v in props.items():
                if k.startswith("cascade_") and k.endswith("_strength"):
                    cascade_strengths[v] = cascade_strengths.get(v, 0) + 1
                if k.startswith("sufficiency_") and k.endswith("_level"):
                    sufficiency_levels[v] = sufficiency_levels.get(v, 0) + 1
        sections.append(f"CASCADE STRENGTHS: {cascade_strengths}")
        sections.append(f"SUFFICIENCY LEVELS: {sufficiency_levels}")

        # 7. BSC balance
        bsc = completeness_results.get("bsc_analysis", {})
        coverage = bsc.get("coverage", {})
        missing = bsc.get("missing_perspectives", [])
        causal_links = completeness_results.get("causal_links", [])
        causal_summary = ", ".join(
            f"{l['source_perspective']}→{l['target_perspective']}({l['strength']})"
            for l in causal_links[:5]
        )
        sections.append(
            f"BSC BALANCE: coverage={coverage}, missing={missing}, "
            f"causal_links={len(causal_links)} [{causal_summary}]"
        )

        # 8. KPI quality (with names)
        kpi_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?kpi WHERE { ?kpi rdf:type bita:KPI . }
        """
        kpi_rows = kg.query_sparql(kpi_query)
        kpi_total = len(kpi_rows)
        kpi_with_baseline = 0
        kpi_measurable = 0
        kpi_with_owner = 0
        kpi_names = []
        for row in kpi_rows:
            kpi_id = str(row["kpi"]).split("#")[-1]
            props = kg.get_entity_properties(kpi_id)
            kpi_names.append(props.get("label", kpi_id))
            if props.get("baseline"):
                kpi_with_baseline += 1
            if props.get("measurability") in ("quantitative", "high"):
                kpi_measurable += 1
            if props.get("owner"):
                kpi_with_owner += 1
        sections.append(
            f"KPI QUALITY: total={kpi_total}, with_baseline={kpi_with_baseline}, "
            f"measurable={kpi_measurable}, with_owner={kpi_with_owner}"
            f"{', names: ' + ', '.join(kpi_names) if kpi_names else ''}"
        )

        return "\n\n".join(sections)

    def assess_alignment(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> dict[str, Any]:
        """Assess strategy-to-action alignment across 6 dimensions.

        Args:
            kg: KnowledgeGraph instance
            completeness_results: Results from Layer 3

        Returns:
            Dictionary mapping dimension key to {verdict, reasoning}
        """
        context = self._build_alignment_context(kg, completeness_results)

        prompt = f"""You are evaluating how well an organization's actions align with its strategy.

Below is a data summary from alignment analysis layers:

{context}

Assess these 6 alignment dimensions. For each, provide:
- a verdict (strong / adequate / weak / critical)
- a brief reasoning sentence
- 1-3 specific examples from the data above that support your verdict. Each example MUST use entity titles/names (e.g., "Revenue Growth", "Sales Initiative", "Customer Satisfaction KPI"). NEVER use internal codes like G1, TG2, G1_O1, A1_2 in the examples. Write examples in plain language that a business user can understand.

Dimensions:
1. strategic_coverage — Are all objectives backed by action plans? Consider orphan counts and coverage.
2. alignment_quality — How strong are the strategy-action links? Consider alignment relevance/strength distribution.
3. resource_adequacy — Does resource allocation match strategic priorities? Consider execution gaps.
4. goal_cascade_coherence — Do task goals flow logically from strategy? Consider cascade strengths and sufficiency levels.
5. bsc_balance — Is there balanced BSC perspective coverage with causal links? Consider BSC coverage and causal link data.
6. execution_readiness — Are actions concrete and measurable? Consider KPI quality indicators.

Return ONLY valid JSON:
{{
  "strategic_coverage": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}},
  "alignment_quality": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}},
  "resource_adequacy": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}},
  "goal_cascade_coherence": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}},
  "bsc_balance": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}},
  "execution_readiness": {{"verdict": "...", "reasoning": "...", "examples": ["..."]}}
}}

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(
            caller="BenchmarkingAgent.assess_alignment",
            prompt=prompt,
            response=content,
            layer=4,
        )

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            content = "\n".join(json_lines)

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            log_llm_call(
                caller="BenchmarkingAgent.assess_alignment",
                prompt=prompt,
                response=content,
                error=str(e),
                layer=4,
            )
            result = {}

        # Validate: ensure all 6 keys present with valid verdicts and examples
        for dim_key in ALIGNMENT_DIMENSIONS:
            if dim_key not in result or not isinstance(result[dim_key], dict):
                result[dim_key] = {"verdict": "weak", "reasoning": "Unable to assess (data unavailable).", "examples": []}
            else:
                verdict = result[dim_key].get("verdict", "").lower()
                if verdict not in VALID_VERDICTS:
                    result[dim_key]["verdict"] = "weak"
                else:
                    result[dim_key]["verdict"] = verdict
                # Ensure examples is a list of strings
                examples = result[dim_key].get("examples", [])
                if not isinstance(examples, list):
                    examples = []
                result[dim_key]["examples"] = [str(e) for e in examples if e]

        return result

    def _build_recommendations_context(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> str:
        """Build rich entity-level context for the recommendations LLM call.

        Includes full details of every goal, objective, task group, KPI,
        orphans, execution gaps, BSC data, and cascade/sufficiency info.
        Names are presented first for readability.
        """
        sections = []

        # 1. Goals with objectives
        goal_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?g WHERE { ?g rdf:type bita:Goal . }
        """
        goal_rows = kg.query_sparql(goal_query)
        goal_lines = []
        goal_map = {}  # goal_id -> props for reuse
        for row in goal_rows:
            g_id = str(row["g"]).split("#")[-1]
            props = kg.get_entity_properties(g_id)
            goal_map[g_id] = props
            g_label = props.get("label", g_id)
            # Find objectives under this goal
            obj_query = f"""
            PREFIX bita: <http://bita-system.org/ontology#>
            SELECT ?o WHERE {{ bita:{g_id} bita:hasObjective ?o . }}
            """
            obj_rows = kg.query_sparql(obj_query)
            obj_names = []
            for orow in obj_rows:
                o_id = str(orow["o"]).split("#")[-1]
                oprops = kg.get_entity_properties(o_id)
                obj_names.append(oprops.get("label", o_id))
            goal_lines.append(
                f"- {g_label}, "
                f"description={props.get('description', 'N/A')}, "
                f"importance={props.get('strategicImportance', 'N/A')}, "
                f"bsc={props.get('bscPerspective', 'N/A')}, "
                f"objectives=[{', '.join(obj_names) if obj_names else 'none'}]"
            )
        sections.append(f"GOALS ({len(goal_lines)}):\n" + "\n".join(goal_lines) if goal_lines else "GOALS: None found")

        # 2. Objectives summary
        obj_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?obj WHERE { ?obj rdf:type bita:Objective . }
        """
        obj_rows = kg.query_sparql(obj_query)
        obj_lines = []
        for row in obj_rows:
            obj_id = str(row["obj"]).split("#")[-1]
            props = kg.get_entity_properties(obj_id)
            obj_label = props.get("label", obj_id)
            # Find parent goal
            parent_query = f"""
            PREFIX bita: <http://bita-system.org/ontology#>
            SELECT ?g WHERE {{ ?g bita:hasObjective bita:{obj_id} . }}
            """
            parent_rows = kg.query_sparql(parent_query)
            parent_id = str(parent_rows[0]["g"]).split("#")[-1] if parent_rows else "N/A"
            parent_label = goal_map.get(parent_id, {}).get("label", parent_id)
            # Find supporting task groups
            support_tgs = []
            tg_query2 = """
            PREFIX bita: <http://bita-system.org/ontology#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?tg WHERE { ?tg rdf:type bita:TaskGroup . }
            """
            for tg_row in kg.query_sparql(tg_query2):
                tg_id = str(tg_row["tg"]).split("#")[-1]
                tg_props = kg.get_entity_properties(tg_id)
                rel_key = f"alignment_{obj_id}_relevance"
                if rel_key in tg_props:
                    tg_label = tg_props.get("label", tg_id)
                    support_tgs.append(f"{tg_label} (relevance={tg_props[rel_key]}, strength={tg_props.get(f'alignment_{obj_id}_strength', 'N/A')})")
            obj_lines.append(
                f"- {obj_label}, "
                f"parent_goal={parent_label}, "
                f"importance={props.get('strategicImportance', 'N/A')}, "
                f"supporting_task_groups=[{', '.join(support_tgs) if support_tgs else 'none'}]"
            )
        sections.append(f"OBJECTIVES ({len(obj_lines)}):\n" + "\n".join(obj_lines) if obj_lines else "OBJECTIVES: None found")

        # 3. Task groups with full context
        tg_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?tg WHERE { ?tg rdf:type bita:TaskGroup . }
        """
        tg_rows = kg.query_sparql(tg_query)
        tg_lines = []
        for row in tg_rows:
            tg_id = str(row["tg"]).split("#")[-1]
            props = kg.get_entity_properties(tg_id)
            tg_label = props.get("label", tg_id)
            supported = []
            for k, v in props.items():
                if k.startswith("alignment_") and k.endswith("_relevance"):
                    o_id = k.replace("alignment_", "").replace("_relevance", "")
                    o_props = kg.get_entity_properties(o_id)
                    o_label = o_props.get("label", o_id)
                    supported.append(f"{o_label} (relevance={v}, strength={props.get(f'alignment_{o_id}_strength', 'N/A')})")
            # Count child tasks
            task_query = f"""
            PREFIX bita: <http://bita-system.org/ontology#>
            SELECT (COUNT(?t) AS ?cnt) WHERE {{ bita:{tg_id} bita:hasTask ?t . }}
            """
            task_rows = kg.query_sparql(task_query)
            task_count = int(task_rows[0]["cnt"]) if task_rows else 0
            tg_lines.append(
                f"- {tg_label}, "
                f"purpose={props.get('intendedPurpose', 'N/A')}, "
                f"allocation={props.get('resourceAllocation', 'N/A')}, "
                f"tasks={task_count}, "
                f"supports=[{', '.join(supported) if supported else 'none'}]"
            )
        sections.append(f"TASK GROUPS ({len(tg_lines)}):\n" + "\n".join(tg_lines) if tg_lines else "TASK GROUPS: None found")

        # 4. KPIs
        kpi_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?kpi WHERE { ?kpi rdf:type bita:KPI . }
        """
        kpi_rows = kg.query_sparql(kpi_query)
        kpi_lines = []
        for row in kpi_rows:
            kpi_id = str(row["kpi"]).split("#")[-1]
            props = kg.get_entity_properties(kpi_id)
            kpi_label = props.get("label", kpi_id)
            kpi_lines.append(
                f"- {kpi_label}, "
                f"type={props.get('kpiType', 'N/A')}, "
                f"owner={props.get('owner', 'N/A')}, "
                f"baseline={props.get('baseline', 'N/A')}, "
                f"measurability={props.get('measurability', 'N/A')}"
            )
        sections.append(f"KPIs ({len(kpi_lines)}):\n" + "\n".join(kpi_lines) if kpi_lines else "KPIs: None found")

        # 5. Orphan objectives with context
        orphan_objs = completeness_results.get("orphan_objectives", [])
        if orphan_objs:
            orphan_lines = []
            for obj_id in orphan_objs:
                props = kg.get_entity_properties(obj_id)
                obj_label = props.get("label", obj_id)
                parent_query = f"""
                PREFIX bita: <http://bita-system.org/ontology#>
                SELECT ?g WHERE {{ ?g bita:hasObjective bita:{obj_id} . }}
                """
                parent_rows = kg.query_sparql(parent_query)
                parent_id = str(parent_rows[0]["g"]).split("#")[-1] if parent_rows else "N/A"
                parent_props = goal_map.get(parent_id, {})
                parent_label = parent_props.get("label", parent_id)
                orphan_lines.append(
                    f"- {obj_label}, "
                    f"parent_goal={parent_label}, "
                    f"bsc={parent_props.get('bscPerspective', 'N/A')}, "
                    f"importance={props.get('strategicImportance', parent_props.get('strategicImportance', 'N/A'))}"
                )
            sections.append(f"ORPHAN OBJECTIVES ({len(orphan_lines)}):\n" + "\n".join(orphan_lines))
        else:
            sections.append("ORPHAN OBJECTIVES: None")

        # 6. Orphan task groups with context
        orphan_tasks = completeness_results.get("orphan_tasks", [])
        if orphan_tasks:
            orphan_tg_lines = []
            for tg_id in orphan_tasks:
                props = kg.get_entity_properties(tg_id)
                tg_label = props.get("label", tg_id)
                orphan_tg_lines.append(
                    f"- {tg_label}, "
                    f"purpose={props.get('intendedPurpose', 'N/A')}, "
                    f"allocation={props.get('resourceAllocation', 'N/A')}"
                )
            sections.append(f"ORPHAN TASK GROUPS ({len(orphan_tg_lines)}):\n" + "\n".join(orphan_tg_lines))
        else:
            sections.append("ORPHAN TASK GROUPS: None")

        # 7. Execution gaps with entity names
        gap_analysis = completeness_results.get("gap_analysis", {})
        gaps = gap_analysis.get("gaps", [])
        if gaps:
            gap_lines = []
            for g in gaps:
                obj_id = g["objective_id"]
                tg_id = g["task_group_id"]
                obj_label = kg.get_entity_properties(obj_id).get("label", obj_id)
                tg_label = kg.get_entity_properties(tg_id).get("label", tg_id)
                gap_lines.append(
                    f"- {obj_label} → {tg_label}: "
                    f"importance={g['importance']}, allocation={g['allocation']}, "
                    f"gap={g['gap_score']:.0f}, severity={g['severity']}"
                )
            sections.append(
                f"EXECUTION GAPS ({len(gap_lines)}, overall={gap_analysis.get('overall_severity', 'low')}):\n"
                + "\n".join(gap_lines)
            )
        else:
            sections.append("EXECUTION GAPS: None")

        # 8. BSC balance + causal links
        bsc = completeness_results.get("bsc_analysis", {})
        coverage = bsc.get("coverage", {})
        missing = bsc.get("missing_perspectives", [])
        causal_links = completeness_results.get("causal_links", [])
        causal_summary = ", ".join(
            f"{l['source_name']}({l['source_perspective']})→{l['target_name']}({l['target_perspective']}) [{l['strength']}]"
            for l in causal_links[:8]
        )
        sections.append(
            f"BSC BALANCE: coverage={coverage}, missing={missing}, "
            f"causal_links={len(causal_links)} [{causal_summary}]"
        )

        # 9. Cascade / sufficiency (with names)
        cascade_details = []
        for row in tg_rows:
            tg_id = str(row["tg"]).split("#")[-1]
            props = kg.get_entity_properties(tg_id)
            tg_label = props.get("label", tg_id)
            for k, v in props.items():
                if k.startswith("cascade_") and k.endswith("_strength"):
                    o_id = k.replace("cascade_", "").replace("_strength", "")
                    o_label = kg.get_entity_properties(o_id).get("label", o_id)
                    suf_key = f"sufficiency_{o_id}_level"
                    cascade_details.append(
                        f"- {tg_label}→{o_label}: cascade={v}, sufficiency={props.get(suf_key, 'N/A')}"
                    )
        if cascade_details:
            sections.append(f"CASCADE & SUFFICIENCY:\n" + "\n".join(cascade_details))

        return "\n\n".join(sections)

    def generate_recommendations(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> list[dict[str, Any]]:
        """Generate deep, entity-specific recommendations via a single LLM call.

        Args:
            kg: KnowledgeGraph instance
            completeness_results: Results from Layer 3 analysis

        Returns:
            List of recommendation dictionaries with structured fields
        """
        context = self._build_recommendations_context(kg, completeness_results)

        prompt = f"""You are an expert in Business-IT Alignment and Balanced Scorecard strategy.

Below is a detailed data summary of an organization's strategic plan analysis, including goals, objectives, task groups, KPIs, orphans, execution gaps, BSC coverage, and cascade data.

{context}

Based on this data, generate 4-8 specific, actionable recommendations. Each recommendation MUST reference actual entity names/titles from the data above (not generic advice).

IMPORTANT: In all text fields (title, gap_description, business_impact, recommended_actions), always use entity titles/names (e.g., "Revenue Growth", "Sales Initiative"). NEVER use internal codes like G1, TG2, G1_O1, A1_2. Write in plain language that a business user can understand. The only place codes should appear is in the "affected_entities" array.

Return ONLY a valid JSON array. Each element must have these fields:
- "title": Short entity-specific title using names (e.g., "Allocate Resources for Digital Transformation Initiative")
- "category": one of "orphan_objective" | "orphan_task" | "resource_gap" | "bsc_gap" | "alignment_weakness" | "kpi_quality"
- "priority": one of "critical" | "high" | "medium" | "low"
- "priority_reasoning": Why this priority level
- "gap_description": What the gap is, referencing specific entity names (not codes)
- "business_impact": Why this gap matters for the organization
- "recommended_actions": Array of 2-3 specific actionable steps using entity names
- "affected_entities": Array of entity IDs involved (e.g., ["G1", "TG2", "O1"])

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(
            caller="BenchmarkingAgent.generate_recommendations",
            prompt=prompt,
            response=content,
            layer=4,
        )

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            content = "\n".join(json_lines)

        try:
            result = json.loads(content)
            if not isinstance(result, list):
                raise ValueError("Expected JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            log_llm_call(
                caller="BenchmarkingAgent.generate_recommendations",
                prompt=prompt,
                response=content,
                error=str(e),
                layer=4,
            )
            return self._generate_fallback_recommendations(kg, completeness_results)

        # Validate each recommendation has required fields
        valid_categories = {"orphan_objective", "orphan_task", "resource_gap", "bsc_gap", "alignment_weakness", "kpi_quality"}
        valid_priorities = {"critical", "high", "medium", "low"}
        validated = []
        for rec in result:
            if not isinstance(rec, dict):
                continue
            # Ensure required fields exist
            if not rec.get("title") or not rec.get("gap_description"):
                continue
            rec["category"] = rec.get("category", "alignment_weakness")
            if rec["category"] not in valid_categories:
                rec["category"] = "alignment_weakness"
            rec["priority"] = rec.get("priority", "medium").lower()
            if rec["priority"] not in valid_priorities:
                rec["priority"] = "medium"
            rec.setdefault("priority_reasoning", "")
            rec.setdefault("business_impact", "")
            rec.setdefault("recommended_actions", [])
            rec.setdefault("affected_entities", [])
            validated.append(rec)

        return validated if validated else self._generate_fallback_recommendations(kg, completeness_results)

    def _generate_fallback_recommendations(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> list[dict[str, Any]]:
        """Generate rule-based recommendations when LLM call fails.

        Args:
            kg: KnowledgeGraph instance
            completeness_results: Results from Layer 3

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # Orphan objectives
        orphan_objs = completeness_results.get("orphan_objectives", [])
        for obj_id in orphan_objs:
            props = kg.get_entity_properties(obj_id)
            name = props.get("label", obj_id)
            recommendations.append({
                "title": f"Create Action Plan for '{name}'",
                "category": "orphan_objective",
                "priority": "high",
                "priority_reasoning": "Objectives without supporting tasks cannot be executed.",
                "gap_description": f"Objective '{name}' ({obj_id}) has no supporting task groups assigned to it.",
                "business_impact": f"Without action plans, the objective '{name}' remains aspirational and will not translate into operational outcomes.",
                "recommended_actions": [
                    f"Identify or create task groups that can support '{name}'.",
                    f"Assign appropriate resource allocation to new task groups.",
                    f"Define KPIs to track progress toward '{name}'.",
                ],
                "affected_entities": [obj_id],
            })

        # Orphan tasks
        orphan_tasks = completeness_results.get("orphan_tasks", [])
        for tg_id in orphan_tasks:
            props = kg.get_entity_properties(tg_id)
            name = props.get("label", tg_id)
            purpose = props.get("intendedPurpose", "N/A")
            recommendations.append({
                "title": f"Align '{name}' to Strategic Objectives",
                "category": "orphan_task",
                "priority": "medium",
                "priority_reasoning": "Unaligned task groups consume resources without strategic justification.",
                "gap_description": f"Task group '{name}' ({tg_id}, purpose: {purpose}) has no alignment to any strategic objective.",
                "business_impact": f"Resources allocated to '{name}' may be wasted if not aligned to organizational strategy.",
                "recommended_actions": [
                    f"Review the intended purpose of '{name}' and map it to relevant objectives.",
                    f"If no strategic fit exists, consider reallocating its resources.",
                ],
                "affected_entities": [tg_id],
            })

        # BSC gaps
        bsc = completeness_results.get("bsc_analysis", {})
        missing = bsc.get("missing_perspectives", [])
        if missing:
            recommendations.append({
                "title": f"Address Missing BSC Perspectives: {', '.join(missing)}",
                "category": "bsc_gap",
                "priority": "high",
                "priority_reasoning": "Unbalanced BSC coverage leads to strategic blind spots.",
                "gap_description": f"The strategic plan lacks goals in {len(missing)} BSC perspective(s): {', '.join(missing)}.",
                "business_impact": "An unbalanced strategy risks neglecting critical areas, leading to unsustainable performance.",
                "recommended_actions": [
                    f"Define at least one strategic goal for each missing perspective: {', '.join(missing)}.",
                    "Ensure new goals have measurable objectives and KPIs.",
                    "Assign task groups to support the new goals.",
                ],
                "affected_entities": [f"BSC_{p.replace(' ', '').replace('&', '')}" for p in missing],
            })

        # Execution gaps
        gap_analysis = completeness_results.get("gap_analysis", {})
        gaps = gap_analysis.get("gaps", [])
        for gap in gaps:
            if gap["severity"] in ("critical", "high"):
                obj_id = gap["objective_id"]
                tg_id = gap["task_group_id"]
                obj_props = kg.get_entity_properties(obj_id)
                tg_props = kg.get_entity_properties(tg_id)
                obj_name = obj_props.get("label", obj_id)
                tg_name = tg_props.get("label", tg_id)
                recommendations.append({
                    "title": f"Increase Resources for '{tg_name}' Supporting '{obj_name}'",
                    "category": "resource_gap",
                    "priority": gap["severity"],
                    "priority_reasoning": f"Gap score of {gap['gap_score']:.0f} indicates significant resource-importance mismatch.",
                    "gap_description": (
                        f"'{tg_name}' ({tg_id}) supports '{obj_name}' ({obj_id}) but has "
                        f"allocation={gap['allocation']} vs importance={gap['importance']} (gap={gap['gap_score']:.0f})."
                    ),
                    "business_impact": f"Under-resourcing '{tg_name}' jeopardizes achievement of '{obj_name}'.",
                    "recommended_actions": [
                        f"Increase resource allocation for '{tg_name}' from {gap['allocation']} to match strategic importance.",
                        f"Review and optimize task priorities within '{tg_name}'.",
                    ],
                    "affected_entities": [obj_id, tg_id],
                })

        return recommendations

    def run_benchmarking(
        self, kg: KnowledgeGraph, completeness_results: dict
    ) -> dict[str, Any]:
        """Run complete Layer 4 benchmarking and recommendations.

        Args:
            kg: KnowledgeGraph instance
            completeness_results: Results from Layer 3

        Returns:
            Dictionary with alignment assessment and recommendations
        """
        print("\n[Layer 4] Benchmarking & Recommendations")
        print("-" * 80)

        # 1. Alignment assessment
        print("\nAssessing strategy-to-action alignment...")
        alignment_assessment = self.assess_alignment(kg, completeness_results)
        print(f"✓ Assessed {len(alignment_assessment)} alignment dimensions")

        # 2. Generate recommendations
        print("\nGenerating improvement recommendations...")
        recommendations = self.generate_recommendations(kg, completeness_results)
        print(f"✓ Generated {len(recommendations)} recommendations")

        return {
            "alignment_assessment": alignment_assessment,
            "recommendations": recommendations,
        }
