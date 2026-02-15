"""Layer 2 — LLM-as-Judge Alignment Scoring.

Evaluates alignment between strategic goals and action plan tasks.
"""

import json
from typing import Any

from .knowledge_graph import KnowledgeGraph
from .llm_factory import DEFAULT_PROVIDER, LLM_PROVIDERS, create_llm
from .llm_logger import log_llm_call


class AlignmentScorer:
    """Evaluates strategic-action alignment using LLM as judge."""

    def __init__(self, api_key: str, model: str | None = None, provider: str = DEFAULT_PROVIDER):
        """Initialize alignment scorer.

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
            temperature=0.0,  # Deterministic for scoring
        )

    def get_strategy_action_pairs(
        self, kg: KnowledgeGraph
    ) -> list[tuple[str, dict, str, dict, dict, list[dict]]]:
        """Extract all objective and task group pairs from KG with full context.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            List of tuples: (objective_id, objective_props, task_group_id,
                             task_group_props, parent_goal_props, child_tasks)
        """
        # Query all objectives with their parent goal
        objective_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?objective ?goal WHERE {
            ?objective rdf:type bita:Objective .
            ?goal bita:hasObjective ?objective .
        }
        """
        objective_results = kg.query_sparql(objective_query)

        # Query all task groups with their child tasks
        task_group_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?tg WHERE {
            ?tg rdf:type bita:TaskGroup .
        }
        """
        tg_results = kg.query_sparql(task_group_query)

        # Pre-fetch child tasks for each task group
        task_query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?tg ?task WHERE {
            ?tg bita:hasTask ?task .
            ?task rdf:type bita:Task .
        }
        """
        task_results = kg.query_sparql(task_query)

        # Build task group -> child tasks mapping
        tg_tasks: dict[str, list[dict]] = {}
        for row in task_results:
            tg_id = str(row["tg"]).split("#")[-1]
            task_id = str(row["task"]).split("#")[-1]
            task_props = kg.get_entity_properties(task_id)
            tg_tasks.setdefault(tg_id, []).append(task_props)

        pairs = []
        for obj_row in objective_results:
            obj_uri = str(obj_row["objective"])
            obj_id = obj_uri.split("#")[-1]
            obj_props = kg.get_entity_properties(obj_id)

            # Get parent goal context
            goal_uri = str(obj_row["goal"])
            goal_id = goal_uri.split("#")[-1]
            goal_props = kg.get_entity_properties(goal_id)

            for tg_row in tg_results:
                tg_uri = str(tg_row["tg"])
                tg_id = tg_uri.split("#")[-1]
                tg_props = kg.get_entity_properties(tg_id)
                child_tasks = tg_tasks.get(tg_id, [])

                pairs.append((obj_id, obj_props, tg_id, tg_props, goal_props, child_tasks))

        return pairs

    def evaluate_alignment(
        self,
        objective_props: dict,
        task_group_props: dict,
        parent_goal_props: dict | None = None,
        child_tasks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Evaluate alignment between a strategic objective and task group.

        Args:
            objective_props: Properties of the strategic objective
            task_group_props: Properties of the task group
            parent_goal_props: Properties of the parent strategic goal (optional)
            child_tasks: List of child task property dicts (optional)

        Returns:
            Dictionary with:
            - relevance: One of: none, indirect, partial, direct
            - contribution_strength: One of: primary, supporting, tangential
            - reasoning: Explanation for the classification
        """
        # Build parent goal context
        goal_context = ""
        if parent_goal_props:
            goal_context = f"""
Parent Strategic Goal:
- Name: {parent_goal_props.get('label', 'N/A')}
- Description: {parent_goal_props.get('description', 'N/A')}
- Importance: {parent_goal_props.get('strategicImportance', 'N/A')}
- Reasoning: {parent_goal_props.get('importanceReasoning', 'N/A')}
"""

        # Build child tasks context
        tasks_context = ""
        if child_tasks:
            task_lines = []
            for t in child_tasks:
                line = f"  - {t.get('label', 'N/A')}: {t.get('description', 'N/A')}"
                outcome = t.get('measurableOutcome', '')
                if outcome:
                    line += f" (Outcome: {outcome})"
                task_lines.append(line)
            tasks_context = f"""
Individual Tasks:
{chr(10).join(task_lines)}
"""

        prompt = f"""You are evaluating the alignment between a strategic objective and an action plan task group.
{goal_context}
Strategic Objective (specific, measurable target):
- Name: {objective_props.get('label', 'N/A')}
- Description: {objective_props.get('description', 'N/A')}

Task Group:
- Name: {task_group_props.get('label', 'N/A')}
- Intended Purpose: {task_group_props.get('intendedPurpose', 'N/A')}
- Resource Allocation: {task_group_props.get('resourceAllocation', 'N/A')}
- Allocation Reasoning: {task_group_props.get('allocationReasoning', 'N/A')}
{tasks_context}
Evaluate the alignment and provide:
1. relevance: How relevant is this task group to achieving the strategic objective?
   - "none": No connection
   - "indirect": Tangentially related
   - "partial": Contributes but not primary focus
   - "direct": Directly advances the objective

2. contribution_strength: What is the strength of this task group's contribution?
   - "tangential": Peripheral support
   - "supporting": Important supporting role
   - "primary": Core driver of objective success

3. reasoning: Brief (1-2 sentences) explanation for your classification

Return ONLY valid JSON with these three fields, no other text.

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(caller="AlignmentScorer.evaluate_alignment", prompt=prompt, response=content, layer=2)

        # Parse JSON, handling code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json or (not line.strip().startswith("```")):
                    json_lines.append(line)
            content = "\n".join(json_lines)

        try:
            result = json.loads(content)
            # Validate required fields
            if "relevance" not in result:
                result["relevance"] = "none"
            if "contribution_strength" not in result:
                result["contribution_strength"] = "tangential"
            if "reasoning" not in result:
                result["reasoning"] = "No reasoning provided"

            # Validate enum values
            valid_relevance = ["none", "indirect", "partial", "direct"]
            valid_strength = ["tangential", "supporting", "primary"]

            if result["relevance"] not in valid_relevance:
                print(f"Invalid relevance: {result['relevance']}, defaulting to 'none'")
                result["relevance"] = "none"

            if result["contribution_strength"] not in valid_strength:
                print(
                    f"Invalid contribution_strength: {result['contribution_strength']}, defaulting to 'tangential'"
                )
                result["contribution_strength"] = "tangential"

            return result

        except json.JSONDecodeError as e:
            log_llm_call(caller="AlignmentScorer.evaluate_alignment", prompt=prompt, response=content, error=str(e), layer=2)
            print(f"Failed to parse LLM alignment output as JSON: {e}")
            print(f"Output was: {content[:500]}")
            return {
                "relevance": "none",
                "contribution_strength": "tangential",
                "reasoning": "Failed to parse LLM output",
            }

    def score_all_alignments(self, kg: KnowledgeGraph):
        """Evaluate all objective to task group alignments.

        Args:
            kg: KnowledgeGraph instance

        Writes alignment relationships to KG with properties:
        - relevance (categorical)
        - contributionStrength (categorical)
        - alignmentReasoning (text)
        """
        pairs = self.get_strategy_action_pairs(kg)
        total_pairs = len(pairs)

        print(f"\nEvaluating {total_pairs} objective-action alignment pairs...")

        for idx, (obj_id, obj_props, tg_id, tg_props, goal_props, child_tasks) in enumerate(pairs, 1):
            print(
                f"[{idx}/{total_pairs}] Evaluating {obj_id} <-> {tg_id}...", end=" "
            )

            # Evaluate alignment with full context
            alignment_result = self.evaluate_alignment(
                obj_props, tg_props, goal_props, child_tasks
            )

            # Only write edge if there's meaningful alignment
            if alignment_result["relevance"] != "none":
                # Create alignment edge with properties
                kg.add_relationship(tg_id, "supportsObjective", obj_id)

                # Add alignment properties as separate triples
                # (In a more sophisticated design, we'd use RDF reification or named graphs,
                # but for simplicity we'll add properties directly to the task group)
                alignment_props = {
                    f"alignment_{obj_id}_relevance": alignment_result["relevance"],
                    f"alignment_{obj_id}_strength": alignment_result[
                        "contribution_strength"
                    ],
                    f"alignment_{obj_id}_reasoning": alignment_result["reasoning"],
                }

                # Update task group entity with alignment properties
                tg_uri = kg.bita[tg_id]
                for prop_name, prop_value in alignment_props.items():
                    predicate = kg.bita[prop_name]
                    from rdflib import Literal
                    from rdflib.namespace import XSD

                    kg.graph.add((tg_uri, predicate, Literal(prop_value, datatype=XSD.string)))

                print(
                    f"✓ {alignment_result['relevance']} ({alignment_result['contribution_strength']})"
                )
            else:
                print("✗ no alignment")

        print("\nAlignment evaluation complete!")
