import pandas as pd

def load_demand(csv_path="data/raw/demand_synthetic.csv"):
    """
    Reads the synthetic demand CSV into a pandas DataFrame.
    Returns a DataFrame sorted by request_time.
    """
    df = pd.read_csv(csv_path)
    df = df.sort_values("request_time").reset_index(drop=True)
    return df