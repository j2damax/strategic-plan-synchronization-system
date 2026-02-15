"""Score computation from categorical labels.

Maps LLM categorical outputs to numeric scores for all composite metrics.
"""

from typing import Any

from .knowledge_graph import KnowledgeGraph

# Mapping tables (defined in PROJECT_PLAN.md Section 2)
IMPORTANCE_MAP = {
    "critical": 100,
    "high": 75,
    "moderate": 50,
    "low": 25,
    "negligible": 0,
}

ALLOCATION_MAP = {
    "heavy": 100,
    "moderate": 70,
    "light": 40,
    "minimal": 10,
}

RELEVANCE_MAP = {
    "direct": 100,
    "partial": 60,
    "indirect": 30,
    "none": 0,
}

EGI_MAP = {
    "critical": 100,
    "high": 70,
    "moderate": 40,
    "low": 10,
}

CASCADE_MAP = {
    "strong": 100,
    "moderate": 60,
    "weak": 30,
    "none": 0,
}

SUFFICIENCY_MAP = {
    "fully_sufficient": 100,
    "adequate": 70,
    "insufficient": 40,
    "severely_lacking": 10,
}

CAUSAL_STRENGTH_MAP = {
    "strong": 1.0,
    "moderate": 0.5,
    "weak": 0.2,
}

RANGE_WIDTH = 30  # Gap between score levels

# BSC perspective adjacency for causal chain analysis
# Each tuple is (source_perspective, target_perspective)
BSC_CAUSAL_PAIRS = [
    ("Learning & Growth", "Internal Process"),
    ("Internal Process", "Customer"),
    ("Customer", "Financial"),
]

# Map perspective labels to BSC entity IDs
BSC_PERSPECTIVE_IDS = {
    "Financial": "BSC_Financial",
    "Customer": "BSC_Customer",
    "Internal Process": "BSC_InternalProcess",
    "Learning & Growth": "BSC_LearningGrowth",
}


def compute_alignment_score(relevance: str) -> float:
    """Compute alignment score from relevance category.

    Args:
        relevance: One of: none, indirect, partial, direct

    Returns:
        Numeric score 0-100
    """
    base_score = RELEVANCE_MAP.get(relevance, 0)

    # Apply randomization within ±RANGE_WIDTH/2 if needed
    # For now, return base score (deterministic)
    return float(base_score)


def compute_priority_score(
    importance: str, allocation: str, risk_exposure: float = 0.5
) -> float:
    """Compute weighted priority score.

    Formula: 0.50 × importance + 0.30 × allocation + 0.20 × risk
    (Updated in CHANGELOG: removed customer_value, rebalanced weights)

    Args:
        importance: Strategic importance category (critical/high/moderate/low/negligible)
        allocation: Resource allocation category (heavy/moderate/light/minimal)
        risk_exposure: Risk exposure score 0-100 (default: 50)

    Returns:
        Weighted priority score 0-100
    """
    importance_score = IMPORTANCE_MAP.get(importance, 50)
    allocation_score = ALLOCATION_MAP.get(allocation, 70)

    priority = (
        0.50 * importance_score + 0.30 * allocation_score + 0.20 * risk_exposure
    )

    return priority


def compute_kpi_utility(
    baseline_exists: bool, measurable: bool, owner_assigned: bool
) -> float:
    """Compute KPI utility score.

    Formula: (baseline_weight × baseline_exists) +
             (measurable_weight × measurable) +
             (ownership_weight × owner_assigned)

    Weights: 0.4, 0.4, 0.2 respectively

    Args:
        baseline_exists: Whether KPI has baseline data
        measurable: Whether KPI is measurable
        owner_assigned: Whether KPI has an assigned owner

    Returns:
        KPI utility score 0-100
    """
    baseline_score = 100.0 if baseline_exists else 0.0
    measurable_score = 100.0 if measurable else 0.0
    owner_score = 100.0 if owner_assigned else 0.0

    utility = (
        0.4 * baseline_score + 0.4 * measurable_score + 0.2 * owner_score
    )

    return utility


