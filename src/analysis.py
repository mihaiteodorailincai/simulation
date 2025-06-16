import pandas as pd
import matplotlib.pyplot as plt

def plot_metrics(csv_path="results/model_metrics.csv"):
    """
    Reads the model_metrics.csv and produces basic plots:
    - TotalRobotKm vs. time
    - TotalBikeKm vs. time
    - DeliveredParcels vs. time
    """
    df = pd.read_csv(csv_path, index_col=0)
    df.index.name = "Step"
    
    plt.figure(figsize=(8, 5))
    plt.plot(df.index, df["TotalRobotKm"], label="Total Robot km")
    plt.plot(df.index, df["TotalBikeKm"], label="Total Bike km")
    plt.xlabel("Simulation Minute")
    plt.ylabel("Kilometers Traveled")
    plt.legend()
    plt.title("Kilometers by Robots & Bikes Over Time")
    plt.savefig("results/robot_bike_km.png")
    plt.close()
    
    plt.figure(figsize=(8, 5))
    plt.plot(df.index, df["DeliveredParcels"], label="Delivered Parcels")
    plt.xlabel("Simulation Minute")
    plt.ylabel("Cumulative Parcels Delivered")
    plt.title("Parcel Delivery Count Over Time")
    plt.savefig("results/delivered_parcels.png")
    plt.close()
    
    print("Plots saved to results/ as .png files.")
    
if __name__ == "__main__":
    plot_metrics()