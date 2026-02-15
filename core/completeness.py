"""Layer 3 — Completeness Analysis.

Detects gaps, validates constraints, analyzes goal cascades,
and builds BSC causal chain links.
"""

import json
from typing import Any

from .knowledge_graph import KnowledgeGraph
from .llm_factory import DEFAULT_PROVIDER, LLM_PROVIDERS, create_llm
from .llm_logger import log_llm_call
from .metrics import BSC_CAUSAL_PAIRS


class CompletenessAnalyzer:
    """Analyzes strategic plan completeness using SPARQL and LLM."""

    def __init__(self, api_key: str, model: str | None = None, provider: str = DEFAULT_PROVIDER):
        """Initialize completeness analyzer.

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
            temperature=0.0,
        )

    def detect_orphan_objectives(self, kg: KnowledgeGraph) -> list[str]:
        """Detect objectives with no supporting tasks.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            List of orphan objective IDs
        """
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?obj WHERE {
            ?obj rdf:type bita:Objective .
            FILTER NOT EXISTS {
                ?tg bita:supportsObjective ?obj .
            }
        }
        """
        results = kg.query_sparql(query)
        orphans = [str(row["obj"]).split("#")[-1] for row in results]
        return orphans

    def detect_orphan_tasks(self, kg: KnowledgeGraph) -> list[str]:
        """Detect task groups with no strategic alignment.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            List of orphan task group IDs
        """
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?tg WHERE {
            ?tg rdf:type bita:TaskGroup .
            FILTER NOT EXISTS {
                ?tg bita:supportsObjective ?obj .
            }
        }
        """
        results = kg.query_sparql(query)
        orphans = [str(row["tg"]).split("#")[-1] for row in results]
        return orphans

    def verify_bsc_chain(self, kg: KnowledgeGraph) -> dict[str, Any]:
        """Verify BSC causal chain coverage across objectives.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            Dictionary with perspective coverage and gaps
        """
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?obj ?perspective ?label WHERE {
            ?obj rdf:type bita:Goal .
            ?obj bita:bscPerspective ?perspective .
            ?perspective rdfs:label ?label .
        }
        """
        results = kg.query_sparql(query)

        perspective_counts = {
            "Financial": 0,
            "Customer": 0,
            "Internal Process": 0,
            "Learning & Growth": 0,
        }

        for row in results:
            label = str(row["label"])
            if label in perspective_counts:
                perspective_counts[label] += 1

        # Check for missing perspectives
        missing = [p for p, count in perspective_counts.items() if count == 0]

        return {
            "coverage": perspective_counts,
            "missing_perspectives": missing,
            "balanced": len(missing) == 0,
        }

    def analyze_goal_cascade(
        self, objective_props: dict, task_group_props: dict
    ) -> dict[str, Any]:
        """Analyze goal cascade strength between goaland task group.

        Args:
            objective_props: Strategic goalproperties
            task_group_props: Task group properties

        Returns:
            Dictionary with cascade category and reasoning
        """
        prompt = f"""Analyze the goal cascade between a strategic goaland task group.

Strategic Objective:
- Name: {objective_props.get('objectiveName', 'N/A')}
- Description: {objective_props.get('objectiveDescription', 'N/A')}

Task Group:
- Name: {task_group_props.get('groupName', 'N/A')}
- Intended Purpose: {task_group_props.get('intendedPurpose', 'N/A')}

Evaluate how well the task group's goals cascade from the strategic objective:

1. goal_cascade: How clearly do the task group's goals flow from the strategic objective?
   - "strong": Clear, direct cascade with explicit connection
   - "moderate": Reasonable cascade but some ambiguity
   - "weak": Indirect or unclear cascade
   - "none": No cascading relationship

2. reasoning: Brief (1-2 sentences) explanation

Return ONLY valid JSON with these two fields, no other text.

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(caller="CompletenessAnalyzer.analyze_goal_cascade", prompt=prompt, response=content, layer=3)

        # Parse JSON
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
            import json

            result = json.loads(content)
            if "goal_cascade" not in result:
                result["goal_cascade"] = "moderate"
            if "reasoning" not in result:
                result["reasoning"] = "No reasoning provided"

            # Validate enum
            valid_cascade = ["strong", "moderate", "weak", "none"]
            if result["goal_cascade"] not in valid_cascade:
                result["goal_cascade"] = "moderate"

            return result

        except json.JSONDecodeError as e:
            log_llm_call(caller="CompletenessAnalyzer.analyze_goal_cascade", prompt=prompt, response=content, error=str(e), layer=3)
            return {"goal_cascade": "moderate", "reasoning": "Failed to parse LLM output"}

    def analyze_resource_sufficiency(
        self, objective_props: dict, task_group_props: dict
    ) -> dict[str, Any]:
        """Analyze resource sufficiency for achieving goalvia task group.

        Args:
            objective_props: Strategic goalproperties
            task_group_props: Task group properties

        Returns:
            Dictionary with sufficiency category and reasoning
        """
        prompt = f"""Analyze resource sufficiency for achieving a strategic goalthrough a task group.

