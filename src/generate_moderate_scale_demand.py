import pandas as pd
import numpy as np
import osmnx as ox
import networkx as nx
from collections import defaultdict

def get_demand_multiplier(current_time_minutes):
    """
    Get the demand multiplier for a given time of day.
    """
    demand_patterns = {
        "night_early": {"start": 0, "end": 360, "multiplier": 0.2},
        "morning_quiet": {"start": 360, "end": 480, "multiplier": 0.4},
        "morning_peak": {"start": 480, "end": 600, "multiplier": 1.8},
        "mid_morning": {"start": 600, "end": 720, "multiplier": 1.2},
        "lunch_peak": {"start": 720, "end": 780, "multiplier": 1.6},
        "afternoon": {"start": 780, "end": 1020, "multiplier": 1.0},
        "evening_peak": {"start": 1020, "end": 1140, "multiplier": 1.5},
        "evening": {"start": 1140, "end": 1320, "multiplier": 0.8},
        "night_late": {"start": 1320, "end": 1440, "multiplier": 0.3}
    }
    
    for period_name, period_data in demand_patterns.items():
        if period_data["start"] <= current_time_minutes < period_data["end"]:
            return period_data["multiplier"]
    
    return 1.0

def sample_zone_nodes(G_walk, hub_nodes_df, n_samples_per_zone=120):
    """
    Sample random delivery points within each zone's walking network.
    """
    zone_delivery_nodes = {}
    
    for _, row in hub_nodes_df.iterrows():
        zone = row['hub']
        hub_node = row['walk_node']
        
        print(f"Sampling delivery points for {zone}...")
        
        try:
            # Get subgraph within 800m of hub for realistic delivery radius
            subgraph = nx.ego_graph(G_walk, hub_node, radius=800, distance='length')
            available_nodes = list(subgraph.nodes())
            
            if hub_node in available_nodes:
                available_nodes.remove(hub_node)
            
            if len(available_nodes) >= n_samples_per_zone:
                sampled_nodes = np.random.choice(available_nodes, n_samples_per_zone, replace=False)
            else:
                sampled_nodes = np.random.choice(available_nodes, n_samples_per_zone, replace=True)
            
            zone_delivery_nodes[zone] = list(sampled_nodes)
            print(f"  -> Sampled {len(sampled_nodes)} delivery points")
            
        except Exception as e:
            print(f"  -> Warning: Could not sample for {zone}, using nearby nodes. Error: {e}")
            try:
                nearby_nodes = [n for n in G_walk.nodes() 
                               if nx.shortest_path_length(G_walk, hub_node, n, weight='length') <= 800]
                if hub_node in nearby_nodes:
                    nearby_nodes.remove(hub_node)
                
                if len(nearby_nodes) > 0:
                    sampled_nodes = np.random.choice(nearby_nodes, 
                                                   min(n_samples_per_zone, len(nearby_nodes)), 
                                                   replace=len(nearby_nodes) < n_samples_per_zone)
                    zone_delivery_nodes[zone] = list(sampled_nodes)
                else:
                    zone_delivery_nodes[zone] = [hub_node]
                    print(f"  -> Warning: Using hub node as fallback for {zone}")
            except:
                zone_delivery_nodes[zone] = [hub_node]
                print(f"  -> Error: Using hub node as fallback for {zone}")
    
    return zone_delivery_nodes

