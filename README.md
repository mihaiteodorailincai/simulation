# Courier Network Simulation (Mesa + OSMnx)

An agent-based simulation of last-mile delivery logistics in an urban area. This model simulates the interactions between parcel delivery demand, robot couriers, and cargo bike couriers over real-world pedestrian and cycling networks.

Built using **Mesa** for agent-based modeling and **OSMnx** for handling OpenStreetMap networks.

## Project Structure

```
simulation/
├── data/
│   └── raw/
│       ├── bike_network.graphml
│       ├── walk_network.graphml
│       ├── hub_nodes.csv
│       └── demand_synthetic.csv
├── src/
│   ├── server.py
│   ├── model.py
│   ├── agents.py
│   └── utils.py
└── README.md
```

## How to Run

### 1. Set up the environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Prepare the network and data

If `data/raw/*.graphml` and `hub_nodes.csv` are not yet created, run the Jupyter notebook or data prep script provided separately to:

- Download a real-world street network with OSMnx
- Identify hub nodes for walking and biking
- Generate synthetic demand

### 3. Launch the server

```bash
python src/server.py
```

Then open your browser at:  
http://127.0.0.1:8521

## Agents

- **ParcelAgent**  
    Represents a delivery request. Has origin, destination, request time, and size class (A or B).

- **RobotAgent**  
    Assigned to the walkable network. Only handles Class A parcels (within the same hub).

- **CargoBikeAgent**  
    Operates on the bike network. Can carry multiple parcels, including inter-hub deliveries.

## Data Collection

Metrics collected during simulation:

- **TotalRobotKm** — Total kilometers traveled by robot agents
- **TotalBikeKm** — Total kilometers traveled by cargo bikes
- **AvgParcelDelay** — Average time parcels wait to be delivered
- **DeliveredParcels** — Total number of parcels successfully delivered

## Model Features

- Multi-graph routing using OSMnx
- Multiple hubs with separate queues for A and B parcels
- Time-based demand and agent activation
- Visual interface with Mesa’s NetworkModule

## Requirements

- mesa
- networkx
- osmnx
- pandas
- numpy
- tornado

Install them with:

```bash
pip install -r requirements.txt
```

## Notes

- The model starts at 7:00 AM (420 minutes since midnight)
- Time advances in 1-minute steps
- Graphs are required to be preprocessed and stored as `.graphml`

## To Do

- Add interactivity to prioritize urgent deliveries
- Enable vehicle rebalancing between hubs
- Add cost/efficiency KPIs to support policy evaluation
