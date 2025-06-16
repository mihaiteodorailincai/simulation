import os
import argparse
import pandas as pd
import osmnx as ox

from model import CourierNetworkModel

def main():
    # 9.1 Parse optional command‐line arguments
    parser = argparse.ArgumentParser(description="Run the 15‐minute courier simulation.")
    parser.add_argument("--steps", type=int, default=600, 
                        help="Number of minutes to simulate (default=600).")
    parser.add_argument("--n_robots", type=int, default=5, 
                        help="Number of robots per hub (default=5).")
    parser.add_argument("--n_bikes", type=int, default=2, 
                        help="Number of cargo bikes per hub (default=2).")
    parser.add_argument("--output", type=str, default="results/model_metrics.csv",
                        help="Where to save the DataCollector CSV.")
    args = parser.parse_args()
    
    # 9.2 Load graphs from data/raw
    bike_graph = ox.load_graphml("data/raw/bike_network.graphml")
    walk_graph = ox.load_graphml("data/raw/walk_network.graphml")
    
    # 9.3 Load hub nodes from data/processed
    hub_nodes_df = pd.read_csv("data/processed/hub_nodes.csv")
    
    # 9.4 Create model instance
    model = CourierNetworkModel(
        bike_graph          = bike_graph,
        walk_graph          = walk_graph,
        hub_nodes_df        = hub_nodes_df,
        demand_csv_path     = "data/raw/demand_synthetic.csv",
        n_robots_per_hub    = args.n_robots,
        n_bikes_per_hub     = args.n_bikes,
        robot_capacity      = 1,
        bike_capacity       = 3
    )
    
    # 9.5 Run for specified steps
    for _ in range(args.steps):
        model.step()
    
    # 9.6 Collect and save metrics
    df_metrics = model.datacollector.get_model_vars_dataframe()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df_metrics.to_csv(args.output)
    print(f"Simulation complete. Metrics saved to {args.output}")

if __name__ == "__main__":
    main()