Strategic Objective:
- Name: {objective_props.get('objectiveName', 'N/A')}
- Importance: {objective_props.get('strategicImportance', 'N/A')}

Task Group:
- Name: {task_group_props.get('groupName', 'N/A')}
- Resource Allocation: {task_group_props.get('resourceAllocation', 'N/A')}

Evaluate whether the resource allocation is sufficient for the objective's importance:

1. resource_sufficiency: Is the resource allocation appropriate?
   - "fully_sufficient": Resources exceed what's needed
   - "adequate": Resources match the requirement
   - "insufficient": Resources fall short
   - "severely_lacking": Critical resource gap

2. reasoning: Brief (1-2 sentences) explanation

Return ONLY valid JSON with these two fields, no other text.

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(caller="CompletenessAnalyzer.analyze_resource_sufficiency", prompt=prompt, response=content, layer=3)

        # Parse JSON
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
            import json

            result = json.loads(content)
            if "resource_sufficiency" not in result:
                result["resource_sufficiency"] = "adequate"
            if "reasoning" not in result:
                result["reasoning"] = "No reasoning provided"

            # Validate enum
            valid_sufficiency = [
                "fully_sufficient",
                "adequate",
                "insufficient",
                "severely_lacking",
            ]
            if result["resource_sufficiency"] not in valid_sufficiency:
                result["resource_sufficiency"] = "adequate"

            return result

        except json.JSONDecodeError as e:
            log_llm_call(caller="CompletenessAnalyzer.analyze_resource_sufficiency", prompt=prompt, response=content, error=str(e), layer=3)
            return {
                "resource_sufficiency": "adequate",
                "reasoning": "Failed to parse LLM output",
            }

    def analyze_execution_gap(self, kg: KnowledgeGraph) -> dict[str, Any]:
        """Analyze execution gap by comparing strategic importance vs resource allocation.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            Dictionary with gap severity and affected objectives
        """
        # Get all alignments (objective ↔ task group)
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>

        SELECT ?tg ?obj WHERE {
            ?tg bita:supportsObjective ?obj .
        }
        """
        results = kg.query_sparql(query)

        gaps = []
        for row in results:
            obj_id = str(row["obj"]).split("#")[-1]
            tg_id = str(row["tg"]).split("#")[-1]

            tg_props = kg.get_entity_properties(tg_id)

            # Look up parent goal for strategicImportance
            parent_query = f"""
            PREFIX bita: <http://bita-system.org/ontology#>
            SELECT ?goal WHERE {{ ?goal bita:hasObjective bita:{obj_id} . }}
            """
            parent_rows = kg.query_sparql(parent_query)
            if parent_rows:
                goal_id = str(parent_rows[0]["goal"]).split("#")[-1]
                goal_props = kg.get_entity_properties(goal_id)
                importance = goal_props.get("strategicImportance", "moderate")
            else:
                goal_id = ""
                importance = "moderate"

            allocation = tg_props.get("resourceAllocation", "moderate")

            # Map to numeric scores for comparison
            importance_map = {
                "critical": 100,
                "high": 75,
                "moderate": 50,
                "low": 25,
                "negligible": 0,
            }
            allocation_map = {"heavy": 100, "moderate": 70, "light": 40, "minimal": 10}

            importance_score = importance_map.get(importance, 50)
            allocation_score = allocation_map.get(allocation, 70)

            # Calculate gap
            gap = importance_score - allocation_score

            if gap > 40:
                severity = "critical"
            elif gap > 20:
                severity = "high"
            elif gap > 0:
                severity = "moderate"
            else:
                severity = "low"

            if gap > 0:
                gaps.append(
                    {
                        "objective_id": obj_id,
                        "goal_id": goal_id,
                        "task_group_id": tg_id,
                        "importance": importance,
                        "allocation": allocation,
                        "gap_score": gap,
                        "severity": severity,
                    }
                )

        # Overall gap assessment
        if not gaps:
            overall_severity = "low"
        else:
            severity_scores = {
                "critical": 100,
                "high": 70,
                "moderate": 40,
                "low": 10,
            }
            avg_severity = sum(severity_scores[g["severity"]] for g in gaps) / len(gaps)

            if avg_severity >= 70:
                overall_severity = "critical"
            elif avg_severity >= 40:
                overall_severity = "high"
            elif avg_severity >= 20:
                overall_severity = "moderate"
            else:
                overall_severity = "low"

        return {
            "overall_severity": overall_severity,
            "gaps": gaps,
            "total_gaps": len(gaps),
        }

    def build_causal_links(self, kg: KnowledgeGraph) -> list[dict[str, Any]]:
        """Identify causal links between objectives in adjacent BSC perspectives.

        For each pair of adjacent BSC perspectives (L&G->IP, IP->C, C->F),
        asks the LLM whether achieving an objective in the source perspective
        causally enables an objective in the target perspective.

        Writes supportsCausalChain edges and causalLink_* properties to KG.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            List of identified causal link dicts with source_id, target_id,
            strength, and reasoning.
        """
        from rdflib import Literal
        from rdflib.namespace import XSD

        # Get goals grouped by BSC perspective
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?goal ?perspective_label WHERE {
            ?goal rdf:type bita:Goal .
            ?goal bita:bscPerspective ?perspective .
            ?perspective rdfs:label ?perspective_label .
        }
        """
        results = kg.query_sparql(query)

        goals_by_perspective: dict[str, list[dict]] = {}
        for row in results:
            label = str(row["perspective_label"])
            goal_uri = str(row["goal"])
            goal_id = goal_uri.split("#")[-1]
            goal_props = kg.get_entity_properties(goal_id)

            if label not in goals_by_perspective:
                goals_by_perspective[label] = []
            goals_by_perspective[label].append({
                "id": goal_id,
                "name": goal_props.get("label", goal_props.get("goalName", goal_id)),
                "description": goal_props.get("description", goal_props.get("goalDescription", "")),
            })

        identified_links: list[dict[str, Any]] = []

        for source_perspective, target_perspective in BSC_CAUSAL_PAIRS:
            source_goals = goals_by_perspective.get(source_perspective, [])
            target_goals = goals_by_perspective.get(target_perspective, [])

            for src in source_goals:
                for tgt in target_goals:
                    prompt = f"""Analyze whether achieving one strategic objective causally enables another.

Source Objective (BSC Perspective: {source_perspective}):
- ID: {src['id']}
- Name: {src['name']}
- Description: {src['description']}

Target Objective (BSC Perspective: {target_perspective}):
- ID: {tgt['id']}
- Name: {tgt['name']}
- Description: {tgt['description']}

Does achieving the source objective causally enable or support achieving the target objective?

Classify the causal link strength:
- "strong": Clear, direct causal relationship — achieving source directly enables target
- "moderate": Indirect but meaningful causal contribution
- "weak": Marginal or conditional causal relationship
- "none": No meaningful causal relationship

Return ONLY valid JSON with these fields:
- "strength": one of "strong", "moderate", "weak", "none"
- "reasoning": Brief (1-2 sentences) explanation

JSON OUTPUT:"""

                    response = self.llm.invoke(prompt)
                    content = response.content.strip()

                    log_llm_call(
                        caller="CompletenessAnalyzer.build_causal_links",
                        prompt=prompt,
                        response=content,
                        layer=3,
                    )

                    # Parse JSON response
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
                            caller="CompletenessAnalyzer.build_causal_links",
                            prompt=prompt,
                            response=content,
                            error=str(e),
                            layer=3,
                        )
                        result = {"strength": "none", "reasoning": "Failed to parse LLM output"}

                    strength = result.get("strength", "none")
                    reasoning = result.get("reasoning", "")

                    valid_strengths = ["strong", "moderate", "weak", "none"]
                    if strength not in valid_strengths:
                        strength = "none"

                    if strength == "none":
                        continue

                    # Write causal link properties to KG on the source goal
                    src_uri = kg.bita[src["id"]]
                    kg.graph.add((
                        src_uri,
                        kg.bita[f"causalLink_{tgt['id']}_strength"],
                        Literal(strength, datatype=XSD.string),
                    ))
                    kg.graph.add((
                        src_uri,
                        kg.bita[f"causalLink_{tgt['id']}_reasoning"],
                        Literal(reasoning, datatype=XSD.string),
                    ))

                    # Add supportsCausalChain relationship edge
                    kg.add_relationship(src["id"], "supportsCausalChain", tgt["id"])

                    identified_links.append({
                        "source_id": src["id"],
                        "source_name": src["name"],
                        "source_perspective": source_perspective,
                        "target_id": tgt["id"],
                        "target_name": tgt["name"],
                        "target_perspective": target_perspective,
                        "strength": strength,
                        "reasoning": reasoning,
                    })

        return identified_links

    def analyze_completeness(self, kg: KnowledgeGraph) -> dict[str, Any]:
        """Run complete Layer 3 analysis.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            Dictionary with all completeness metrics and gaps
        """
        print("\n[Layer 3] Completeness Analysis")
        print("-" * 80)

        # 1. Orphan detection
        print("Detecting orphan objectives and tasks...")
        orphan_objectives = self.detect_orphan_objectives(kg)
        orphan_tasks = self.detect_orphan_tasks(kg)
        print(f"✓ Found {len(orphan_objectives)} orphan objectives")
        print(f"✓ Found {len(orphan_tasks)} orphan task groups")

        # 2. BSC chain verification
        print("\nVerifying BSC causal chain...")
        bsc_analysis = self.verify_bsc_chain(kg)
        print(
            f"✓ BSC Coverage: {bsc_analysis['coverage']}"
        )
        if bsc_analysis["missing_perspectives"]:
            print(f"  ⚠️  Missing: {', '.join(bsc_analysis['missing_perspectives'])}")

        # 2b. Build causal links between BSC perspective objectives
        print("\nBuilding BSC causal chain links...")
        causal_links = self.build_causal_links(kg)
        print(f"✓ Identified {len(causal_links)} causal links across BSC perspectives")

        # 3. Goal cascade analysis for aligned pairs
        print("\nAnalyzing goal cascades and resource sufficiency...")
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>

        SELECT ?tg ?obj WHERE {
            ?tg bita:supportsGoal ?obj .
        }
        """
        results = kg.query_sparql(query)

        for row in results:
            obj_id = str(row["obj"]).split("#")[-1]
            tg_id = str(row["tg"]).split("#")[-1]

            obj_props = kg.get_entity_properties(obj_id)
            tg_props = kg.get_entity_properties(tg_id)

            # Analyze cascade
            cascade_result = self.analyze_goal_cascade(obj_props, tg_props)

            # Analyze sufficiency
            sufficiency_result = self.analyze_resource_sufficiency(obj_props, tg_props)

            # Write to KG
            from rdflib import Literal
            from rdflib.namespace import XSD

            tg_uri = kg.bita[tg_id]
            kg.graph.add(
                (
                    tg_uri,
                    kg.bita[f"cascade_{obj_id}_strength"],
                    Literal(cascade_result["goal_cascade"], datatype=XSD.string),
                )
            )
            kg.graph.add(
                (
                    tg_uri,
                    kg.bita[f"cascade_{obj_id}_reasoning"],
                    Literal(cascade_result["reasoning"], datatype=XSD.string),
                )
            )
            kg.graph.add(
                (
                    tg_uri,
                    kg.bita[f"sufficiency_{obj_id}_level"],
                    Literal(sufficiency_result["resource_sufficiency"], datatype=XSD.string),
                )
            )
            kg.graph.add(
                (
                    tg_uri,
                    kg.bita[f"sufficiency_{obj_id}_reasoning"],
                    Literal(sufficiency_result["reasoning"], datatype=XSD.string),
                )
            )

        print(f"✓ Analyzed {len(results)} alignment pairs")

        # 4. Execution gap analysis
        print("\nAnalyzing execution gaps...")
        gap_analysis = self.analyze_execution_gap(kg)
        print(
            f"✓ Overall gap severity: {gap_analysis['overall_severity']} ({gap_analysis['total_gaps']} gaps)"
        )

        return {
            "orphan_objectives": orphan_objectives,
            "orphan_tasks": orphan_tasks,
            "bsc_analysis": bsc_analysis,
            "causal_links": causal_links,
            "gap_analysis": gap_analysis,
        }
