"""Page 5: Knowledge Graph Visualization.

Interactive network visualization of the strategic plan Knowledge Graph.
"""

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
import tempfile
from pathlib import Path


def render():
    """Render the knowledge graph visualization page."""
    st.markdown(
        '<h1 class="main-header">🕸️ Knowledge Graph Visualization</h1>',
        unsafe_allow_html=True,
    )

    if st.session_state.kg is None:
        st.warning(
            "⚠️ Please upload and analyze a strategic plan first (Upload Plans page)."
        )
        return

    kg = st.session_state.kg

    st.markdown("Interactive visualization of the strategic plan Knowledge Graph. "
                "Hover over nodes and edges to see details. Legend is shown on the graph.")

    # Filter options
    st.markdown("### Visualization Settings")

    col1, col2, col3 = st.columns(3)

    with col1:
        show_goals = st.checkbox("Show Goals", value=True)
        show_task_groups = st.checkbox("Show Task Groups", value=True)
        show_bsc = st.checkbox("Show BSC Perspectives", value=True)

    with col2:
        show_objectives = st.checkbox("Show Objectives", value=True)
        show_kpis = st.checkbox("Show KPIs", value=True)
        show_tasks = st.checkbox("Show Individual Tasks", value=True)

    with col3:
        show_node_labels = st.checkbox("Show Node Labels", value=False)
        show_edge_labels = st.checkbox("Show Edge Labels", value=True)

    # Generate visualization
    if st.button("🔄 Generate Visualization", type="primary"):
        with st.spinner("Generating interactive graph..."):
            html_file = create_knowledge_graph_viz(
                kg,
                show_goals=show_goals,
                show_task_groups=show_task_groups,
                show_bsc=show_bsc,
                show_objectives=show_objectives,
                show_kpis=show_kpis,
                show_tasks=show_tasks,
                show_node_labels=show_node_labels,
                show_edge_labels=show_edge_labels,
            )

        # Display
        st.success("✅ Visualization generated!")

        # Read and display HTML
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        components.html(html_content, height=800, scrolling=True)

        # Stats
        st.markdown("### 📊 Graph Statistics")

        import networkx as nx

        G = kg.export_to_networkx()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Nodes", G.number_of_nodes())

        with col2:
            st.metric("Total Edges", G.number_of_edges())

        with col3:
            # Count by type
            goal_count = len([n for n, d in G.nodes(data=True) if d.get("type") == "Goal"])
            st.metric("Goals", goal_count)

        with col4:
            tg_count = len([n for n, d in G.nodes(data=True) if d.get("type") == "TaskGroup"])
            st.metric("Task Groups", tg_count)

    # SPARQL Query Interface
    st.markdown("---")
    st.markdown("### 🔍 SPARQL Query Interface")

    st.markdown("""
    Query the Knowledge Graph using SPARQL. The namespace prefix is `bita:` for `http://bita-system.org/ontology#`
    """)

    # Sample queries
    sample_queries = {
        "All Strategic Goals": """SELECT ?goal ?name ?importance
WHERE {
    ?goal rdf:type bita:Goal .
    ?goal rdfs:label ?name .
    ?goal bita:strategicImportance ?importance .
}""",
        "All Task Groups": """SELECT ?tg ?name ?allocation
WHERE {
    ?tg rdf:type bita:TaskGroup .
    ?tg rdfs:label ?name .
    ?tg bita:resourceAllocation ?allocation .
}""",
        "Alignment Relationships": """SELECT ?goal ?taskGroup ?relevance ?strength
WHERE {
    ?taskGroup bita:supportsObjective ?goal .
    ?taskGroup ?relProp ?relevance .
    ?taskGroup ?strProp ?strength .
    FILTER(CONTAINS(STR(?relProp), "alignment_") && CONTAINS(STR(?relProp), "_relevance"))
    FILTER(CONTAINS(STR(?strProp), "alignment_") && CONTAINS(STR(?strProp), "_strength"))
}""",
        "BSC Perspective Distribution": """SELECT ?perspective (COUNT(?goal) as ?count)
WHERE {
    ?goal rdf:type bita:Goal .
    ?goal bita:bscPerspective ?perspective .
}
GROUP BY ?perspective""",
        "All Triples": """SELECT ?subject ?predicate ?object
WHERE {
    ?subject ?predicate ?object .
}
LIMIT 100""",
    }

    # Query selector
    query_option = st.selectbox(
        "Select a sample query or write your own:",
        ["Custom Query"] + list(sample_queries.keys())
    )

    # Query input
    if query_option == "Custom Query":
        default_query = """SELECT ?s ?p ?o
WHERE {
    ?s ?p ?o .
}
LIMIT 10"""
    else:
        default_query = sample_queries[query_option]

    sparql_query = st.text_area(
        "SPARQL Query:",
        value=default_query,
        height=200,
        help="Write a SPARQL query to explore the Knowledge Graph"
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        execute_query = st.button("▶️ Execute Query", type="primary")

    if execute_query:
        try:
            with st.spinner("Executing SPARQL query..."):
                results = kg.query_sparql(sparql_query)

            if results:
                st.success(f"✅ Query returned {len(results)} results")

                # Display as dataframe
                import pandas as pd

                # Convert results to display format
                display_results = []
                for row in results:
                    display_row = {}
                    for key, value in row.items():
                        if value is None:
                            display_row[key] = None
                        else:
                            # Extract local name from URIs
                            value_str = str(value)
                            if "#" in value_str:
                                display_row[key] = value_str.split("#")[-1]
                            else:
                                display_row[key] = value_str
                    display_results.append(display_row)

                df = pd.DataFrame(display_results)
                st.dataframe(df, width="stretch")

                # Download option
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name="sparql_results.csv",
                    mime="text/csv"
                )
            else:
                st.info("Query returned no results.")

        except Exception as e:
            st.error(f"❌ Query execution failed: {str(e)}")
            st.exception(e)

    # Export options
    st.markdown("---")
    st.markdown("### 💾 Export Options")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Export as Turtle (.ttl)"):
            ttl_content = kg.serialize(format="turtle")
            st.download_button(
                label="Download Turtle File",
                data=ttl_content,
                file_name="knowledge_graph.ttl",
                mime="text/turtle",
            )

    with col2:
        if st.button("Export as RDF/XML (.rdf)"):
            rdf_content = kg.serialize(format="xml")
            st.download_button(
                label="Download RDF/XML File",
                data=rdf_content,
                file_name="knowledge_graph.rdf",
                mime="application/rdf+xml",
            )


