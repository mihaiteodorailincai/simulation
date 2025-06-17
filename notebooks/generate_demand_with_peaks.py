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

def sample_zone_nodes(G_walk, hub_nodes_df, n_samples_per_zone=50):
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

def sample_realistic_request_times(num_parcels, windows):
    """
    Sample request times with peak-aware distribution.
    FIXED VERSION: Generates exactly num_parcels without dropping any.
    
    This function uses weighted sampling to create realistic peak patterns
    while ensuring we generate exactly the target number of parcels.
    """
    
    # Build a minute-by-minute probability distribution based on multipliers
    minute_weights = []
    
    # For each minute of the day, calculate its weight based on the multiplier
    for minute in range(0, 1440):  # 0 to 1439 minutes in a day
        weight = get_demand_multiplier(minute)
        minute_weights.append(weight)
    
    # Normalize weights to create probabilities
    total_weight = sum(minute_weights)
    probabilities = [w / total_weight for w in minute_weights]
    
    # Sample exactly num_parcels times based on the probability distribution
    # This ensures peak hours get more parcels but we always get the exact count
    sampled_times = np.random.choice(
        range(0, 1440),  # All minutes in the day
        size=num_parcels,
        p=probabilities,
        replace=True
    )
    
    # Filter to only keep times within our operating window (6 AM to 10 PM)
    # and resample any that fall outside
    operating_start = 360  # 6 AM
    operating_end = 1320   # 10 PM
    
    filtered_times = []
    for time in sampled_times:
        if operating_start <= time <= operating_end:
            filtered_times.append(time)
    
    # If we lost some due to operating hours, resample from peak periods
    while len(filtered_times) < num_parcels:
        # Sample from weighted distribution within operating hours only
        operating_weights = minute_weights[operating_start:operating_end]
        operating_probs = [w / sum(operating_weights) for w in operating_weights]
        
        additional_time = np.random.choice(
            range(operating_start, operating_end),
            p=operating_probs
        )
        filtered_times.append(additional_time)
    
    # Ensure we have exactly the right number
    filtered_times = filtered_times[:num_parcels]
    
    # Convert to numpy array and shuffle
    result = np.array(filtered_times)
    np.random.shuffle(result)
    
    return result

