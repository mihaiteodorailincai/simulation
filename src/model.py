from mesa import Model
from mesa.time import SimultaneousActivation
from mesa.datacollection import DataCollector
import pandas as pd

from routing import shortest_path_length_time, shortest_path_route
from demand import load_demand
from agents import ParcelAgent, RobotAgent, CargoBikeAgent

def minutes_to_time_string(minutes_since_midnight):
    """
    Convert minutes since midnight to HH:MM format.
    
    Args:
        minutes_since_midnight: Integer minutes (e.g., 420 = 7:00 AM)
    
    Returns:
        String in HH:MM format (e.g., "07:00")
    """
    hours = minutes_since_midnight // 60
    minutes = minutes_since_midnight % 60
    return f"{hours:02d}:{minutes:02d}"

class CourierNetworkModel(Model):
    """
    An agent‐based model where:
    - RobotAgents serve same-zone deliveries (short distances, <1km)
    - CargoBikeAgents serve cross-zone deliveries and Class B parcels (longer distances, 1km+)
    """
    def __init__(self, 
                 bike_graph,
                 walk_graph,
                 hub_nodes_df,
                 demand_csv_path,
                 n_robots_per_hub=5,
                 n_bikes_per_hub=2,
                 robot_capacity=1,
                 bike_capacity=3):
        super().__init__()
        # 1) Store the graphs
        self.G_bike = bike_graph
        self.G_walk = walk_graph
        
        # 2) Hub nodes DataFrame
        self.hub_nodes_df = hub_nodes_df.copy()
        # Convert to dicts for quick lookup
        self.hub_bike_nodes = dict(zip(hub_nodes_df["hub"], hub_nodes_df["bike_node"]))
        self.hub_walk_nodes = dict(zip(hub_nodes_df["hub"], hub_nodes_df["walk_node"]))
        
        # 3) Model params
        self.robot_speed = 5 * 1000 / 3600       # m/s (5 km/h)
        self.bike_speed = 15 * 1000 / 3600       # m/s (15 km/h)
        self.robot_capacity = robot_capacity     # 1 parcel each
        self.bike_capacity = bike_capacity       # e.g. 3 parcels each
        
        # 4) Scheduler
        self.schedule = SimultaneousActivation(self)
        
        # 5) UPDATED QUEUE STRUCTURE: Separate queues by delivery type, not parcel class
        #    Format: { "Centrum": {"robot": deque(), "bike": deque()}, ... }
        from collections import deque
        self.hub_queues = {}
        for hub in self.hub_bike_nodes:
            self.hub_queues[hub] = {
                "robot": deque(),  # Same-zone deliveries (robots)
                "bike": deque()    # Cross-zone deliveries + Class B (bikes)
            }
        
        # 6) Data structures to hold agents
        self.parcels = []
        self.robots = []
        self.bikes = []
        
        # 7) Load demand
        self.demand_df = load_demand(demand_csv_path)
        
        # 8) Create ParcelAgents
        self._create_parcel_agents()
        
        # 9) Create RobotAgents & CargoBikeAgents
        self._create_vehicle_agents(n_robots_per_hub, n_bikes_per_hub)
        
        # 10) Data Collector
        self.datacollector = DataCollector(
            model_reporters={
                # divide by 1000 to convert from meters → kilometers
                "TotalRobotKm": lambda m: sum([r.distance_traveled for r in m.robots]) / 1000.0,
                "TotalBikeKm":  lambda m: sum([b.distance_traveled for b in m.bikes]) / 1000.0,
                "AvgParcelDelay": lambda m: m._compute_avg_parcel_delay(),
                "DeliveredParcels": lambda m: m._compute_total_delivered(),
                "RobotQueue": lambda m: sum([len(m.hub_queues[hub]["robot"]) for hub in m.hub_queues]),
                "BikeQueue": lambda m: sum([len(m.hub_queues[hub]["bike"]) for hub in m.hub_queues])
            }
        )

        
        # 11) Current time (in minutes since midnight). Start at 7:00 (optional)
        self.current_time = 420  # 7:00 AM = 7*60
        
    def _create_parcel_agents(self):
        """
        Instantiate one ParcelAgent per row in demand_df.
        """
        for idx, row in self.demand_df.iterrows():
            # Handle both old format (without dest_node) and new format (with dest_node)
            dest_node = row.get("dest_node", self.hub_walk_nodes[row["destination"]])
            
            agent = ParcelAgent(
                unique_id = int(row["parcel_id"]),
                model     = self,
                origin    = row["origin"],
                destination = row["destination"],
                size_class = row["size_class"],
                request_time = int(row["request_time"]),
                dest_node = dest_node
            )
            self.parcels.append(agent)
            self.schedule.add(agent)
    
    def _create_vehicle_agents(self, n_robots, n_bikes):
        """
        Instantiate RobotAgents and CargoBikeAgents for each hub.
        Each is placed on its home hub node initially.
        """
        uid = max(self.demand_df["parcel_id"]) + 1  # parcel IDs end here
        
        for hub in self.hub_bike_nodes:
            bike_node = self.hub_bike_nodes[hub]
            walk_node = self.hub_walk_nodes[hub]
            
            # Create n_robots RobotAgents at walk_node
            for i in range(n_robots):
                agent = RobotAgent(
                    unique_id = uid,
                    model     = self,
                    home_hub  = hub,
                    speed_mps = self.robot_speed,
                    capacity  = self.robot_capacity
                )
                agent.location_node = walk_node
                self.robots.append(agent)
                self.schedule.add(agent)
                uid += 1
            
            # Create n_bikes CargoBikeAgents at bike_node
            for j in range(n_bikes):
                agent = CargoBikeAgent(
                    unique_id = uid,
                    model     = self,
                    home_hub  = hub,
                    speed_mps = self.bike_speed,
                    capacity  = self.bike_capacity
                )
                agent.location_node = bike_node
                self.bikes.append(agent)
                self.schedule.add(agent)
                uid += 1
    
    def _compute_avg_parcel_delay(self):
        """
        Average (delivery_time - request_time) for all parcels that have delivery_time set.
        """
        delivered = [p for p in self.parcels if p.delivery_time is not None]
        if not delivered:
            return 0
        delays = [(p.delivery_time - p.request_time) for p in delivered]
        return sum(delays) / len(delays)
    
    def _compute_total_delivered(self):
        """
        Return count of all parcels with a non‐None delivery_time.
        """
        return len([p for p in self.parcels if p.delivery_time is not None])
    
    def step(self):
        """
        Advance the simulation by one minute:
        1) Let every agent run its step()
        2) Collect data
        3) Increment current_time
        """
        self.schedule.step()
        self.datacollector.collect(self)
        self.current_time += 1