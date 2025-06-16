import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

def create_peak_demand_patterns():
    """
    Create realistic peak vs off-peak demand patterns for a 15-minute city.
    """
    
    # Define time periods with multipliers (minutes from midnight)
    demand_patterns = {
        "night_early": {"start": 0, "end": 360, "multiplier": 0.2, "name": "Early Night (12-6 AM)"},
        "morning_quiet": {"start": 360, "end": 480, "multiplier": 0.4, "name": "Early Morning (6-8 AM)"},
        "morning_peak": {"start": 480, "end": 600, "multiplier": 1.8, "name": "Morning Peak (8-10 AM)"},
        "mid_morning": {"start": 600, "end": 720, "multiplier": 1.2, "name": "Mid Morning (10-12 PM)"},
        "lunch_peak": {"start": 720, "end": 780, "multiplier": 1.6, "name": "Lunch Peak (12-1 PM)"},
        "afternoon": {"start": 780, "end": 1020, "multiplier": 1.0, "name": "Afternoon (1-5 PM)"},
        "evening_peak": {"start": 1020, "end": 1140, "multiplier": 1.5, "name": "Evening Peak (5-7 PM)"},
        "evening": {"start": 1140, "end": 1320, "multiplier": 0.8, "name": "Evening (7-10 PM)"},
        "night_late": {"start": 1320, "end": 1440, "multiplier": 0.3, "name": "Late Night (10-12 PM)"}
    }
    
    return demand_patterns

def get_demand_multiplier(current_time_minutes):
    """
    Get the demand multiplier for a given time of day.
    
    Args:
        current_time_minutes: Minutes since midnight (0-1439)
    
    Returns:
        float: Demand multiplier (0.2 to 1.8)
    """
    patterns = create_peak_demand_patterns()
    
    for period_name, period_data in patterns.items():
        if period_data["start"] <= current_time_minutes < period_data["end"]:
            return period_data["multiplier"]
    
    # Default fallback
    return 1.0

def generate_hourly_demand_profile(base_daily_volumes):
    """
    Generate hourly demand profile for the entire day.
    
    Args:
        base_daily_volumes: dict like {"Centrum": 200, "Blixembosch": 120, "Meerhoven": 80}
    
    Returns:
        DataFrame with hourly demand for each zone
    """
    patterns = create_peak_demand_patterns()
    
    # Create hourly breakdown
    hours = range(24)
    zones = list(base_daily_volumes.keys())
    
    hourly_data = []
    
    for hour in hours:
        time_minutes = hour * 60
        multiplier = get_demand_multiplier(time_minutes)
        
        for zone, base_volume in base_daily_volumes.items():
            # Base hourly volume (assuming even distribution)
            base_hourly = base_volume / 24
            # Apply peak multiplier
            peak_hourly = base_hourly * multiplier
            
            hourly_data.append({
                'hour': hour,
                'zone': zone,
                'base_demand': base_hourly,
                'peak_demand': peak_hourly,
                'multiplier': multiplier,
                'time_label': f"{hour:02d}:00"
            })
    
    return pd.DataFrame(hourly_data)

