import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def calculate_sustainability_metrics(model_metrics_df):
    """
    Calculate comprehensive sustainability metrics for the delivery system.
    """
    
    # Vehicle specifications
    robot_specs = {
        'energy_consumption_kwh_per_km': 0.15,  # Electric robots
        'co2_per_kwh': 0.233,  # EU electricity grid average (kg CO2/kWh)
        'capacity': 1,
        'speed_kmh': 5
    }
    
    bike_specs = {
        'energy_consumption_kwh_per_km': 0.025,  # E-cargo bikes (very efficient)
        'co2_per_kwh': 0.233,
        'capacity': 3,
        'speed_kmh': 15
    }
    
    # Traditional delivery comparison (diesel vans)
    traditional_van = {
        'fuel_consumption_l_per_km': 0.08,  # 12.5 km/l
        'co2_per_liter': 2.68,  # kg CO2/liter diesel
        'capacity': 20,
        'speed_kmh': 25
    }
    
    # Calculate sustainability metrics for each time step
    sustainability_data = []
    
    for step, row in model_metrics_df.iterrows():
        robot_km = row['TotalRobotKm']
        bike_km = row['TotalBikeKm']
        delivered = row['DeliveredParcels']
        
        # Energy consumption
        robot_energy = robot_km * robot_specs['energy_consumption_kwh_per_km']
        bike_energy = bike_km * bike_specs['energy_consumption_kwh_per_km']
        total_energy = robot_energy + bike_energy
        
        # CO2 emissions
        robot_co2 = robot_energy * robot_specs['co2_per_kwh']
        bike_co2 = bike_energy * bike_specs['co2_per_kwh']
        total_co2 = robot_co2 + bike_co2
        
        # Traditional delivery comparison
        # Assume traditional delivery needs 1 van trip per 15 parcels
        traditional_trips = delivered / 15 if delivered > 0 else 0
        traditional_km = traditional_trips * 8  # Average 8km per delivery route
        traditional_fuel = traditional_km * traditional_van['fuel_consumption_l_per_km']
        traditional_co2 = traditional_fuel * traditional_van['co2_per_liter']
        
        # CO2 savings
        co2_savings = traditional_co2 - total_co2
        co2_reduction_pct = (co2_savings / traditional_co2 * 100) if traditional_co2 > 0 else 0
        
        # Energy efficiency metrics
        energy_per_parcel = total_energy / delivered if delivered > 0 else 0
        co2_per_parcel = total_co2 / delivered if delivered > 0 else 0
        
        sustainability_data.append({
            'step': step,
            'simulation_minute': step,
            'robot_km': robot_km,
            'bike_km': bike_km,
            'total_km': robot_km + bike_km,
            'delivered_parcels': delivered,
            'robot_energy_kwh': robot_energy,
            'bike_energy_kwh': bike_energy,
            'total_energy_kwh': total_energy,
            'robot_co2_kg': robot_co2,
            'bike_co2_kg': bike_co2,
            'total_co2_kg': total_co2,
            'traditional_co2_kg': traditional_co2,
            'co2_savings_kg': co2_savings,
            'co2_reduction_pct': co2_reduction_pct,
            'energy_per_parcel_kwh': energy_per_parcel,
            'co2_per_parcel_kg': co2_per_parcel
        })
    
    return pd.DataFrame(sustainability_data)

