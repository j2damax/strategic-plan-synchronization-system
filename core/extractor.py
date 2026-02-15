"""Layer 1 — Structured Extraction using LLM.

Extracts structured data from strategic and action plans.
"""

import json
from typing import Any

from .knowledge_graph import KnowledgeGraph
from .llm_factory import DEFAULT_PROVIDER, LLM_PROVIDERS, create_llm
from .llm_logger import log_llm_call


class StructuredExtractor:
    """Extracts structured data from plan documents using LLM."""

    def __init__(self, api_key: str, model: str | None = None, provider: str = DEFAULT_PROVIDER):
        """Initialize extractor.

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
            temperature=0.0,  # Deterministic for extraction
        )

    def extract_strategic_plan(self, text: str) -> list[dict[str, Any]]:
        """Extract strategic goals from strategic plan text.

        Args:
            text: Strategic plan text

        Returns:
            List of strategic goal dictionaries
        """
        prompt = f"""Extract structured data from the following strategic plan document.

For each strategic goal (high-level direction), extract:
- goal_id: A short alphanumeric identifier (MUST follow format "G1", "G2", "G3", etc.)
- goal_name: Short name of the goal
- description: Detailed description
- objectives: List of objects, each with:
  - name: Short name of the objective
  - description: Detailed description of what the objective entails and how success is measured
- kpis: List of KPIs with name, baseline_exists (bool), owner (string or null), type (leading/lagging), measurable (bool)
- bsc_perspective: One of: financial, customer, internal_process, learning_growth
- strategic_importance: One of: critical, high, moderate, low, negligible
- importance_reasoning: 1-2 sentence explanation for the importance classification
- target_segments: List of markets, verticals, or customer segments
- timeline: Time period as string
- dependencies: List of goal IDs this depends on

Return ONLY valid JSON array of goals, no other text.