def compute_catchball(goal_cascade: str, resource_sufficiency: str) -> float:
    """Compute catchball consistency score.

    Formula: mapped(goal_cascade) × mapped(resource_sufficiency) / 100
    (Fixed in CHANGELOG: removed incorrect mean() wrapper)

    Args:
        goal_cascade: Goal cascade category (strong/moderate/weak/none)
        resource_sufficiency: Resource sufficiency category
                             (fully_sufficient/adequate/insufficient/severely_lacking)

    Returns:
        Catchball score 0-100
    """
    cascade_score = CASCADE_MAP.get(goal_cascade, 0)
    sufficiency_score = SUFFICIENCY_MAP.get(resource_sufficiency, 70)

    # Product, normalized to 0-100 scale
    catchball = (cascade_score * sufficiency_score) / 100.0

    return catchball


def compute_coverage(objectives_count: int, supported_count: int) -> float:
    """Compute coverage percentage.

    Formula: (supported_objectives / total_objectives) × 100

    Args:
        objectives_count: Total number of strategic objectives
        supported_count: Number of objectives with at least one supporting task

    Returns:
        Coverage percentage 0-100
    """
    if objectives_count == 0:
        return 0.0

    coverage = (supported_count / objectives_count) * 100.0
    return coverage


def compute_egi(execution_gap: str) -> float:
    """Compute Execution Gap Index.

    Args:
        execution_gap: Gap severity category (critical/high/moderate/low)

    Returns:
        EGI score 0-100 (higher = worse gap)
    """
    return float(EGI_MAP.get(execution_gap, 40))


