"""Pipeline State — KG snapshots and SHACL validation per layer.

Captures knowledge graph state after each pipeline layer runs,
enabling layer-by-layer inspection and diff computation.
"""

from datetime import datetime
from typing import Any

from rdflib import Graph, RDF

from .knowledge_graph import KnowledgeGraph

# SHACL shapes for KG validation (Turtle format)
SHACL_SHAPES_TTL = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix bita: <http://bita-system.org/ontology#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Shape 1: Every TaskGroup must have at least one task with an assignee
bita:TaskGroupShape
    a sh:NodeShape ;
    sh:targetClass bita:TaskGroup ;
    sh:property [
        sh:path bita:hasTask ;
        sh:minCount 1 ;
        sh:name "hasTask" ;
        sh:message "Every TaskGroup must have at least one task." ;
    ] .

# Shape 2: Every Goal/Objective must have at least one KPI
bita:ObjectiveKPIShape
    a sh:NodeShape ;
    sh:targetClass bita:Goal ;
    sh:property [
        sh:path bita:hasKPI ;
        sh:minCount 1 ;
        sh:name "hasKPI" ;
        sh:message "Every Goal must have at least one KPI." ;
    ] .

# Shape 3: Every KPI should have an owner
bita:KPIOwnerShape
    a sh:NodeShape ;
    sh:targetClass bita:KPI ;
    sh:property [
        sh:path bita:ownedBy ;
        sh:minCount 1 ;
        sh:severity sh:Warning ;
        sh:name "ownedBy" ;
        sh:message "Every KPI should have an owner." ;
    ] .

