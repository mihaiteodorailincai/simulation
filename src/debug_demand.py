#!/usr/bin/env python3
"""
Quick fix script to regenerate demand data with proper delivery addresses.
Run this from your project root directory.
"""

import os
import sys
import pandas as pd
import numpy as np
import osmnx as ox
import networkx as nx
from collections import defaultdict, deque

def generate_quick_demand_fix():
    """Generate demand data with proper dest_node values."""
    
    print("FIXING DEMAND DATA WITH REALISTIC DELIVERY ADDRESSES")
    print("=" * 60)
    
    # Load networks
    print("Loading network data...")
    try:
        G_walk = ox.load_graphml("data/raw/walk_network.graphml")
        hub_nodes_df = pd.read_csv("data/processed/hub_nodes.csv")
        print("Network data loaded successfully")
    except Exception as e:
        print(f"Error loading network data: {e}")
        print("Make sure you're running from the project root directory")
        return False
    
    # Sample delivery nodes for each zone
    print("\nSampling realistic delivery addresses...")
    zone_delivery_nodes = {}
    
    for _, row in hub_nodes_df.iterrows():
        zone = row['hub']
        hub_node = row['walk_node']
        
        print(f"  Sampling for {zone}...")
        
        try:
            # Get nodes within 800m of hub
            subgraph = nx.ego_graph(G_walk, hub_node, radius=800, distance='length')
            available_nodes = list(subgraph.nodes())
            
            # Remove hub node itself
            if hub_node in available_nodes:
                available_nodes.remove(hub_node)
            
            # Sample 100 random delivery addresses
            n_samples = min(100, len(available_nodes))
            if n_samples > 0:
                sampled_nodes = np.random.choice(available_nodes, n_samples, replace=False)
                zone_delivery_nodes[zone] = list(sampled_nodes)
                print(f"    Sampled {len(sampled_nodes)} delivery addresses")
            else:
                # Fallback: use nearby nodes
                nearby_nodes = [n for n in G_walk.nodes() 
                               if nx.shortest_path_length(G_walk, hub_node, n, weight='length') <= 800]
                if hub_node in nearby_nodes:
                    nearby_nodes.remove(hub_node)
                zone_delivery_nodes[zone] = nearby_nodes[:50]
                print(f"    Using {len(zone_delivery_nodes[zone])} nearby nodes as fallback")
                
        except Exception as e:
            print(f"    Error sampling for {zone}: {e}")
            # Emergency fallback
            zone_delivery_nodes[zone] = [hub_node]
    
    # Generate demand with proper addressing
    print("\nGenerating demand data...")
    
    daily_volumes = {
        "Centrum": 200,
        "Blixembosch": 120,
        "Meerhoven": 80
    }
    
    within_pct = 0.70   # Same zone -> robots
    cross_pct = 0.20    # Cross zone -> bikes  
    external_pct = 0.10 # External -> robots
    
    classA_pct = 0.80
    classB_pct = 0.20
    
    # Time windows
    time_windows = [
        (480, 660, 0.50),   # 08:00–11:00, 50%
        (660, 900, 0.30),   # 11:00–15:00, 30%
        (900, 1140, 0.20)   # 15:00–19:00, 20%
    ]
    
    def sample_request_times(num_parcels, windows):
        times = []
        for start_min, end_min, frac in windows:
            count = int(round(num_parcels * frac))
            sampled = np.random.randint(start_min, end_min, size=count)
            times.extend(sampled.tolist())
        
        # Adjust for rounding
        if len(times) < num_parcels:
            extra = num_parcels - len(times)
            times.extend(np.random.randint(windows[0][0], windows[-1][1], size=extra).tolist())
        elif len(times) > num_parcels:
            times = times[:num_parcels]
        
        np.random.shuffle(times)
        return np.array(times)
    
    # Generate parcels
    rows = []
    parcel_id = 0
    
    for zone, total in daily_volumes.items():
        print(f"  Generating {total} parcels for {zone}...")
        
        delivery_nodes = zone_delivery_nodes[zone]
        
        # Same-zone deliveries (robots)
        same_zone_count = int(total * within_pct)
        times_same = sample_request_times(same_zone_count, time_windows)
        
        for t in times_same:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_node = np.random.choice(delivery_nodes)
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": zone,
                "destination": zone,
                "dest_node": int(dest_node),  # Ensure it's an integer
                "size_class": size,
                "request_time": int(t)
            })
        
        # Cross-zone deliveries (bikes)
        cross_zone_count = int(total * cross_pct)
        times_cross = sample_request_times(cross_zone_count, time_windows)
        dest_choices = [z for z in daily_volumes.keys() if z != zone]
        
        for t in times_cross:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_zone = np.random.choice(dest_choices)
            dest_node = np.random.choice(zone_delivery_nodes[dest_zone])
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": zone,
                "destination": dest_zone,
                "dest_node": int(dest_node),
                "size_class": size,
                "request_time": int(t)
            })
        
        # External deliveries (robots)
        external_zone_count = total - same_zone_count - cross_zone_count
        times_ext = sample_request_times(external_zone_count, time_windows)
        
        for t in times_ext:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_node = np.random.choice(delivery_nodes)
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": "External",
                "destination": zone,
                "dest_node": int(dest_node),
                "size_class": size,
                "request_time": int(t)
            })
    
    # Create DataFrame and save
    demand_df = pd.DataFrame(rows)
    demand_df = demand_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Ensure data directory exists
    os.makedirs("data/raw", exist_ok=True)
    
    # Save with backup
    output_path = "data/raw/demand_synthetic.csv"
    if os.path.exists(output_path):
        backup_path = "data/raw/demand_synthetic_backup.csv"
        os.rename(output_path, backup_path)
        print(f"  Backed up old demand file to {backup_path}")
    
    demand_df.to_csv(output_path, index=False)
    
    print(f"\nSUCCESS!")
    print(f"Generated {len(demand_df)} parcels with realistic delivery addresses")
    print(f"Saved to: {output_path}")
    
    # Validate the data
    print(f"\nVALIDATION:")
    same_zone = demand_df[demand_df['origin'] == demand_df['destination']]
    cross_zone = demand_df[(demand_df['origin'] != demand_df['destination']) & (demand_df['origin'] != 'External')]
    external = demand_df[demand_df['origin'] == 'External']
    
    print(f"  Same-zone (robots): {len(same_zone)} parcels ({len(same_zone)/len(demand_df)*100:.1f}%)")
    print(f"  Cross-zone (bikes): {len(cross_zone)} parcels ({len(cross_zone)/len(demand_df)*100:.1f}%)")
    print(f"  External (robots): {len(external)} parcels ({len(external)/len(demand_df)*100:.1f}%)")
    
    # Check dest_node values
    hub_nodes = set(hub_nodes_df['walk_node'].values)
    dest_nodes_are_hubs = demand_df['dest_node'].isin(hub_nodes).sum()
    print(f"  Deliveries to hub nodes: {dest_nodes_are_hubs} (should be 0 for realistic addresses)")
    
    if dest_nodes_are_hubs == 0:
        print(f"  All deliveries have realistic addresses (not hub locations)")
    else:
        print(f"  Some deliveries still go to hub locations")
    
    return True

if __name__ == "__main__":
    if generate_quick_demand_fix():
        print(f"\nNow run your simulation again:")
        print(f"python src/run_simulation.py --steps 840 --n_robots 8 --n_bikes 3")
    else:
        print(f"\nFailed to fix demand data. Check error messages above.")