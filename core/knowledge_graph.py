"""Knowledge Graph — Central data store using RDFLib.

All layers write to and read from this central KG.
"""

from typing import Any, Optional

import networkx as nx
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD


class KnowledgeGraph:
    """Central RDF knowledge graph for BITA system."""

    def __init__(self):
        """Initialize empty RDF graph with BITA namespace."""
        self.graph = Graph()
        self.bita = Namespace("http://bita-system.org/ontology#")
        self.graph.bind("bita", self.bita)
        self.graph.bind("xsd", XSD)

        # Initialize static instances (BSC perspectives)
        self._init_static_instances()

    def _init_static_instances(self):
        """Pre-load BSC perspectives."""
        # BSC Perspectives
        bsc_perspectives = [
            ("BSC_Financial", "Financial"),
            ("BSC_Customer", "Customer"),
            ("BSC_InternalProcess", "Internal Process"),
            ("BSC_LearningGrowth", "Learning & Growth"),
        ]

        for uri_suffix, label in bsc_perspectives:
            uri = self.bita[uri_suffix]
            self.graph.add((uri, RDF.type, self.bita.BSCPerspective))
            self.graph.add((uri, RDFS.label, Literal(label)))

        # BSC causal chain
        self.graph.add(
            (self.bita.BSC_Financial, self.bita.bscDependsOn, self.bita.BSC_Customer)
        )
        self.graph.add(
            (
                self.bita.BSC_Customer,
                self.bita.bscDependsOn,
                self.bita.BSC_InternalProcess,
            )
        )
        self.graph.add(
            (
                self.bita.BSC_InternalProcess,
                self.bita.bscDependsOn,
                self.bita.BSC_LearningGrowth,
            )
        )

    def add_entity(
        self, entity_id: str, entity_type: str, properties: dict[str, Any]
    ) -> URIRef:
        """Add an entity to the knowledge graph.

        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type/class of the entity (e.g., "StrategicObjective")
            properties: Dictionary of property_name: value pairs
                       Should include "label" key for rdfs:label

        Returns:
            URIRef of the created entity
        """
        uri = self.bita[entity_id]
        self.graph.add((uri, RDF.type, self.bita[entity_type]))

        # Add rdfs:label if provided (RDF standard for display name)
        if "label" in properties:
            label_value = properties["label"]
            self.graph.add((uri, RDFS.label, Literal(label_value)))

        # Add all other properties (excluding "label" which is handled above)
        for prop, value in properties.items():
            if prop == "label":
                continue  # Already added as rdfs:label

            predicate = self.bita[prop]

            # Handle different value types
            if isinstance(value, bool):
                obj = Literal(value, datatype=XSD.boolean)
            elif isinstance(value, int):
                obj = Literal(value, datatype=XSD.integer)
            elif isinstance(value, float):
                obj = Literal(value, datatype=XSD.float)
            elif isinstance(value, str):
                # Check if it's a reference to another entity (short ID like G1, A1_2, BSC_Financial)
                if value and value[0].isupper() and "_" in value and " " not in value and len(value) <= 30:
                    obj = self.bita[value]
                else:
                    obj = Literal(value, datatype=XSD.string)
            else:
                obj = Literal(str(value), datatype=XSD.string)

            self.graph.add((uri, predicate, obj))

        return uri

    def add_relationship(
        self, subject_id: str, predicate: str, object_id: str
    ) -> None:
        """Add a relationship between two entities.

        Args:
            subject_id: ID of the subject entity
            predicate: Relationship type
            object_id: ID of the object entity
        """
        subject = self.bita[subject_id]
        predicate_uri = self.bita[predicate]
        obj = self.bita[object_id]

        self.graph.add((subject, predicate_uri, obj))

    def query_sparql(self, query: str) -> list[dict]:
        """Execute a SPARQL query.

        Args:
            query: SPARQL query string

        Returns:
            List of result bindings as dictionaries
        """
        results = self.graph.query(query)
        return [dict(row.asdict()) for row in results]

    def get_entity_properties(self, entity_id: str) -> dict[str, Any]:
        """Get all properties of an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Dictionary of property names to values
        """
        uri = self.bita[entity_id]
        properties = {}

        for pred, obj in self.graph.predicate_objects(uri):
            # Skip RDF type
            if pred == RDF.type:
                continue

            # Extract property name from URI
            prop_name = str(pred).split("#")[-1]

            # Extract value
            if isinstance(obj, Literal):
                properties[prop_name] = obj.toPython()
            else:
                # It's a reference to another entity
                properties[prop_name] = str(obj).split("#")[-1]

        return properties

    def export_to_networkx(self) -> nx.DiGraph:
        """Export the RDF graph to NetworkX for graph analysis.

        Returns:
            NetworkX directed graph
        """
        G = nx.DiGraph()

        # Add nodes
        for subj in self.graph.subjects(unique=True):
            node_id = str(subj).split("#")[-1]
            # Get node type
            for obj in self.graph.objects(subj, RDF.type):
                node_type = str(obj).split("#")[-1]
                G.add_node(node_id, type=node_type)
                break

        # Add edges
        for subj, pred, obj in self.graph:
            if pred == RDF.type:
                continue

            subj_id = str(subj).split("#")[-1]
            pred_name = str(pred).split("#")[-1]

            if isinstance(obj, URIRef):
                obj_id = str(obj).split("#")[-1]
                G.add_edge(subj_id, obj_id, relationship=pred_name)

        return G

    def serialize(self, format: str = "turtle") -> str:
        """Serialize the graph to a string.

        Args:
            format: Serialization format (turtle, xml, n3, etc.)

        Returns:
            Serialized graph as string
        """
        return self.graph.serialize(format=format)

    def save(self, filepath: str, format: str = "turtle"):
        """Save the graph to a file.

        Args:
            filepath: Path to output file
            format: Serialization format
        """
        self.graph.serialize(destination=filepath, format=format)

    def load(self, filepath: str, format: str = "turtle"):
        """Load a graph from a file.

        Args:
            filepath: Path to input file
            format: Serialization format
        """
        self.graph.parse(filepath, format=format)
