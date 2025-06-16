import networkx as nx

def shortest_path_length_time(G, origin_node, dest_node, speed_mps):
    """
    Returns shortest‐path length (in meters) and time (in seconds) 
    from origin_node to dest_node in graph G,
    given a constant speed (m/s).
    """
    length_m = nx.shortest_path_length(G, origin_node, dest_node, weight="length")
    time_s = length_m / speed_mps if length_m is not None else None
    return length_m, time_s

def shortest_path_route(G, origin_node, dest_node):
    """
    Returns a list of node IDs forming the shortest path (by length) 
    between origin_node and dest_node in graph G.
    """
    path = nx.shortest_path(G, origin_node, dest_node, weight="length")
    return path