Strategic Plan Text:
{text}

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(caller="StructuredExtractor.extract_strategic_plan", prompt=prompt, response=content, layer=1)

        # Try to parse JSON, handling code blocks
        if content.startswith("```"):
            # Extract JSON from code block
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
            objectives = json.loads(content)
            return objectives if isinstance(objectives, list) else [objectives]
        except json.JSONDecodeError as e:
            log_llm_call(caller="StructuredExtractor.extract_strategic_plan", prompt=prompt, response=content, error=str(e), layer=1)
            print(f"Failed to parse LLM output as JSON: {e}")
            print(f"Output was: {content[:500]}")
            return []

    def extract_action_plan(self, text: str) -> list[dict[str, Any]]:
        """Extract action task groups from action plan text.

        Args:
            text: Action plan text

        Returns:
            List of task group dictionaries
        """
        prompt = f"""Extract structured data from the following action plan document.

For each task group, extract:
- task_group_id: A short alphanumeric identifier (MUST follow format "A1_1", "A2_1", "A1_2", etc.)
- task_group_name: Short name of the task group
- phase: Which phase this belongs to (e.g., "Phase 1: Core Development")
- resource_allocation: One of: heavy, moderate, light, minimal
- allocation_reasoning: 1-2 sentence explanation for the allocation classification
- tasks: List of ALL individual tasks (extract every task mentioned, do not summarize or group) with:
  - name: Short name of the task
  - description: Detailed description of what the task involves and its expected deliverables
  - assignee: Person or team (string or null)
  - deadline: Deadline as string
  - status: One of: pending, in_progress, completed
  - measurable_outcome: What defines success
  - has_business_justification: boolean
- intended_strategic_purpose: Brief description of which strategic goal this serves

Return ONLY valid JSON array of task groups, no other text.

Action Plan Text:
{text}

JSON OUTPUT:"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        log_llm_call(caller="StructuredExtractor.extract_action_plan", prompt=prompt, response=content, layer=1)

        # Try to parse JSON, handling code blocks
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
            task_groups = json.loads(content)
            return task_groups if isinstance(task_groups, list) else [task_groups]
        except json.JSONDecodeError as e:
            log_llm_call(caller="StructuredExtractor.extract_action_plan", prompt=prompt, response=content, error=str(e), layer=1)
            print(f"Failed to parse LLM output as JSON: {e}")
            print(f"Output was: {content[:500]}")
            return []

    def write_to_knowledge_graph(
        self,
        kg: KnowledgeGraph,
        strategic_goals: list[dict],
        task_groups: list[dict],
    ):
        """Write extracted data to the Knowledge Graph.

        Args:
            kg: KnowledgeGraph instance
            strategic_goals: List of strategic goals from extract_strategic_plan
            task_groups: List of task groups from extract_action_plan
        """
        # Create organization
        kg.add_entity("Organization", "Organization", {"label": "Organization"})

        # Create plan
        plan_id = "StrategicPlan_2026"
        kg.add_entity(plan_id, "Plan", {"label": "Strategic Plan"})
        kg.add_relationship(plan_id, "belongsTo", "Organization")

        # Add strategic goals (high-level)
        for goal_data in strategic_goals:
            goal_id = goal_data["goal_id"]

            # Create goal entity
            goal_props = {
                "label": goal_data["goal_name"],  # RDF standard
                "description": goal_data.get("description", ""),
                "strategicImportance": goal_data.get("strategic_importance", "moderate"),
                "importanceReasoning": goal_data.get("importance_reasoning", ""),
                "timeline": goal_data.get("timeline", ""),
            }
            kg.add_entity(goal_id, "Goal", goal_props)
            kg.add_relationship(plan_id, "hasGoal", goal_id)

            # Map BSC perspective
            bsc_mapping = {
                "financial": "BSC_Financial",
                "customer": "BSC_Customer",
                "internal_process": "BSC_InternalProcess",
                "learning_growth": "BSC_LearningGrowth",
            }
            bsc_perspective = goal_data.get("bsc_perspective", "internal_process")
            if bsc_perspective in bsc_mapping:
                kg.add_relationship(goal_id, "bscPerspective", bsc_mapping[bsc_perspective])

            # Add objectives (specific, measurable targets under the goal)
            for i, objective_data in enumerate(goal_data.get("objectives", [])):
                objective_id = f"{goal_id}_O{i+1}"
                obj_props = {
                    "label": objective_data["name"],
                    "description": objective_data.get("description", ""),
                }
                kg.add_entity(objective_id, "Objective", obj_props)
                kg.add_relationship(goal_id, "hasObjective", objective_id)

            # Add KPIs
            for i, kpi_data in enumerate(goal_data.get("kpis", [])):
                kpi_id = f"{goal_id}_KPI{i+1}"
                kpi_props = {
                    "label": kpi_data.get("name", ""),  # RDF standard
                    "kpiType": kpi_data.get("type", "lagging"),
                    "baselineExists": kpi_data.get("baseline_exists", False),
                    "measurable": kpi_data.get("measurable", True),
                }
                if kpi_data.get("owner"):
                    kpi_props["owner"] = kpi_data["owner"]

                kg.add_entity(kpi_id, "KPI", kpi_props)
                kg.add_relationship(goal_id, "hasKPI", kpi_id)

        # Group task groups by phase
        phases = {}
        for tg_data in task_groups:
            phase_name = tg_data.get("phase", "Phase 1")
            if phase_name not in phases:
                phases[phase_name] = []
            phases[phase_name].append(tg_data)

        # Add phases and task groups
        for phase_idx, (phase_name, tg_list) in enumerate(phases.items(), 1):
            phase_id = f"P{phase_idx}"
            kg.add_entity(
                phase_id,
                "ActionPhase",
                {"label": phase_name, "phaseOrder": phase_idx},  # RDF standard
            )
            kg.add_relationship(plan_id, "hasPhase", phase_id)

            # Add task groups in this phase
            for tg_data in tg_list:
                tg_id = tg_data["task_group_id"]
                print(f"[DEBUG] task_group_id from LLM: '{tg_id}'")
                tg_props = {
                    "label": tg_data["task_group_name"],  # RDF standard
                    "resourceAllocation": tg_data.get("resource_allocation", "moderate"),
                    "allocationReasoning": tg_data.get("allocation_reasoning", ""),
                    "intendedPurpose": tg_data.get("intended_strategic_purpose", ""),
                }
                kg.add_entity(tg_id, "TaskGroup", tg_props)
                kg.add_relationship(phase_id, "containsGroup", tg_id)

                # Add individual tasks
                for task_idx, task_data in enumerate(tg_data.get("tasks", []), 1):
                    task_id = f"{tg_id}_T{task_idx}"
                    task_props = {
                        "label": task_data["name"],
                        "description": task_data.get("description", ""),
                        "deadline": task_data.get("deadline", ""),
                        "status": task_data.get("status", "pending"),
                        "measurableOutcome": task_data.get("measurable_outcome", ""),
                        "hasBusinessJustification": task_data.get(
                            "has_business_justification", True
                        ),
                    }
                    if task_data.get("assignee"):
                        task_props["assignee"] = task_data["assignee"]

                    kg.add_entity(task_id, "Task", task_props)
                    kg.add_relationship(tg_id, "hasTask", task_id)
