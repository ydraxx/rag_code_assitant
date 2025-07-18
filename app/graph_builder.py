import networkx as nx
from typing import List
from langchain_core.documents import Document

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_chunk(self, doc: Document):
        chunk_id = doc.metadata["hash"]
        file_path = doc.metadata["file_path"]
        namespace = doc.metadata.get("namespace", "")
        current_class = doc.metadata.get("class", "")

        for func in doc.metadata.get("defined_functions", []):
            fq_name = f"{file_path}::{namespace}::{current_class}::{func}"
            self.graph.add_node(fq_name, type="function", file=file_path, class_=current_class, namespace=namespace)

        for used_func in doc.metadata.get("used_functions", []):
            # Hypothèse : tu as déjà du code pour désambiguiser `used_func` (ex: ajout du contexte)
            used_node = f"{file_path}::{used_func}"
            self.graph.add_node(used_node, type="used_function")
            for defined_func in doc.metadata.get("defined_functions", []):
                defined_node = f"{file_path}::{namespace}::{current_class}::{defined_func}"
                self.graph.add_edge(defined_node, used_node, type="CALLS")

    def export(self, path="code_graph.gml"):
        nx.write_gml(self.graph, path)
