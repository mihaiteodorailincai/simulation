import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def analyze_peak_patterns_in_data(csv_path="../data/raw/demand_synthetic.csv"):
    """
    Analyze the generated demand data to visualize peak patterns.
    """
    
    # Load the generated demand data
    print("Loading generated demand data...")
    demand_df = pd.read_csv(csv_path)
    
    print(f"Total parcels: {len(demand_df)}")
    print(f"Columns: {list(demand_df.columns)}")
    print(f"\nFirst few rows:")
    print(demand_df.head())
    
    # Convert request_time to hours for analysis
    demand_df['hour'] = demand_df['request_time'] // 60
    demand_df['time_label'] = demand_df['hour'].apply(lambda x: f"{x:02d}:00")
    
    # Create visualizations
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # 1. Hourly distribution of all parcels
    ax1 = axes[0, 0]
    hourly_counts = demand_df['hour'].value_counts().sort_index()
    ax1.bar(hourly_counts.index, hourly_counts.values, alpha=0.7, color='skyblue')
    ax1.set_title('Total Parcels by Hour', fontweight='bold')
    ax1.set_xlabel('Hour of Day')
    ax1.set_ylabel('Number of Parcels')
    ax1.grid(True, alpha=0.3)
    
    # Highlight peak hours
    peak_hours = [8, 9, 12, 17, 18]
    for hour in peak_hours:
        if hour in hourly_counts.index:
            ax1.bar(hour, hourly_counts[hour], color='orange', alpha=0.8)
    
    # 2. Parcels by zone and hour (using origin as zone)
    ax2 = axes[0, 1]
    
    # Use origin as the zone for analysis
    demand_df['zone'] = demand_df['origin']
    zone_hour_counts = demand_df.groupby(['zone', 'hour']).size().unstack(fill_value=0)
    
    # Plot each zone
    for zone in zone_hour_counts.index:
        ax2.plot(zone_hour_counts.columns, zone_hour_counts.loc[zone], 
                marker='o', label=zone, linewidth=2)
    
    ax2.set_title('Parcels by Zone and Hour', fontweight='bold')
    ax2.set_xlabel('Hour of Day')
    ax2.set_ylabel('Number of Parcels')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Urgency distribution by hour
    ax3 = axes[0, 2]
    if 'urgency' in demand_df.columns:
        urgency_by_hour = demand_df.groupby(['hour', 'urgency']).size().unstack(fill_value=0)
        
        if 'high' in urgency_by_hour.columns and 'normal' in urgency_by_hour.columns:
            ax3.bar(urgency_by_hour.index, urgency_by_hour['normal'], 
                   label='Normal', alpha=0.7, color='lightblue')
            ax3.bar(urgency_by_hour.index, urgency_by_hour['high'], 
                   bottom=urgency_by_hour['normal'], label='High', alpha=0.7, color='red')
        else:
            urgency_by_hour.plot(kind='bar', stacked=True, ax=ax3, alpha=0.7)
        
        ax3.set_title('Urgency Distribution by Hour', fontweight='bold')
        ax3.set_xlabel('Hour of Day')
        ax3.set_ylabel('Number of Parcels')
        ax3.legend()
    else:
        ax3.text(0.5, 0.5, 'No urgency data available', 
                transform=ax3.transAxes, ha='center', va='center')
        ax3.set_title('Urgency Distribution by Hour', fontweight='bold')
    
    # 4. Peak multiplier effect (if available)
    ax4 = axes[1, 0]
    if 'peak_multiplier' in demand_df.columns:
        multiplier_by_hour = demand_df.groupby('hour')['peak_multiplier'].mean()
        ax4.plot(multiplier_by_hour.index, multiplier_by_hour.values, 
                'ro-', linewidth=3, markersize=8)
        ax4.set_title('Peak Multiplier by Hour', fontweight='bold')
        ax4.set_xlabel('Hour of Day')
        ax4.set_ylabel('Average Peak Multiplier')
        ax4.grid(True, alpha=0.3)
    else:
        ax4.text(0.5, 0.5, 'No peak multiplier data available', 
                transform=ax4.transAxes, ha='center', va='center')
        ax4.set_title('Peak Multiplier by Hour', fontweight='bold')
    
    # 5. Same-zone vs Cross-zone distribution
    ax5 = axes[1, 1]
    
    # Filter out External origins for cleaner analysis
    non_external = demand_df[demand_df['origin'] != 'External']
    same_zone = non_external[non_external['origin'] == non_external['destination']]
    cross_zone = non_external[non_external['origin'] != non_external['destination']]
    
    same_zone_hourly = same_zone['hour'].value_counts().sort_index()
    cross_zone_hourly = cross_zone['hour'].value_counts().sort_index()
    
    # Align indices
    all_hours = set(same_zone_hourly.index) | set(cross_zone_hourly.index)
    same_zone_hourly = same_zone_hourly.reindex(sorted(all_hours), fill_value=0)
    cross_zone_hourly = cross_zone_hourly.reindex(sorted(all_hours), fill_value=0)
    
    ax5.bar(same_zone_hourly.index, same_zone_hourly.values, 
           alpha=0.7, label='Same Zone', color='green')
    ax5.bar(cross_zone_hourly.index, cross_zone_hourly.values, 
           bottom=same_zone_hourly.values, alpha=0.7, label='Cross Zone', color='purple')
    
    ax5.set_title('Same-Zone vs Cross-Zone by Hour', fontweight='bold')
    ax5.set_xlabel('Hour of Day')
    ax5.set_ylabel('Number of Parcels')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. Summary statistics
    ax6 = axes[1, 2]
    ax6.axis('off')
    
    # Calculate key statistics
    busiest_hours = hourly_counts.nlargest(3)
    quietest_hours = hourly_counts.nsmallest(3)
    peak_ratio = hourly_counts.iloc[8:10].mean() / hourly_counts.iloc[2:6].mean() if len(hourly_counts) > 10 else 1
    
    stats_text = f"""
PEAK PATTERN STATISTICS

Busiest Hours:
{chr(10).join([f"  {hour:02d}:00 - {count} parcels" for hour, count in busiest_hours.items()])}

Quietest Hours:
{chr(10).join([f"  {hour:02d}:00 - {count} parcels" for hour, count in quietest_hours.items()])}

Peak-to-Off-Peak Ratio: {peak_ratio:.1f}x

Total Parcels: {len(demand_df)}
Time Span: {demand_df['hour'].min():02d}:00 - {demand_df['hour'].max():02d}:00
"""
    
    if 'urgency' in demand_df.columns:
        urgency_stats = demand_df['urgency'].value_counts()
        stats_text += f"\nUrgency Distribution:\n"
        for urgency, count in urgency_stats.items():
            pct = count / len(demand_df) * 100
            stats_text += f"  {urgency}: {count} ({pct:.1f}%)\n"
    
    ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes, 
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))
    
    plt.tight_layout()
    plt.savefig('peak_analysis_generated_data.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\nPeak analysis visualization saved as 'peak_analysis_generated_data.png'")
    
    return demand_df, hourly_counts

def compare_with_theoretical_peaks():
    """
    Compare the generated data with the theoretical peak patterns.
    """
    
    # Load generated data
    demand_df = pd.read_csv("../data/raw/demand_synthetic.csv")
    demand_df['hour'] = demand_df['request_time'] // 60
    actual_hourly = demand_df['hour'].value_counts().sort_index()
    
    # Generate theoretical distribution
    from peak_demand_analysis import generate_hourly_demand_profile
    
    base_volumes = {"Centrum": 200, "Blixembosch": 120, "Meerhoven": 80}
    theoretical_df = generate_hourly_demand_profile(base_volumes)
    theoretical_hourly = theoretical_df.groupby('hour')['peak_demand'].sum()
    
    # Plot comparison
    plt.figure(figsize=(12, 6))
    
    plt.subplot(1, 2, 1)
    plt.plot(theoretical_hourly.index, theoretical_hourly.values, 
            'b-o', label='Theoretical Pattern', linewidth=3, markersize=8)
    plt.plot(actual_hourly.index, actual_hourly.values, 
            'r-s', label='Generated Data', linewidth=3, markersize=8)
    plt.title('Theoretical vs Generated Demand Patterns', fontweight='bold')
    plt.xlabel('Hour of Day')
    plt.ylabel('Packages per Hour')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.subplot(1, 2, 2)
    # Calculate correlation
    aligned_theoretical = theoretical_hourly.reindex(actual_hourly.index, fill_value=0)
    correlation = np.corrcoef(aligned_theoretical.values, actual_hourly.values)[0, 1]
    
    plt.scatter(aligned_theoretical.values, actual_hourly.values, alpha=0.7, s=100)
    plt.plot([0, max(aligned_theoretical.values)], [0, max(aligned_theoretical.values)], 'r--', alpha=0.5)
    plt.title(f'Correlation: {correlation:.3f}', fontweight='bold')
    plt.xlabel('Theoretical Packages/Hour')
    plt.ylabel('Generated Packages/Hour')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('theoretical_vs_generated_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"Correlation between theoretical and generated patterns: {correlation:.3f}")
    print(f"Comparison visualization saved as 'theoretical_vs_generated_comparison.png'")

if __name__ == "__main__":
    print("ANALYZING PEAK PATTERNS IN GENERATED DATA")
    print("="*50)
    
    # Analyze the generated data
    demand_data, hourly_distribution = analyze_peak_patterns_in_data()
    
    print("\n" + "="*50)
    print("COMPARING WITH THEORETICAL PATTERNS")
    print("="*50)
    
    # Compare with theoretical patterns
    try:
        compare_with_theoretical_peaks()
    except ImportError:
        print("Could not import peak_demand_analysis module for comparison")
        print("Run this from the same directory as peak_demand_analysis.py")