def generate_moderate_scale_demand(G_walk, hub_nodes_df, output_path="../data/raw/demand_synthetic.csv"):
    """
    Generate synthetic demand with MODERATE SCALE (550 packages/day) and peak patterns.
    """
    
    # 1. Sample delivery points for each zone
    zone_delivery_nodes = sample_zone_nodes(G_walk, hub_nodes_df, n_samples_per_zone=120)
    
    # 2. MODERATE SCALE demand parameters (550 total packages)
    daily_volumes = {
        "Centrum": 275,       # 50% of 550 (main commercial center)
        "Blixembosch": 165,   # 30% of 550 (large residential)
        "Meerhoven": 110      # 20% of 550 (smaller residential)
    }
    
    print(f"MODERATE SCALE DEMAND GENERATION")
    print(f"Total daily packages: {sum(daily_volumes.values())}")
    print(f"Zone distribution:")
    for zone, volume in daily_volumes.items():
        pct = (volume / sum(daily_volumes.values())) * 100
        print(f"  {zone}: {volume} packages ({pct:.0f}%)")
    
    within_pct = 0.70   # 70% same zone
    cross_pct = 0.20    # 20% cross zone  
    external_pct = 0.10 # 10% external
    
    classA_pct = 0.80   # 80% Class A (robots)
    classB_pct = 0.20   # 20% Class B (bikes)
    
    # 3. Enhanced time windows with peak patterns
    time_windows = [
        (360, 480, 0.05),   # 06:00–08:00, 5% (quiet morning)
        (480, 600, 0.25),   # 08:00–10:00, 25% (morning peak)
        (600, 720, 0.15),   # 10:00–12:00, 15% (mid-morning)
        (720, 780, 0.12),   # 12:00–13:00, 12% (lunch peak)
        (780, 1020, 0.20),  # 13:00–17:00, 20% (afternoon)
        (1020, 1140, 0.18), # 17:00–19:00, 18% (evening peak)
        (1140, 1320, 0.05)  # 19:00–22:00, 5% (evening)
    ]
    
    def sample_realistic_request_times(num_parcels, windows):
        """Sample request times with peak-aware distribution."""
        times = []
        for start_min, end_min, frac in windows:
            count = int(round(num_parcels * frac))
            # Sample within the window
            sampled = np.random.randint(start_min, end_min, size=count)
            
            # Apply peak multiplier to determine if parcel actually gets requested
            filtered_times = []
            for time_min in sampled:
                multiplier = get_demand_multiplier(time_min)
                # Higher multiplier = higher chance of generating this parcel
                if np.random.random() < min(multiplier / 2.0, 1.0):
                    filtered_times.append(time_min)
            
            times.extend(filtered_times)
        
        # Ensure we have enough parcels by adding more during peak hours if needed
        while len(times) < num_parcels:
            # Add more parcels during peak hours (morning and evening)
            peak_hour = np.random.choice([540, 570, 1080, 1110])  # 9 AM, 9:30 AM, 6 PM, 6:30 PM
            times.append(peak_hour + np.random.randint(-30, 30))
        
        # If we have too many, randomly remove some
        if len(times) > num_parcels:
            times = np.random.choice(times, num_parcels, replace=False)
        
        np.random.shuffle(times)
        return np.array(times)
    
    # 4. Generate parcels with realistic destinations AND peak timing
    rows = []
    parcel_id = 0
    
    print(f"\nGenerating demand with peak patterns...")
    
    for zone, total in daily_volumes.items():
        print(f"\nGenerating {total} parcels for {zone}...")
        
        delivery_nodes = zone_delivery_nodes[zone]
        
        # Same-zone deliveries
        same_zone_count = int(total * within_pct)
        times_same = sample_realistic_request_times(same_zone_count, time_windows)
        
        print(f"  Same-zone deliveries: {same_zone_count}")
        
        for t in times_same:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_node = np.random.choice(delivery_nodes)
            
            # Add urgency based on time of day
            hour = int(t // 60)
            if hour in [8, 9, 12, 17, 18]:  # Peak hours
                urgency = "high" if np.random.random() < 0.6 else "normal"
            else:
                urgency = "normal"
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": zone,
                "destination": zone,
                "dest_node": dest_node,
                "size_class": size,
                "request_time": int(t),
                "urgency": urgency,
                "peak_multiplier": get_demand_multiplier(t)
            })
        
        # Cross-zone deliveries
        cross_zone_count = int(total * cross_pct)
        times_cross = sample_realistic_request_times(cross_zone_count, time_windows)
        dest_choices = [z for z in daily_volumes.keys() if z != zone]
        
        print(f"  Cross-zone deliveries: {cross_zone_count}")
        
        for t in times_cross:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_zone = np.random.choice(dest_choices)
            dest_node = np.random.choice(zone_delivery_nodes[dest_zone])
            
            hour = int(t // 60)
            urgency = "high" if hour in [8, 9, 12, 17, 18] and np.random.random() < 0.6 else "normal"
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": zone,
                "destination": dest_zone,
                "dest_node": dest_node,
                "size_class": size,
                "request_time": int(t),
                "urgency": urgency,
                "peak_multiplier": get_demand_multiplier(t)
            })
        
        # External deliveries
        external_zone_count = total - same_zone_count - cross_zone_count
        times_ext = sample_realistic_request_times(external_zone_count, time_windows)
        
        print(f"  External deliveries: {external_zone_count}")
        
        for t in times_ext:
            parcel_id += 1
            size = np.random.choice(["A", "B"], p=[classA_pct, classB_pct])
            dest_node = np.random.choice(delivery_nodes)
            
            hour = int(t // 60)
            urgency = "high" if hour in [8, 9, 12, 17, 18] and np.random.random() < 0.4 else "normal"
            
            rows.append({
                "parcel_id": parcel_id,
                "origin": "External",
                "destination": zone,
                "dest_node": dest_node,
                "size_class": size,
                "request_time": int(t),
                "urgency": urgency,
                "peak_multiplier": get_demand_multiplier(t)
            })
    
    # 5. Create DataFrame and shuffle
    demand_df = pd.DataFrame(rows)
    demand_df = demand_df.sort_values("request_time").reset_index(drop=True)
    
    # 6. Print peak analysis
    print(f"\nPEAK PATTERN ANALYSIS:")
    print(f"Total parcels generated: {len(demand_df)}")
    
    # Group by hour to show distribution
    demand_df['hour'] = demand_df['request_time'] // 60
    hourly_counts = demand_df.groupby('hour').size()
    
    peak_hours = hourly_counts.nlargest(3)
    quiet_hours = hourly_counts.nsmallest(3)
    
    print(f"Busiest hours:")
    for hour, count in peak_hours.items():
        print(f"   {hour:02d}:00 - {count} parcels")
    
    print(f"Quietest hours:")
    for hour, count in quiet_hours.items():
        print(f"   {hour:02d}:00 - {count} parcels")
    
    # Urgency distribution
    urgency_counts = demand_df['urgency'].value_counts()
    print(f"\nUrgency distribution:")
    for urgency, count in urgency_counts.items():
        print(f"   {urgency}: {count} parcels ({count/len(demand_df)*100:.1f}%)")
    
    # Delivery type distribution
    same_zone = demand_df[demand_df['origin'] == demand_df['destination']]
    cross_zone = demand_df[(demand_df['origin'] != demand_df['destination']) & (demand_df['origin'] != 'External')]
    external = demand_df[demand_df['origin'] == 'External']
    
    print(f"\nDelivery type distribution:")
    print(f"   Same-zone: {len(same_zone)} parcels ({len(same_zone)/len(demand_df)*100:.1f}%)")
    print(f"   Cross-zone: {len(cross_zone)} parcels ({len(cross_zone)/len(demand_df)*100:.1f}%)")
    print(f"   External: {len(external)} parcels ({len(external)/len(demand_df)*100:.1f}%)")
    
    # 7. Save to CSV
    demand_df.to_csv(output_path, index=False)
    print(f"\nGenerated {len(demand_df)} parcels saved to {output_path}")
    
    return demand_df

if __name__ == "__main__":
    # Load networks and generate moderate scale demand with peak patterns
    print("Loading networks...")
    G_walk = ox.load_graphml("../data/raw/walk_network.graphml")
    hub_nodes_df = pd.read_csv("../data/processed/hub_nodes.csv")
    
    print("Generating MODERATE SCALE demand with peak patterns...")
    print("="*60)
    demand_df = generate_moderate_scale_demand(G_walk, hub_nodes_df)
    print("Done!")