def create_sustainability_dashboard(sustainability_df, save_path="results/sustainability_analysis.png"):
    """
    Create a comprehensive sustainability dashboard.
    """
    
    fig = plt.figure(figsize=(16, 12))
    
    # Color palette
    colors = {
        'robot': '#2E8B57',     # Sea green
        'bike': '#4169E1',      # Royal blue  
        'traditional': '#DC143C', # Crimson
        'savings': '#32CD32'    # Lime green
    }
    
    # 1. CO2 Emissions Comparison
    ax1 = plt.subplot(2, 3, 1)
    plt.plot(sustainability_df['simulation_minute'], sustainability_df['total_co2_kg'], 
             color=colors['robot'], linewidth=3, label='Our System')
    plt.plot(sustainability_df['simulation_minute'], sustainability_df['traditional_co2_kg'], 
             color=colors['traditional'], linewidth=3, label='Traditional Vans')
    plt.fill_between(sustainability_df['simulation_minute'], 
                     sustainability_df['total_co2_kg'], 
                     sustainability_df['traditional_co2_kg'],
                     color=colors['savings'], alpha=0.3, label='CO₂ Savings')
    
    plt.title('CO₂ Emissions Comparison', fontweight='bold', fontsize=12)
    plt.xlabel('Simulation Time (minutes)')
    plt.ylabel('Cumulative CO₂ (kg)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 2. Energy Consumption Breakdown
    ax2 = plt.subplot(2, 3, 2)
    plt.stackplot(sustainability_df['simulation_minute'],
                  sustainability_df['robot_energy_kwh'],
                  sustainability_df['bike_energy_kwh'],
                  labels=['Robots', 'E-Bikes'],
                  colors=[colors['robot'], colors['bike']],
                  alpha=0.8)
    
    plt.title('Energy Consumption Breakdown', fontweight='bold', fontsize=12)
    plt.xlabel('Simulation Time (minutes)')
    plt.ylabel('Cumulative Energy (kWh)')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)
    
    # 3. CO2 Reduction Percentage
    ax3 = plt.subplot(2, 3, 3)
    plt.plot(sustainability_df['simulation_minute'], sustainability_df['co2_reduction_pct'],
             color=colors['savings'], linewidth=4)
    plt.fill_between(sustainability_df['simulation_minute'], 
                     0, sustainability_df['co2_reduction_pct'],
                     color=colors['savings'], alpha=0.3)
    
    plt.title('CO₂ Reduction vs Traditional', fontweight='bold', fontsize=12)
    plt.xlabel('Simulation Time (minutes)')
    plt.ylabel('CO₂ Reduction (%)')
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 100)
    
    # 4. Efficiency Metrics
    ax4 = plt.subplot(2, 3, 4)
    
    # Filter out zero values for cleaner visualization
    efficiency_data = sustainability_df[sustainability_df['delivered_parcels'] > 0].copy()
    
    if len(efficiency_data) > 0:
        ax4_twin = ax4.twinx()
        
        line1 = ax4.plot(efficiency_data['simulation_minute'], 
                         efficiency_data['energy_per_parcel_kwh'],
                         color=colors['bike'], linewidth=2, label='Energy per Parcel')
        line2 = ax4_twin.plot(efficiency_data['simulation_minute'], 
                              efficiency_data['co2_per_parcel_kg'] * 1000,  # Convert to grams
                              color=colors['traditional'], linewidth=2, label='CO₂ per Parcel')
        
        ax4.set_xlabel('Simulation Time (minutes)')
        ax4.set_ylabel('Energy per Parcel (kWh)', color=colors['bike'])
        ax4_twin.set_ylabel('CO₂ per Parcel (g)', color=colors['traditional'])
        
        # Combine legends
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax4.legend(lines, labels, loc='upper right')
    
    ax4.set_title('Delivery Efficiency Metrics', fontweight='bold', fontsize=12)
    ax4.grid(True, alpha=0.3)
    
    # 5. Sustainability Score Over Time
    ax5 = plt.subplot(2, 3, 5)
    
    # Calculate a composite sustainability score (0-100)
    sustainability_score = sustainability_df['co2_reduction_pct'].copy()
    
    plt.plot(sustainability_df['simulation_minute'], sustainability_score,
             color='green', linewidth=3)
    plt.fill_between(sustainability_df['simulation_minute'], 0, sustainability_score,
                     color='green', alpha=0.3)
    
    plt.title('CO₂ Reduction Score', fontweight='bold', fontsize=12)
    plt.xlabel('Simulation Time (minutes)')
    plt.ylabel('CO₂ Reduction (%)')
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 100)
    
    # 6. Key Metrics Summary
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')
    
    # Calculate final metrics
    final_co2_savings = sustainability_df['co2_savings_kg'].iloc[-1]
    final_energy = sustainability_df['total_energy_kwh'].iloc[-1]
    final_reduction_pct = sustainability_df['co2_reduction_pct'].iloc[-1]
    total_km = sustainability_df['total_km'].iloc[-1]
    delivered_parcels = sustainability_df['delivered_parcels'].iloc[-1]
    
    # Equivalent metrics
    cars_off_road = final_co2_savings / (4.6 * 1000 / 365)  # Average car: 4.6 tons CO2/year
    trees_planted = final_co2_savings / 0.021  # One tree absorbs ~21kg CO2/year
    
    summary_text = f"""
SUSTAINABILITY IMPACT SUMMARY

🌱 Environmental Benefits:
   • CO₂ Reduction: {final_reduction_pct:.1f}%
   • Total CO₂ Saved: {final_co2_savings:.1f} kg
   • Energy Used: {final_energy:.1f} kWh
   
🚗 Equivalent Impact:
   • Cars off road: {cars_off_road:.1f} days
   • Trees equivalent: {trees_planted:.0f} trees
   
📊 Efficiency Metrics:
   • Total distance: {total_km:.1f} km
   • Parcels delivered: {delivered_parcels:.0f}
   • Energy per parcel: {final_energy/delivered_parcels:.3f} kWh
   • CO₂ per parcel: {sustainability_df['co2_per_parcel_kg'].iloc[-1]*1000:.1f} g
   
🎯 System Performance:
   • 90%+ electric delivery
   • Zero local emissions
   • Reduced traffic congestion
   • Improved air quality
"""
    
    ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes, 
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgreen", alpha=0.3))
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"Sustainability dashboard saved to: {save_path}")
    
    return fig