def generate_realistic_demand_with_peaks(G_walk, hub_nodes_df, output_path="../data/raw/demand_synthetic.csv"):
    """
    Generate synthetic demand with realistic delivery addresses AND peak patterns.
    FIXED VERSION: Generates EXACTLY the target number of parcels.
    """
    
    # 1. Sample delivery points for each zone
    zone_delivery_nodes = sample_zone_nodes(G_walk, hub_nodes_df, n_samples_per_zone=100)
    
    # 2. Base demand parameters - THESE WILL BE EXACT COUNTS
    daily_volumes = {
        "Centrum": 275,
        "Blixembosch": 165,
        "Meerhoven": 110
    }
    
    # Calculate expected total
    expected_total = sum(daily_volumes.values())
    print(f"\n{'='*60}")
    print(f"DEMAND GENERATION TARGET: {expected_total} parcels")
    print(f"{'='*60}")
    
    within_pct = 0.80   # 70% same zone
    cross_pct = 0.15    # 20% cross zone  
    external_pct = 0.05 # 10% external
    
    classA_pct = 0.80   # 80% Class A (robots)
    classB_pct = 0.20   # 20% Class B (bikes)
    
    # 3. Time windows - used for reporting, not filtering
    time_windows = [
        (360, 480, 0.05),   # 06:00–08:00, 5% (quiet morning)
        (480, 600, 0.25),   # 08:00–10:00, 25% (morning peak)
        (600, 720, 0.15),   # 10:00–12:00, 15% (mid-morning)
        (720, 780, 0.12),   # 12:00–13:00, 12% (lunch peak)
        (780, 1020, 0.20),  # 13:00–17:00, 20% (afternoon)
        (1020, 1140, 0.18), # 17:00–19:00, 18% (evening peak)
        (1140, 1320, 0.05)  # 19:00–22:00, 5% (evening)
    ]
    
    # 4. Generate parcels with realistic destinations AND peak timing
    rows = []
    parcel_id = 0
    parcels_generated = 0
    
    print(f"\nGenerating demand with peak patterns...")
    print(f"Method: Weighted sampling (no parcels dropped)")
    print(f"\nZone breakdown:")
    
    for zone, total in daily_volumes.items():
        zone_start_count = parcels_generated
        
        delivery_nodes = zone_delivery_nodes[zone]
        
        # Calculate exact counts for each delivery type
        same_zone_count = int(total * within_pct)
        cross_zone_count = int(total * cross_pct)
        external_zone_count = total - same_zone_count - cross_zone_count  # Ensures exact total
        
        print(f"\n{zone}: {total} parcels")
        print(f"  Same-zone: {same_zone_count}")
        print(f"  Cross-zone: {cross_zone_count}")
        print(f"  External: {external_zone_count}")
        
        # Same-zone deliveries
        times_same = sample_realistic_request_times(same_zone_count, time_windows)
        
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
            parcels_generated += 1
        
        # Cross-zone deliveries
        dest_choices = [z for z in daily_volumes.keys() if z != zone]
        times_cross = sample_realistic_request_times(cross_zone_count, time_windows)
        
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
            parcels_generated += 1
        
        # External deliveries
        times_ext = sample_realistic_request_times(external_zone_count, time_windows)
        
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
            parcels_generated += 1
        
        zone_total_generated = parcels_generated - zone_start_count
        print(f"  Generated: {zone_total_generated} ✓" if zone_total_generated == total else f"  Generated: {zone_total_generated} ✗ (expected {total})")
    
    # 5. Create DataFrame and sort by request time
    demand_df = pd.DataFrame(rows)
    demand_df = demand_df.sort_values("request_time").reset_index(drop=True)
    
    # 6. Verification and analysis
    print(f"\n{'='*60}")
    print(f"GENERATION SUMMARY")
    print(f"{'='*60}")
    print(f"Expected parcels: {expected_total}")
    print(f"Generated parcels: {len(demand_df)}")
    print(f"Status: {'SUCCESS ✓' if len(demand_df) == expected_total else 'FAILED ✗'}")
    
    # Peak analysis
    demand_df['hour'] = demand_df['request_time'] // 60
    hourly_counts = demand_df.groupby('hour').size()
    
    print(f"\nPEAK PATTERN ANALYSIS:")
    
    # Find peak and off-peak hours
    peak_hours = hourly_counts.nlargest(3)
    quiet_hours = hourly_counts.nsmallest(3)
    
    print(f"\nBusiest hours:")
    for hour, count in peak_hours.items():
        print(f"  {hour:02d}:00 - {count} parcels")
    
    print(f"\nQuietest hours:")
    for hour, count in quiet_hours.items():
        print(f"  {hour:02d}:00 - {count} parcels")
    
    # Calculate peak ratio
    avg_peak = peak_hours.mean()
    avg_quiet = quiet_hours.mean() if quiet_hours.mean() > 0 else 1
    peak_ratio = avg_peak / avg_quiet
    
    print(f"\nPeak-to-quiet ratio: {peak_ratio:.1f}x")
    
    # Urgency distribution
    urgency_counts = demand_df['urgency'].value_counts()
    print(f"\nUrgency distribution:")
    for urgency, count in urgency_counts.items():
        print(f"  {urgency}: {count} parcels ({count/len(demand_df)*100:.1f}%)")
    
    # Visual hourly distribution
    print(f"\nHOURLY DISTRIBUTION:")
    print("Hour | Count | Visual")
    print("-" * 40)
    
    for hour in range(6, 22):  # 6 AM to 10 PM
        count = hourly_counts.get(hour, 0)
        bar = '█' * int(count / 3)  # Scale for display
        print(f"{hour:02d}:00 | {count:4d} | {bar}")
    
    # 7. Save to CSV
    demand_df.to_csv(output_path, index=False)
    print(f"\n{'='*60}")
    print(f"SUCCESS: Generated exactly {len(demand_df)} parcels")
    print(f"Saved to: {output_path}")
    print(f"{'='*60}")
    
    return demand_df

if __name__ == "__main__":
    # Load networks and generate realistic demand with peak patterns
    print("15-MINUTE CITY DELIVERY DEMAND GENERATION")
    print("="*60)
    print("Loading networks...")
    
    try:
        G_walk = ox.load_graphml("../data/raw/walk_network.graphml")
        hub_nodes_df = pd.read_csv("../data/processed/hub_nodes.csv")
        
        print(f"Walk network loaded: {len(G_walk.nodes())} nodes, {len(G_walk.edges())} edges")
        print(f"Hub locations loaded: {len(hub_nodes_df)} hubs")
        
        print("\nGenerating demand with realistic peak patterns...")
        demand_df = generate_realistic_demand_with_peaks(G_walk, hub_nodes_df, "../data/raw/demand_synthetic.csv")
        
        print("\nDemand generation complete!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("Make sure you're running this from the 'src' directory")
        print("and that the network files exist in '../data/'")