def visualize_demand_patterns(hourly_df, save_plots=True):
    """
    Create comprehensive visualizations of demand patterns.
    """
    
    # Set up the plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # 1. Overall demand multiplier throughout the day
    ax1 = plt.subplot(2, 3, 1)
    unique_hours = hourly_df[['hour', 'multiplier']].drop_duplicates()
    plt.plot(unique_hours['hour'], unique_hours['multiplier'], 'o-', linewidth=3, markersize=8)
    plt.title('Demand Multiplier Throughout Day', fontsize=14, fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('Demand Multiplier')
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24, 2))
    
    # Add period labels
    patterns = create_peak_demand_patterns()
    colors = ['red', 'orange', 'green', 'blue', 'purple']
    for i, (period_name, data) in enumerate(patterns.items()):
        start_hour = data['start'] // 60
        end_hour = data['end'] // 60
        plt.axvspan(start_hour, end_hour, alpha=0.2, color=colors[i % len(colors)])
    
    # 2. Hourly demand by zone
    ax2 = plt.subplot(2, 3, 2)
    for zone in hourly_df['zone'].unique():
        zone_data = hourly_df[hourly_df['zone'] == zone]
        plt.plot(zone_data['hour'], zone_data['peak_demand'], 'o-', 
                label=zone, linewidth=2, markersize=6)
    
    plt.title('Hourly Demand by Zone', fontsize=14, fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('Packages per Hour')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24, 2))
    
    # 3. Stacked area chart
    ax3 = plt.subplot(2, 3, 3)
    pivot_data = hourly_df.pivot(index='hour', columns='zone', values='peak_demand')
    plt.stackplot(pivot_data.index, *[pivot_data[col] for col in pivot_data.columns], 
                 labels=pivot_data.columns, alpha=0.8)
    plt.title('Cumulative Demand by Zone', fontsize=14, fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('Cumulative Packages per Hour')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)
    
    # 4. Heatmap of demand intensity
    ax4 = plt.subplot(2, 3, 4)
    heatmap_data = hourly_df.pivot(index='zone', columns='hour', values='peak_demand')
    sns.heatmap(heatmap_data, annot=False, cmap='YlOrRd', cbar_kws={'label': 'Packages/Hour'})
    plt.title('Demand Intensity Heatmap', fontsize=14, fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('Zone')
    
    # 5. Peak vs Off-Peak comparison
    ax5 = plt.subplot(2, 3, 5)
    
    # Define peak and off-peak hours
    peak_hours = [8, 9, 12, 17, 18]  # Morning, lunch, evening peaks
    off_peak_hours = [2, 3, 4, 14, 15, 21, 22]  # Quiet periods
    
    peak_data = hourly_df[hourly_df['hour'].isin(peak_hours)].groupby('zone')['peak_demand'].mean()
    off_peak_data = hourly_df[hourly_df['hour'].isin(off_peak_hours)].groupby('zone')['peak_demand'].mean()
    
    x = np.arange(len(peak_data.index))
    width = 0.35
    
    plt.bar(x - width/2, peak_data.values, width, label='Peak Hours', alpha=0.8)
    plt.bar(x + width/2, off_peak_data.values, width, label='Off-Peak Hours', alpha=0.8)
    
    plt.title('Peak vs Off-Peak Demand', fontsize=14, fontweight='bold')
    plt.xlabel('Zone')
    plt.ylabel('Average Packages per Hour')
    plt.xticks(x, peak_data.index)
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 6. Delivery urgency by time of day
    ax6 = plt.subplot(2, 3, 6)
    
    # Simulate urgency based on time of day
    urgency_data = []
    for hour in range(24):
        if hour in [8, 9, 12, 17, 18]:  # Peak hours
            urgent_pct = 0.6  # 60% urgent during peaks
        elif hour in [10, 11, 13, 14, 15, 16]:  # Business hours
            urgent_pct = 0.3  # 30% urgent during business
        else:  # Off hours
            urgent_pct = 0.1  # 10% urgent at night
        
        urgency_data.append({'hour': hour, 'urgent_percentage': urgent_pct * 100})
    
    urgency_df = pd.DataFrame(urgency_data)
    plt.plot(urgency_df['hour'], urgency_df['urgent_percentage'], 'ro-', linewidth=3, markersize=8)
    plt.title('Delivery Urgency by Hour', fontsize=14, fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('% Urgent Deliveries')
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24, 2))
    plt.ylim(0, 70)
    
    plt.tight_layout()
    
    if save_plots:
        plt.savefig('demand_patterns_analysis.png', dpi=300, bbox_inches='tight')
        print("Saved demand patterns visualization as 'demand_patterns_analysis.png'")
    
    plt.show()
    
    return fig