def compute_sai(kg: KnowledgeGraph) -> float:
    """Compute Strategic Alignment Index (aggregate across all pairs).

    Formula: Average of all non-zero alignment scores

    Args:
        kg: KnowledgeGraph instance

    Returns:
        SAI score 0-100
    """
    # Query all task groups
    task_group_query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?tg WHERE {
        ?tg rdf:type bita:TaskGroup .
    }
    """
    tg_results = kg.query_sparql(task_group_query)

    alignment_scores = []

    for tg_row in tg_results:
        tg_uri = str(tg_row["tg"])
        tg_id = tg_uri.split("#")[-1]
        tg_props = kg.get_entity_properties(tg_id)

        # Find all alignment properties for this task group
        for prop_name, prop_value in tg_props.items():
            if "_relevance" in prop_name:
                relevance = prop_value
                score = compute_alignment_score(relevance)
                if score > 0:
                    alignment_scores.append(score)

    if not alignment_scores:
        return 0.0

    sai = sum(alignment_scores) / len(alignment_scores)
    return sai


def _get_goals_by_perspective(kg: KnowledgeGraph) -> dict[str, list[dict]]:
    """Query KG for all goals grouped by BSC perspective label.

    Returns:
        Dict mapping perspective label to list of
        {"id": str, "name": str, "props": dict}
    """
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

    by_perspective: dict[str, list[dict]] = {}
    for row in results:
        label = str(row["perspective_label"])
        goal_uri = str(row["goal"])
        goal_id = goal_uri.split("#")[-1]
        goal_props = kg.get_entity_properties(goal_id)

        if label not in by_perspective:
            by_perspective[label] = []
        by_perspective[label].append({
            "id": goal_id,
            "name": goal_props.get("label", goal_props.get("goalName", goal_id)),
            "props": goal_props,
        })

    return by_perspective


def compute_causal_linkage_density(kg: KnowledgeGraph) -> dict[str, Any]:
    """Compute Causal Linkage Density across BSC perspective pairs.

    Queries the KG for all supportsCausalChain edges with causalLink_*
    properties, groups by BSC perspective pair, and computes density.

    Args:
        kg: KnowledgeGraph instance

    Returns:
        Dictionary with:
        - cld_score: Overall causal linkage density (0-1)
        - perspective_pair_scores: Per-pair density scores
        - chain_completeness: Which perspective pairs have any links
        - missing_chains: Perspective pairs with no causal links
    """
    goals_by_perspective = _get_goals_by_perspective(kg)

    perspective_pair_scores: dict[str, float] = {}
    chain_completeness: dict[str, bool] = {}
    missing_chains: list[str] = []

    pair_densities = []

    for source_perspective, target_perspective in BSC_CAUSAL_PAIRS:
        pair_label = f"{source_perspective} -> {target_perspective}"
        source_goals = goals_by_perspective.get(source_perspective, [])
        target_goals = goals_by_perspective.get(target_perspective, [])

        max_possible = len(source_goals) * len(target_goals)
        if max_possible == 0:
            chain_completeness[pair_label] = False
            missing_chains.append(pair_label)
            perspective_pair_scores[pair_label] = 0.0
            continue

        # Sum up causal link strengths for this perspective pair
        total_strength = 0.0
        link_count = 0

        for src in source_goals:
            src_props = src["props"]
            for tgt in target_goals:
                strength_key = f"causalLink_{tgt['id']}_strength"
                strength_val = src_props.get(strength_key)
                if strength_val and strength_val in CAUSAL_STRENGTH_MAP:
                    total_strength += CAUSAL_STRENGTH_MAP[strength_val]
                    link_count += 1

        pair_density = total_strength / max_possible if max_possible > 0 else 0.0
        perspective_pair_scores[pair_label] = round(pair_density, 4)
        chain_completeness[pair_label] = link_count > 0

        if link_count == 0:
            missing_chains.append(pair_label)

        pair_densities.append(pair_density)

    # Overall CLD = average density across perspective pairs
    # Apply completeness penalty: reduce by fraction of missing chains
    if pair_densities:
        avg_density = sum(pair_densities) / len(pair_densities)
        complete_count = sum(1 for v in chain_completeness.values() if v)
        completeness_factor = complete_count / len(chain_completeness) if chain_completeness else 0
        cld_score = avg_density * completeness_factor
    else:
        cld_score = 0.0

    return {
        "cld_score": round(cld_score, 4),
        "perspective_pair_scores": perspective_pair_scores,
        "chain_completeness": chain_completeness,
        "missing_chains": missing_chains,
    }


def detect_prioritization_misalignment(kg: KnowledgeGraph) -> list[dict[str, Any]]:
    """Detect misalignment between strategic importance and resource allocation.

    Compares strategicImportance of objectives with resourceAllocation of
    supporting task groups. Flags under-resourced (high importance + low
    allocation) and over-resourced (low importance + high allocation) pairs.

    Args:
        kg: KnowledgeGraph instance

    Returns:
        List of misalignment dicts with:
        - objective_id, task_group_id, importance, allocation, type
    """
    query = """
    PREFIX bita: <http://bita-system.org/ontology#>

    SELECT ?tg ?obj WHERE {
        ?tg bita:supportsObjective ?obj .
    }
    """
    results = kg.query_sparql(query)

    misalignments = []

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
            importance = "moderate"

        allocation = tg_props.get("resourceAllocation", "moderate")

        importance_score = IMPORTANCE_MAP.get(importance, 50)
        allocation_score = ALLOCATION_MAP.get(allocation, 70)

        # Under-resourced: critical/high importance + light/minimal allocation
        if importance_score >= 75 and allocation_score <= 40:
            misalignments.append({
                "objective_id": obj_id,
                "task_group_id": tg_id,
                "importance": importance,
                "allocation": allocation,
                "type": "under-resourced",
            })
        # Over-resourced: low/negligible importance + heavy allocation
        elif importance_score <= 25 and allocation_score >= 100:
            misalignments.append({
                "objective_id": obj_id,
                "task_group_id": tg_id,
                "importance": importance,
                "allocation": allocation,
                "type": "over-resourced",
            })

    return misalignments


def detect_bsc_structural_gaps(kg: KnowledgeGraph) -> list[str]:
    """Detect BSC structural gaps where objectives lack causal chain support.

    Checks for:
    - Financial objectives with no causal support from Internal Process objectives
    - Customer objectives with no causal support from Internal Process objectives

    Args:
        kg: KnowledgeGraph instance

    Returns:
        List of gap description strings
    """
    goals_by_perspective = _get_goals_by_perspective(kg)
    gaps = []

    ip_goals = goals_by_perspective.get("Internal Process", [])

    # Check Financial objectives for causal support from IP
    for fin_goal in goals_by_perspective.get("Financial", []):
        has_support = False
        for ip_goal in ip_goals:
            ip_props = ip_goal["props"]
            strength_key = f"causalLink_{fin_goal['id']}_strength"
            if ip_props.get(strength_key) in CAUSAL_STRENGTH_MAP:
                has_support = True
                break
        if not has_support:
            gaps.append(
                f"Financial objective '{fin_goal['name']}' ({fin_goal['id']}) "
                f"has no causal chain support from Internal Process objectives"
            )

    # Check Customer objectives for causal support from IP
    for cust_goal in goals_by_perspective.get("Customer", []):
        has_support = False
        for ip_goal in ip_goals:
            ip_props = ip_goal["props"]
            strength_key = f"causalLink_{cust_goal['id']}_strength"
            if ip_props.get(strength_key) in CAUSAL_STRENGTH_MAP:
                has_support = True
                break
        if not has_support:
            gaps.append(
                f"Customer objective '{cust_goal['name']}' ({cust_goal['id']}) "
                f"has no causal chain support from Internal Process objectives"
            )

    return gaps


def compute_kipga_matrix(kg: KnowledgeGraph) -> dict[str, Any]:
    """Compute Key Importance-Performance Gap Analysis (KIPGA) matrix.

    For each objective, determines importance (inherited from parent goal's
    strategicImportance) and performance (from alignment scores), then
    classifies into quadrants.

    Args:
        kg: KnowledgeGraph instance

    Returns:
        Dictionary with:
        - quadrants: Dict of quadrant name to list of objective IDs
        - plot_data: List of dicts for visualization
    """
    # Get all objectives with their parent goal
    obj_query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?obj ?goal WHERE {
        ?obj rdf:type bita:Objective .
        ?goal bita:hasObjective ?obj .
    }
    """
    obj_results = kg.query_sparql(obj_query)

    # Get supported objectives and their alignment scores
    support_query = """
    PREFIX bita: <http://bita-system.org/ontology#>

    SELECT ?tg ?obj WHERE {
        ?tg bita:supportsObjective ?obj .
    }
    """
    support_results = kg.query_sparql(support_query)

    # Build per-objective alignment scores
    obj_alignment_scores: dict[str, list[float]] = {}
    for row in support_results:
        obj_id = str(row["obj"]).split("#")[-1]
        tg_id = str(row["tg"]).split("#")[-1]

        tg_props = kg.get_entity_properties(tg_id)
        relevance_key = f"alignment_{obj_id}_relevance"
        relevance = tg_props.get(relevance_key, "none")
        score = compute_alignment_score(relevance)

        if obj_id not in obj_alignment_scores:
            obj_alignment_scores[obj_id] = []
        obj_alignment_scores[obj_id].append(score)

    quadrants: dict[str, list[str]] = {
        "concentrate_here": [],
        "keep_up": [],
        "low_priority": [],
        "possible_overkill": [],
    }
    plot_data: list[dict[str, Any]] = []

    for obj_row in obj_results:
        obj_id = str(obj_row["obj"]).split("#")[-1]
        goal_id = str(obj_row["goal"]).split("#")[-1]

        obj_props = kg.get_entity_properties(obj_id)
        goal_props = kg.get_entity_properties(goal_id)

        # Importance inherited from parent goal
        importance_label = goal_props.get("strategicImportance", "moderate")
        importance = IMPORTANCE_MAP.get(importance_label, 50) / 100.0

        obj_name = obj_props.get("label", obj_id)
        goal_name = goal_props.get("label", goal_props.get("goalName", goal_id))

        # Performance = average alignment score for this objective
        if obj_id in obj_alignment_scores and obj_alignment_scores[obj_id]:
            perf_scores = obj_alignment_scores[obj_id]
            performance = (sum(perf_scores) / len(perf_scores)) / 100.0
        else:
            performance = 0.0

        # Classify into quadrants (threshold at 0.5 for both axes)
        if importance >= 0.5 and performance < 0.5:
            quadrant = "concentrate_here"
        elif importance >= 0.5 and performance >= 0.5:
            quadrant = "keep_up"
        elif importance < 0.5 and performance < 0.5:
            quadrant = "low_priority"
        else:
            quadrant = "possible_overkill"

        quadrants[quadrant].append(obj_id)

        plot_data.append({
            "id": obj_id,
            "name": obj_name,
            "goal_id": goal_id,
            "goal_name": goal_name,
            "importance": round(importance, 3),
            "performance": round(performance, 3),
            "quadrant": quadrant,
        })

    return {
        "quadrants": quadrants,
        "plot_data": plot_data,
    }


