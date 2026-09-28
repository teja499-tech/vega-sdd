"""Compatibility wrapper. Graphify owns retrieval; this module no longer builds an ID dump."""
from .graphify_index import graph_context, query_knowledge_graph, refresh_knowledge_graph

refresh_graph = refresh_knowledge_graph

__all__ = ["graph_context", "query_knowledge_graph", "refresh_graph", "refresh_knowledge_graph"]