def analyze_simulation_sustainability(csv_path="results/model_metrics.csv"):
    """
    Main function to run sustainability analysis on your simulation results.
    """
    
    print("\n" + "="*60)
    print("SUSTAINABILITY ANALYSIS")
    print("="*60)
    
    try:
        # Load simulation data
        model_metrics = pd.read_csv(csv_path, index_col=0)
        total_delivered = model_metrics['DeliveredParcels'].iloc[-1]
        
        print(f"Analyzing simulation with {total_delivered} delivered parcels...")
        
        # Calculate sustainability metrics
        sustainability_df = calculate_sustainability_metrics(model_metrics)
        
        # Create dashboard
        fig = create_sustainability_dashboard(sustainability_df)
        
        # Print key insights
        final_metrics = sustainability_df.iloc[-1]
        print(f"\nKEY SUSTAINABILITY INSIGHTS:")
        print(f"  • CO₂ reduction: {final_metrics['co2_reduction_pct']:.1f}%")
        print(f"  • Total CO₂ saved: {final_metrics['co2_savings_kg']:.1f} kg")
        print(f"  • Energy consumption: {final_metrics['total_energy_kwh']:.1f} kWh")
        print(f"  • Energy per parcel: {final_metrics['energy_per_parcel_kwh']:.3f} kWh")
        print(f"  • CO₂ per parcel: {final_metrics['co2_per_parcel_kg']*1000:.1f} g")
        
        # Save detailed data
        sustainability_df.to_csv("results/sustainability_metrics.csv")
        print(f"  • Detailed metrics saved to: results/sustainability_metrics.csv")
        
        return sustainability_df, fig
        
    except FileNotFoundError:
        print(f"Error: Could not find {csv_path}")
        print("Make sure you've run the simulation first!")
        return None, None
    except Exception as e:
        print(f"Error in sustainability analysis: {e}")
        return None, None

if __name__ == "__main__":
    # Run sustainability analysis
    sustainability_data, dashboard = analyze_simulation_sustainability()
    
    if sustainability_data is not None:
        print(f"\nSustainability analysis completed successfully!")
        print(f"Files generated:")
        print(f"  • results/sustainability_analysis.png")
        print(f"  • results/sustainability_metrics.csv")