def compute_all_metrics(kg: KnowledgeGraph) -> dict[str, Any]:
    """Compute all composite metrics from the Knowledge Graph.

    Args:
        kg: KnowledgeGraph instance

    Returns:
        Dictionary with all metric values:
        - sai: Strategic Alignment Index (0-100)
        - coverage: Coverage percentage (0-100)
        - avg_priority: Average weighted priority score (0-100)
        - avg_kpi_utility: Average KPI utility score (0-100)
        - avg_catchball: Average catchball consistency (0-100)
        - egi: Execution Gap Index (0-100)
        - cld: Causal Linkage Density result dict
        - prioritization_misalignments: List of misalignment dicts
        - bsc_structural_gaps: List of gap description strings
        - kipga: KIPGA matrix result dict
    """
    # 1. SAI (Strategic Alignment Index)
    sai = compute_sai(kg)

    # 2. Coverage
    obj_query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?obj WHERE {
        ?obj rdf:type bita:Objective .
    }
    """
    obj_results = kg.query_sparql(obj_query)
    total_objectives = len(obj_results)

    # Find objectives with at least one supporting task
    supported_objectives = set()
    tg_query = """
    PREFIX bita: <http://bita-system.org/ontology#>

    SELECT ?tg ?obj WHERE {
        ?tg bita:supportsObjective ?obj .
    }
    """
    support_results = kg.query_sparql(tg_query)
    for row in support_results:
        obj_uri = str(row["obj"])
        obj_id = obj_uri.split("#")[-1]
        supported_objectives.add(obj_id)

    coverage = compute_coverage(total_objectives, len(supported_objectives))

    # 3. Average Priority Score (aggregate from aligned task groups)
    priority_scores = []
    for row in support_results:
        obj_uri = str(row["obj"])
        obj_id = obj_uri.split("#")[-1]
        tg_uri = str(row["tg"])
        tg_id = tg_uri.split("#")[-1]

        obj_props = kg.get_entity_properties(obj_id)
        tg_props = kg.get_entity_properties(tg_id)

        importance = obj_props.get("strategicImportance", "moderate")
        allocation = tg_props.get("resourceAllocation", "moderate")

        # Use default risk exposure of 50
        priority = compute_priority_score(importance, allocation, risk_exposure=50.0)
        priority_scores.append(priority)

    avg_priority = (
        sum(priority_scores) / len(priority_scores) if priority_scores else 50.0
    )

    # 4. Average KPI Utility
    kpi_query = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?kpi WHERE {
        ?kpi rdf:type bita:KPI .
    }
    """
    kpi_results = kg.query_sparql(kpi_query)
    kpi_utilities = []

    for kpi_row in kpi_results:
        kpi_uri = str(kpi_row["kpi"])
        kpi_id = kpi_uri.split("#")[-1]
        kpi_props = kg.get_entity_properties(kpi_id)

        baseline_exists = kpi_props.get("kpiBaselineExists", False)
        measurable = kpi_props.get("kpiMeasurable", True)
        owner_assigned = "ownedBy" in kpi_props

        utility = compute_kpi_utility(baseline_exists, measurable, owner_assigned)
        kpi_utilities.append(utility)

    avg_kpi_utility = (
        sum(kpi_utilities) / len(kpi_utilities) if kpi_utilities else 0.0
    )

    # 5. Average Catchball (from Layer 3 cascade analysis)
    catchball_scores = []
    tg_query_all = """
    PREFIX bita: <http://bita-system.org/ontology#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?tg WHERE {
        ?tg rdf:type bita:TaskGroup .
    }
    """
    tg_results_all = kg.query_sparql(tg_query_all)

    for tg_row in tg_results_all:
        tg_uri = str(tg_row["tg"])
        tg_id = tg_uri.split("#")[-1]
        tg_props = kg.get_entity_properties(tg_id)

        # Find cascade and sufficiency properties
        for prop_name, prop_value in tg_props.items():
            if "_strength" in prop_name and "cascade_" in prop_name:
                # Extract corresponding sufficiency
                obj_id = prop_name.split("cascade_")[1].split("_strength")[0]
                sufficiency_key = f"sufficiency_{obj_id}_level"

                if sufficiency_key in tg_props:
                    cascade = prop_value
                    sufficiency = tg_props[sufficiency_key]

                    catchball = compute_catchball(cascade, sufficiency)
                    catchball_scores.append(catchball)

    avg_catchball = (
        sum(catchball_scores) / len(catchball_scores) if catchball_scores else 70.0
    )

    # 6. EGI (from Layer 3 gap analysis - compute overall severity)
    # Calculate gap severity across all alignments
    gap_severities = []
    for row in support_results:
        obj_uri = str(row["obj"])
        obj_id = obj_uri.split("#")[-1]
        tg_uri = str(row["tg"])
        tg_id = tg_uri.split("#")[-1]

        obj_props = kg.get_entity_properties(obj_id)
        tg_props = kg.get_entity_properties(tg_id)

        importance = obj_props.get("strategicImportance", "moderate")
        allocation = tg_props.get("resourceAllocation", "moderate")

        # Map to numeric scores
        importance_score = IMPORTANCE_MAP.get(importance, 50)
        allocation_score = ALLOCATION_MAP.get(allocation, 70)

        # Calculate gap
        gap = importance_score - allocation_score

        if gap > 40:
            gap_severities.append(compute_egi("critical"))
        elif gap > 20:
            gap_severities.append(compute_egi("high"))
        elif gap > 0:
            gap_severities.append(compute_egi("moderate"))
        else:
            gap_severities.append(compute_egi("low"))

    egi = sum(gap_severities) / len(gap_severities) if gap_severities else 30.0

    # 7. New metrics
    cld = compute_causal_linkage_density(kg)
    prioritization_misalignments = detect_prioritization_misalignment(kg)
    bsc_structural_gaps = detect_bsc_structural_gaps(kg)
    kipga = compute_kipga_matrix(kg)

    return {
        "sai": round(sai, 2),
        "coverage": round(coverage, 2),
        "avg_priority": round(avg_priority, 2),
        "avg_kpi_utility": round(avg_kpi_utility, 2),
        "avg_catchball": round(avg_catchball, 2),
        "egi": round(egi, 2),
        "cld": cld,
        "prioritization_misalignments": prioritization_misalignments,
        "bsc_structural_gaps": bsc_structural_gaps,
        "kipga": kipga,
    }