def create_summary_statistics(hourly_df):
    """
    Create summary statistics for the demand patterns.
    """
    
    print("="*60)
    print("PEAK VS OFF-PEAK DEMAND ANALYSIS")
    print("="*60)
    
    total_daily = hourly_df.groupby('zone')['peak_demand'].sum()
    
    print(f"\nDAILY TOTALS:")
    for zone, total in total_daily.items():
        print(f"  {zone}: {total:.0f} packages/day")
    
    print(f"\nPEAK PERIODS:")
    patterns = create_peak_demand_patterns()
    for period_name, data in patterns.items():
        if data['multiplier'] > 1.2:  # Only show high-demand periods
            start_hour = data['start'] // 60
            end_hour = data['end'] // 60
            print(f"  {data['name']}: {data['multiplier']:.1f}x normal demand")
    
    # Find busiest hour overall
    hourly_totals = hourly_df.groupby('hour')['peak_demand'].sum()
    busiest_hour = hourly_totals.idxmax()
    busiest_demand = hourly_totals.max()
    
    print(f"\nBUSIEST HOUR: {busiest_hour}:00 with {busiest_demand:.0f} total packages")
    
    # Find quietest hour
    quietest_hour = hourly_totals.idxmin()
    quietest_demand = hourly_totals.min()
    
    print(f"QUIETEST HOUR: {quietest_hour}:00 with {quietest_demand:.0f} total packages")
    
    # Peak to off-peak ratio
    peak_avg = hourly_totals.iloc[8:10].mean()  # 8-10 AM
    off_peak_avg = hourly_totals.iloc[2:6].mean()  # 2-6 AM
    ratio = peak_avg / off_peak_avg
    
    print(f"\nPEAK-TO-OFF-PEAK RATIO: {ratio:.1f}x")
    print(f"   Morning peak averages {peak_avg:.0f} packages/hour")
    print(f"   Night period averages {off_peak_avg:.0f} packages/hour")
    
    return {
        'daily_totals': total_daily,
        'busiest_hour': busiest_hour,
        'quietest_hour': quietest_hour,
        'peak_ratio': ratio
    }

def simulate_realistic_day():
    """
    Run a complete simulation showing how demand varies throughout a day.
    """
    
    # Your current volumes
    base_volumes = {
        "Centrum": 200,
        "Blixembosch": 120,
        "Meerhoven": 80
    }
    
    print("SIMULATING 24-HOUR DEMAND PATTERNS")
    print("="*50)
    
    # Generate hourly profile
    hourly_df = generate_hourly_demand_profile(base_volumes)
    
    # Create visualizations
    fig = visualize_demand_patterns(hourly_df)
    
    # Print summary statistics
    stats = create_summary_statistics(hourly_df)
    
    print(f"\nINSIGHTS FOR YOUR SIMULATION:")
    print(f"  • Use time-dependent demand in your ParcelAgent generation")
    print(f"  • Scale robot/bike availability based on predicted demand")
    print(f"  • Implement priority queues for peak hours")
    print(f"  • Consider dynamic pricing during high-demand periods")
    
    return hourly_df, stats

if __name__ == "__main__":
    # Run the complete analysis
    hourly_data, statistics = simulate_realistic_day()
    
    # Show sample implementation for your existing code
    print(f"\n" + "="*60)
    print("IMPLEMENTATION FOR YOUR SIMULATION")
    print("="*60)
    
    print("""
    # Add this to your demand generation:
    
    def generate_time_based_demand(parcel_request_time):
        base_multiplier = get_demand_multiplier(parcel_request_time)
        
        # Adjust parcel generation probability
        if random.random() < base_multiplier / 2.0:  # Scale probability
            return True  # Generate this parcel
        return False  # Skip this parcel
    
    # Add this to your model.py step() method:
    
    def step(self):
        current_multiplier = get_demand_multiplier(self.current_time)
        
        # Scale vehicle availability based on demand
        if current_multiplier > 1.5:  # Peak period
            # Deploy more vehicles or increase speed
            peak_mode = True
        elif current_multiplier < 0.5:  # Off-peak
            # Reduce active vehicles to save costs
            peak_mode = False
    """)