# Shape 4: At least one objective per BSC perspective
# (Implemented as a check in code since SHACL cardinality
#  on class instances across a property is complex;
#  we validate this programmatically in run_shacl_validation)
"""


class PipelineState:
    """Tracks KG state across pipeline layers for inspection and debugging."""

    def __init__(self):
        self._snapshots: list[dict[str, Any]] = []
        self._shacl_results: list[dict[str, Any]] = []

    def capture_snapshot(
        self, kg: KnowledgeGraph, layer: int, label: str
    ) -> None:
        """Serialize KG state and compute statistics after a layer runs.

        Args:
            kg: KnowledgeGraph instance to snapshot
            layer: Pipeline layer number (0=init, 1-4=layers)
            label: Human-readable label (e.g. "After Layer 1: Extraction")
        """
        triple_count = len(kg.graph)

        # Count nodes by RDF type
        node_counts: dict[str, int] = {}
        for subj, _, obj in kg.graph.triples((None, RDF.type, None)):
            type_name = str(obj).split("#")[-1]
            node_counts[type_name] = node_counts.get(type_name, 0) + 1

        # Count edges by predicate (excluding rdf:type and literal properties)
        edge_counts: dict[str, int] = {}
        for _, pred, obj in kg.graph:
            if pred == RDF.type:
                continue
            pred_name = str(pred).split("#")[-1]
            from rdflib import URIRef
            if isinstance(obj, URIRef):
                edge_counts[pred_name] = edge_counts.get(pred_name, 0) + 1

        # Graph density: edges / (nodes * (nodes-1)) for directed graph
        total_nodes = sum(node_counts.values())
        total_edges = sum(edge_counts.values())
        if total_nodes > 1:
            density = total_edges / (total_nodes * (total_nodes - 1))
        else:
            density = 0.0

        # Serialize graph to Turtle for diff/export
        turtle_str = kg.serialize(format="turtle")

        snapshot = {
            "layer": layer,
            "label": label,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "triple_count": triple_count,
            "node_counts": node_counts,
            "edge_counts": edge_counts,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "density": round(density, 6),
            "turtle": turtle_str,
        }

        self._snapshots.append(snapshot)

    def run_shacl_validation(
        self, kg: KnowledgeGraph, layer: int
    ) -> dict[str, Any]:
        """Run SHACL shapes against current KG state.

        Args:
            kg: KnowledgeGraph instance to validate
            layer: Pipeline layer number

        Returns:
            Validation result dict with conforms, violations, etc.
        """
        import pyshacl

        shapes_graph = Graph()
        shapes_graph.parse(data=SHACL_SHAPES_TTL, format="turtle")

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=kg.graph,
            shacl_graph=shapes_graph,
            inference="none",
            abort_on_first=False,
        )

        # Parse violations from results graph
        violations: list[dict[str, Any]] = []
        SH = "http://www.w3.org/ns/shacl#"

        for result_node in results_graph.subjects(
            RDF.type,
            results_graph.namespace_manager.expand_curie("sh:ValidationResult")
            if hasattr(results_graph.namespace_manager, "expand_curie")
            else Graph().parse(
                data='@prefix sh: <http://www.w3.org/ns/shacl#> .', format="turtle"
            ).namespace_manager.expand_curie("sh:ValidationResult"),
        ):
            pass  # Fallback: parse from results_text

        # Parse violations from results_text (more reliable across pyshacl versions)
        violation_entries = []
        if not conforms and results_text:
            from rdflib import Namespace
            sh = Namespace(SH)

            for result_node in results_graph.subjects(RDF.type, sh.ValidationResult):
                violation: dict[str, Any] = {}

                for p, o in results_graph.predicate_objects(result_node):
                    p_name = str(p).split("#")[-1]
                    if p_name == "focusNode":
                        violation["focus_node"] = str(o).split("#")[-1]
                    elif p_name == "resultMessage":
                        violation["message"] = str(o)
                    elif p_name == "resultSeverity":
                        violation["severity"] = str(o).split("#")[-1]
                    elif p_name == "sourceShape":
                        violation["source_shape"] = str(o).split("#")[-1]
                    elif p_name == "resultPath":
                        violation["path"] = str(o).split("#")[-1]

                if violation:
                    violation_entries.append(violation)

        # BSC balance check (programmatic, not SHACL)
        bsc_check = self._check_bsc_balance(kg)

        result = {
            "layer": layer,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "conforms": conforms and bsc_check["balanced"],
            "shacl_conforms": conforms,
            "violation_count": len(violation_entries),
            "violations": violation_entries,
            "bsc_balance": bsc_check,
            "results_text": results_text,
        }

        self._shacl_results.append(result)
        return result

    @staticmethod
    def _check_bsc_balance(kg: KnowledgeGraph) -> dict[str, Any]:
        """Check that at least one goal exists per BSC perspective.

        Args:
            kg: KnowledgeGraph instance

        Returns:
            Dict with balanced flag and per-perspective counts
        """
        query = """
        PREFIX bita: <http://bita-system.org/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?label (COUNT(?goal) AS ?count) WHERE {
            ?goal rdf:type bita:Goal .
            ?goal bita:bscPerspective ?perspective .
            ?perspective rdfs:label ?label .
        }
        GROUP BY ?label
        """
        results = kg.query_sparql(query)

        expected = {"Financial", "Customer", "Internal Process", "Learning & Growth"}
        found: dict[str, int] = {}
        for row in results:
            label = str(row["label"])
            count = int(row["count"])
            found[label] = count

        missing = [p for p in expected if found.get(p, 0) == 0]

        return {
            "balanced": len(missing) == 0,
            "perspective_counts": found,
            "missing_perspectives": missing,
        }

    def get_snapshot(self, layer: int) -> dict[str, Any] | None:
        """Get snapshot for a specific layer.

        Args:
            layer: Layer number to retrieve

        Returns:
            Snapshot dict or None if not found
        """
        for snap in self._snapshots:
            if snap["layer"] == layer:
                return snap
        return None

    def get_kg_diff(
        self, layer_before: int, layer_after: int
    ) -> dict[str, Any]:
        """Compute diff between two layer snapshots.

        Args:
            layer_before: Earlier layer number
            layer_after: Later layer number

        Returns:
            Dict with new_triples count, count changes, etc.
        """
        snap_before = self.get_snapshot(layer_before)
        snap_after = self.get_snapshot(layer_after)

        if snap_before is None or snap_after is None:
            return {
                "error": f"Missing snapshot(s): before={layer_before}, after={layer_after}",
            }

        # Parse both turtle strings to compute triple diff
        g_before = Graph()
        g_before.parse(data=snap_before["turtle"], format="turtle")

        g_after = Graph()
        g_after.parse(data=snap_after["turtle"], format="turtle")

        triples_before = set(g_before)
        triples_after = set(g_after)

        new_triples = triples_after - triples_before
        removed_triples = triples_before - triples_after

        # Summarize node type changes
        node_before = snap_before["node_counts"]
        node_after = snap_after["node_counts"]
        all_types = set(node_before.keys()) | set(node_after.keys())
        node_changes = {}
        for t in all_types:
            before_count = node_before.get(t, 0)
            after_count = node_after.get(t, 0)
            if before_count != after_count:
                node_changes[t] = {
                    "before": before_count,
                    "after": after_count,
                    "delta": after_count - before_count,
                }

        return {
            "layer_before": layer_before,
            "layer_after": layer_after,
            "triples_before": snap_before["triple_count"],
            "triples_after": snap_after["triple_count"],
            "new_triple_count": len(new_triples),
            "removed_triple_count": len(removed_triples),
            "node_type_changes": node_changes,
            "density_before": snap_before["density"],
            "density_after": snap_after["density"],
        }

    def get_all_snapshots(self) -> list[dict[str, Any]]:
        """Return all snapshots for Pipeline Inspector page.

        Returns:
            List of snapshot dicts (without full turtle to keep it small).
        """
        return [
            {k: v for k, v in snap.items() if k != "turtle"}
            for snap in self._snapshots
        ]

    def get_shacl_results(self, layer: int) -> dict[str, Any] | None:
        """Get SHACL validation results for a layer.

        Args:
            layer: Layer number

        Returns:
            SHACL result dict or None if not found
        """
        for result in self._shacl_results:
            if result["layer"] == layer:
                return result
        return None