def create_knowledge_graph_viz(
    kg,
    show_goals=True,
    show_task_groups=True,
    show_bsc=True,
    show_objectives=True,
    show_kpis=True,
    show_tasks=True,
    show_node_labels=False,
    show_edge_labels=True,
):
    """Create interactive Knowledge Graph visualization using pyvis."""

    # Export to NetworkX
    import networkx as nx

    G = kg.export_to_networkx()

    # Create pyvis network
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#ffffff",
        font_color="black",
        directed=True,
    )

    # Configure physics with stabilization — graph settles then freezes
    net.set_options("""
    {
        "nodes": {
            "font": {
                "size": 14,
                "face": "arial",
                "multi": "html",
                "bold": {
                    "color": "#000000"
                }
            }
        },
        "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.01,
                "springLength": 120,
                "springConstant": 0.06,
                "damping": 0.4,
                "avoidOverlap": 0.5
            },
            "stabilization": {
                "enabled": true,
                "iterations": 300,
                "updateInterval": 25,
                "fit": true
            }
        },
        "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true
        }
    }
    """)

    # Node type filters
    entity_types = {
        "Goal": show_goals,
        "TaskGroup": show_task_groups,
        "BSCPerspective": show_bsc,
        "Objective": show_objectives,
        "KPI": show_kpis,
        "Task": show_tasks,
    }

    # Color mapping
    color_map = {
        "Goal": "#1f77b4",          # Blue
        "TaskGroup": "#2ca02c",     # Green
        "BSCPerspective": "#ff7f0e",  # Orange
        "Objective": "#e377c2",     # Pink
        "KPI": "#bcbd22",          # Yellow-green
        "Task": "#17becf",          # Cyan
        "Plan": "#7f7f7f",          # Gray
        "Organization": "#7f7f7f",  # Gray
        "ActionPhase": "#aec7e8",   # Light blue
    }

    # Size mapping (importance-based)
    size_map = {
        "Goal": 30,
        "TaskGroup": 25,
        "BSCPerspective": 35,
        "Objective": 10,
        "KPI": 10,
        "Task": 8,
        "Plan": 40,
        "Organization": 45,
        "ActionPhase": 20,
    }

    # Add nodes
    for node, data in G.nodes(data=True):
        node_type = data.get("type", "Unknown")

        # Apply filter
        if node_type not in entity_types or not entity_types.get(node_type, True):
            continue

        # Get node properties
        props = kg.get_entity_properties(node)

        # Get display label from rdfs:label (standard RDF property)
        display_name = props.get('label', node)

        # Build title (hover tooltip) - show entity type, name and ID
        title = f"[{node_type}] {display_name} ({node})"

        # Show entity name as label only if enabled
        label = display_name if show_node_labels else ""

        # Add node
        net.add_node(
            node,
            label=label,
            title=title,
            color=color_map.get(node_type, "#cccccc"),
            size=size_map.get(node_type, 15),
            shape="dot",
        )

    # Width by contribution strength (for supportsObjective edges)
    strength_width_map = {
        "primary": 5,
        "supporting": 3,
        "tangential": 1.5,
    }

    # Dash pattern by alignment relevance (for supportsObjective edges)
    # pyvis dashes: False=solid, [dash, gap]=dashed, [dot, gap]=dotted
    relevance_dash_map = {
        "direct": False,           # solid line
        "partial": [10, 6],        # dashed
        "indirect": [3, 5],        # dotted
        "none": [2, 8],            # sparse dots
    }

    # Color intensity by relevance
    relevance_color_map = {
        "direct": "#2ca02c",       # strong green
        "partial": "#66c266",      # medium green
        "indirect": "#a3d9a3",     # light green
        "none": "#cccccc",         # gray
    }

    # Add edges
    for source, target, data in G.edges(data=True):
        # Check if both nodes are in the filtered set
        if source not in net.get_nodes() or target not in net.get_nodes():
            continue

        relationship = data.get("relationship", "")

        # Edge styling based on relationship type
        if "supportsObjective" in relationship:
            # Look up alignment relevance and strength from source (TaskGroup) properties
            source_props = kg.get_entity_properties(source)
            relevance = source_props.get(f"alignment_{target}_relevance", "none")
            strength = source_props.get(f"alignment_{target}_strength", "supporting")

            color = relevance_color_map.get(relevance, "#cccccc")
            width = strength_width_map.get(strength, 2)
            dashes = relevance_dash_map.get(relevance, False)
            title = f"supports | relevance={relevance}, strength={strength}"
            label = "supports" if show_edge_labels else None
        elif "hasGoal" in relationship:
            color = "#1f77b4"
            width = 1
            dashes = False
            title = "hasGoal"
            label = "hasGoal" if show_edge_labels else None
        elif "hasTask" in relationship or "hasObjective" in relationship or "hasKPI" in relationship:
            color = "#1f77b4"
            width = 1
            dashes = False
            title = relationship
            label = relationship if show_edge_labels else None
        elif "bscPerspective" in relationship:
            color = "#ff7f0e"
            width = 2
            dashes = False
            title = "bscPerspective"
            label = "BSC" if show_edge_labels else None
        elif "belongsTo" in relationship or "containsGroup" in relationship:
            color = "#7f7f7f"
            width = 1
            dashes = False
            title = relationship
            label = None
        else:
            color = "#cccccc"
            width = 1
            dashes = False
            title = relationship
            label = relationship if show_edge_labels else None

        # Add edge
        edge_config = {
            "color": color,
            "width": width,
            "title": title,
            "dashes": dashes,
        }
        if label and show_edge_labels:
            edge_config["label"] = label
            edge_config["font"] = {"size": 10, "color": "#333333", "align": "middle"}

        net.add_edge(source, target, **edge_config)

    # Save to temp file, then inject SVG legend overlay
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".html", mode="w", encoding="utf-8"
    )
    net.save_graph(temp_file.name)

    # Build SVG legend and script to freeze after stabilization
    legend_html = _build_legend_html()
    freeze_script = """
<script>
  // Disable physics after stabilization so graph stops moving
  network.once("stabilizationIterationsDone", function () {
      network.setOptions({ physics: { enabled: false } });
  });
</script>
"""
    with open(temp_file.name, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", legend_html + "\n" + freeze_script + "\n</body>")
    with open(temp_file.name, "w", encoding="utf-8") as f:
        f.write(html)

    return temp_file.name


def _build_legend_html() -> str:
    """Build an HTML/SVG legend overlay for the KG visualization."""

    # Node type entries: (label, color) — matches color_map
    node_types = [
        ("Goal", "#1f77b4"),
        ("Task Group", "#2ca02c"),
        ("BSC Perspective", "#ff7f0e"),
        ("Objective", "#e377c2"),
        ("KPI", "#bcbd22"),
        ("Task", "#17becf"),
        ("Phase", "#aec7e8"),
    ]

    # Relevance entries: (label, color, dash_array) — matches relevance_color_map
    relevance_styles = [
        ("Direct", "#2ca02c", ""),             # solid
        ("Partial", "#66c266", "8,5"),         # dashed
        ("Indirect", "#a3d9a3", "2,4"),        # dotted
    ]

    # Strength entries: (label, width)
    strength_styles = [
        ("Primary", 5),
        ("Supporting", 3),
        ("Tangential", 1.5),
    ]

    # Build SVG for node types
    node_y = 20
    node_svg = ""
    for label, color in node_types:
        node_svg += (
            f'<circle cx="12" cy="{node_y}" r="7" fill="{color}"/>'
            f'<text x="26" y="{node_y + 4}" font-size="11" fill="#333">{label}</text>'
        )
        node_y += 20

    # Build SVG for relevance (line styles)
    rel_y = node_y + 10
    rel_svg = (
        f'<text x="4" y="{rel_y}" font-size="11" font-weight="bold" fill="#333">'
        f'Relevance</text>'
    )
    rel_y += 16
    for label, color, dash in relevance_styles:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        rel_svg += (
            f'<line x1="4" y1="{rel_y}" x2="40" y2="{rel_y}" '
            f'stroke="{color}" stroke-width="3"{dash_attr}/>'
            f'<text x="46" y="{rel_y + 4}" font-size="11" fill="#333">{label}</text>'
        )
        rel_y += 18

    # Build SVG for strength (line widths)
    str_y = rel_y + 8
    str_svg = (
        f'<text x="4" y="{str_y}" font-size="11" font-weight="bold" fill="#333">'
        f'Strength</text>'
    )
    str_y += 16
    for label, width in strength_styles:
        str_svg += (
            f'<line x1="4" y1="{str_y}" x2="40" y2="{str_y}" '
            f'stroke="#2ca02c" stroke-width="{width}"/>'
            f'<text x="46" y="{str_y + 4}" font-size="11" fill="#333">{label}</text>'
        )
        str_y += 18

    total_height = str_y + 8

    return f"""
<div style="
    position: absolute; top: 10px; left: 10px;
    background: rgba(255,255,255,0.92);
    border: 1px solid #ccc; border-radius: 6px;
    padding: 6px 8px; z-index: 1000;
    pointer-events: none; box-shadow: 0 1px 4px rgba(0,0,0,0.15);
">
  <svg width="130" height="{total_height}" xmlns="http://www.w3.org/2000/svg">
    <text x="4" y="12" font-size="11" font-weight="bold" fill="#333">Nodes</text>
    {node_svg}
    {rel_svg}
    {str_svg}
  </svg>
</div>"""
