from mesa import Agent
from routing import shortest_path_route

def minutes_to_time_string(minutes_since_midnight):
    """
    Convert minutes since midnight to HH:MM format.
    """
    hours = minutes_since_midnight // 60
    minutes = minutes_since_midnight % 60
    return f"{hours:02d}:{minutes:02d}"

class ParcelAgent(Agent):
    """
    Represents a single parcel that goes from origin hub to a specific delivery address.
    """
    def __init__(self, unique_id, model, origin, destination, size_class, request_time, dest_node=None):
        super().__init__(unique_id, model)
        self.origin = origin
        self.destination = destination
        self.dest_node = dest_node or model.hub_walk_nodes.get(destination)  # Actual delivery node
        self.size_class = size_class  # "A" or "B"
        self.request_time = request_time  # in minutes since midnight
        self.assigned = False
        self.pickup_time = None
        self.delivery_time = None
        self.current_vehicle = None

    def step(self):
        if not self.assigned and self.model.current_time >= self.request_time:
            if self.origin == "External":
                target_hub = self.destination
            else:
                target_hub = self.origin
            
            # DEBUG: Print first few parcels to understand the data
            if self.unique_id <= 10:
                real_time = minutes_to_time_string(self.model.current_time)
                print(f"Parcel {self.unique_id} at {real_time}: {self.origin} → {self.destination}")
            
            # FIXED LOGIC: Route parcels based on delivery type
            if self.origin == "External":
                # External deliveries: robots handle last-mile delivery
                self.model.hub_queues[target_hub]["robot"].append(self)
                if self.unique_id <= 10:
                    print(f"  → Routed to ROBOT queue at {target_hub}")
            elif self.origin == self.destination:
                # Same-zone delivery: robots can handle these
                self.model.hub_queues[target_hub]["robot"].append(self)
                if self.unique_id <= 10:
                    print(f"  → Routed to ROBOT queue at {target_hub} (same zone)")
            else:
                # Cross-zone delivery: bikes must handle these
                self.model.hub_queues[target_hub]["bike"].append(self)
                if self.unique_id <= 10:
                    print(f"  → Routed to BIKE queue at {target_hub} (cross zone)")
            
            self.assigned = True


def _get_edge_length(graph, u, v):
    """
    Fetch 'length' attribute (in meters) from edge (u, v) in graph.
    """
    edge_data = graph.get_edge_data(u, v)
    if edge_data is None:
        raise ValueError(f"No edge between {u} and {v}")
    
    if isinstance(edge_data, dict) and edge_data:
        first_val = next(iter(edge_data.values()))
        if isinstance(first_val, dict) and 'length' in first_val:
            for attr in edge_data.values():
                if 'length' in attr:
                    return attr['length']
            raise ValueError(f"Edge data for {u}-{v} missing 'length'")
        
        if 'length' in edge_data:
            return edge_data['length']
        else:
            raise ValueError(f"Edge data for {u}-{v} missing 'length'")
    
    raise ValueError(f"Edge data for {u}-{v} missing 'length'")


class RobotAgent(Agent):
    """
    Sidewalk robot for delivering parcels WITHIN THE SAME ZONE ONLY.
    Max distance: ~1km deliveries.
    """
    def __init__(self, unique_id, model, home_hub, speed_mps, capacity):
        super().__init__(unique_id, model)
        self.home_hub = home_hub
        self.speed_mps = speed_mps
        self.capacity = capacity
        self.load = []
        self.location_node = None
        self.route = []
        self.state = "idle"
        self.distance_traveled = 0
        self.edge_progress = 0.0
        self.current_edge_length = None
        self.current_edge = None
        self.location_index = 0

    def start_next_edge(self):
        if self.location_index < len(self.route) - 1:
            curr_node = self.route[self.location_index]
            next_node = self.route[self.location_index + 1]
            length = _get_edge_length(self.model.G_walk, curr_node, next_node)
            self.current_edge_length = length
            self.edge_progress = 0.0
            self.current_edge = (curr_node, next_node)
        else:
            self.current_edge_length = None
            self.edge_progress = 0.0
            self.current_edge = None

    def _finish_route_and_idle(self):
        self.state = "idle"
        self.route = []
        self.location_index = 0
        self.current_edge = None
        self.current_edge_length = None
        self.edge_progress = 0.0

    def step(self):
        hub = self.home_hub
        robot_queue = self.model.hub_queues[hub]["robot"]

        # Debug for first robot
        if self.unique_id == min([r.unique_id for r in self.model.robots]) and self.model.current_time % 50 == 0:
            real_time = minutes_to_time_string(self.model.current_time)
            print(f"Time {real_time} (minute {self.model.current_time}): Robot {self.unique_id} at {hub} - State: {self.state}, Queue: {len(robot_queue)}, Distance: {self.distance_traveled:.1f}m")

        # CASE 1: Idle & pick up SAME-ZONE parcels only
        if self.state == "idle":
            if len(robot_queue) > 0:
                parcel = robot_queue.popleft()
                
                # SAFETY CHECK: Ensure robot only takes same-zone or external deliveries
                if parcel.origin != "External" and parcel.origin != parcel.destination:
                    print(f"ERROR: Robot {self.unique_id} trying to take cross-zone parcel {parcel.unique_id}")
                    # Put it back and assign to bike queue
                    self.model.hub_queues[hub]["bike"].append(parcel)
                    return
                
                parcel.pickup_time = self.model.current_time
                parcel.current_vehicle = self
                
                # Plan route: hub → actual delivery address
                hub_node = self.model.hub_walk_nodes[hub]
                dest_node = parcel.dest_node  # Use actual delivery node, not zone hub
                
                # Check distance
                if hub_node == dest_node:
                    parcel.delivery_time = self.model.current_time
                    return
                
                # For same-zone delivery, just go there and back
                route_to = shortest_path_route(self.model.G_walk, hub_node, dest_node)
                route_back = shortest_path_route(self.model.G_walk, dest_node, hub_node)
                
                self.route = route_to + route_back[1:]
                self.state = "delivering"
                self.load = [parcel]
                self.location_index = 0
                self.current_edge_length = None
                self.edge_progress = 0.0
                self.current_edge = None
                
                if self.unique_id == min([r.unique_id for r in self.model.robots]):
                    real_time = minutes_to_time_string(self.model.current_time)
                    print(f"{real_time} - Robot {self.unique_id} picked up parcel {parcel.unique_id}, route length: {len(self.route)}")
            else:
                # No parcels - stay idle
                return

        # CASE 2: Delivering within zone
        if self.state in ["delivering", "returning"]:
            if self.current_edge_length is None:
                self.start_next_edge()
                if self.current_edge_length is None:
                    self._finish_route_and_idle()
                    return
            
            dt_seconds = 60
            max_distance_this_step = self.speed_mps * dt_seconds
            dist_to_finish = self.current_edge_length - self.edge_progress
            move_dist = min(max_distance_this_step, dist_to_finish)
            
            if move_dist > 0:
                self.edge_progress += move_dist
                self.distance_traveled += move_dist
            
            if move_dist < dist_to_finish:
                return

            # Edge finished
            curr_node, next_node = self.current_edge
            self.location_node = next_node
            self.location_index += 1
            self.edge_progress = 0.0
            self.current_edge_length = None
            self.current_edge = None

            if self.state == "delivering":
                if len(self.load) > 0:
                    parcel = self.load[0]
                    dest_node = parcel.dest_node if hasattr(parcel, 'dest_node') else self.model.hub_walk_nodes[parcel.destination]
                    if self.location_node == dest_node:
                        parcel = self.load.pop(0)
                        parcel.delivery_time = self.model.current_time
                        self.state = "returning"
                        if self.unique_id == min([r.unique_id for r in self.model.robots]):
                            real_time = minutes_to_time_string(self.model.current_time)
                            print(f"{real_time} - Robot {self.unique_id} delivered parcel {parcel.unique_id}")
                        return
            elif self.state == "returning":
                home_node = self.model.hub_walk_nodes[self.home_hub]
                if self.location_node == home_node:
                    self._finish_route_and_idle()
                    if self.unique_id == min([r.unique_id for r in self.model.robots]):
                        real_time = minutes_to_time_string(self.model.current_time)
                        print(f"{real_time} - Robot {self.unique_id} returned home")
                    return


class CargoBikeAgent(Agent):
    """
    E-cargo-bike for:
    1. Cross-zone deliveries (hub-to-hub transport)
    2. Class B parcels (large packages)
    3. Longer distance deliveries (1km+)
    """
    def __init__(self, unique_id, model, home_hub, speed_mps, capacity):
        super().__init__(unique_id, model)
        self.home_hub = home_hub
        self.speed_mps = speed_mps
        self.capacity = capacity
        self.load = []
        self.location_node = None
        self.route = []
        self.state = "idle"
        self.distance_traveled = 0
        self.edge_progress = 0.0
        self.current_edge_length = None
        self.current_edge = None
        self.location_index = 0

    def start_next_edge(self):
        if self.location_index < len(self.route) - 1:
            curr_node = self.route[self.location_index]
            next_node = self.route[self.location_index + 1]
            length = _get_edge_length(self.model.G_bike, curr_node, next_node)
            self.current_edge_length = length
            self.edge_progress = 0.0
            self.current_edge = (curr_node, next_node)
        else:
            self.current_edge_length = None
            self.edge_progress = 0.0
            self.current_edge = None

    def _finish_route_and_idle(self):
        self.state = "idle"
        self.route = []
        self.location_index = 0
        self.current_edge = None
        self.current_edge_length = None
        self.edge_progress = 0.0

    def step(self):
        hub = self.home_hub
        bike_queue = self.model.hub_queues[hub]["bike"]

        # Idle & pick up cross-zone parcels or Class B parcels
        if self.state == "idle":
            if len(bike_queue) > 0:
                parcel = bike_queue.popleft()
                parcel.pickup_time = self.model.current_time
                parcel.current_vehicle = self
                
                # Use bike network for longer distances
                origin_node = self.model.hub_bike_nodes[hub]
                dest_node = self.model.hub_bike_nodes[parcel.destination]
                
                route_to = shortest_path_route(self.model.G_bike, origin_node, dest_node)
                route_back = shortest_path_route(self.model.G_bike, dest_node, origin_node)
                
                self.route = route_to + route_back[1:]
                self.state = "transit"
                self.load = [parcel]
                self.location_index = 0
                self.current_edge_length = None
                self.edge_progress = 0.0
                self.current_edge = None
            else:
                return

        # Transit or returning
        if self.state in ["transit", "returning"]:
            if self.current_edge_length is None:
                self.start_next_edge()
                if self.current_edge_length is None:
                    self._finish_route_and_idle()
                    return
            
            dt_seconds = 60
            max_distance_this_step = self.speed_mps * dt_seconds
            dist_to_finish = self.current_edge_length - self.edge_progress
            move_dist = min(max_distance_this_step, dist_to_finish)
            
            if move_dist > 0:
                self.edge_progress += move_dist
                self.distance_traveled += move_dist
                
            if move_dist < dist_to_finish:
                return

            # Edge finished
            curr_node, next_node = self.current_edge
            self.location_node = next_node
            self.location_index += 1
            self.edge_progress = 0.0
            self.current_edge_length = None
            self.current_edge = None

            if self.state == "transit":
                dest_node = self.model.hub_bike_nodes[self.load[0].destination]
                if self.location_node == dest_node:
                    parcel = self.load.pop(0)
                    parcel.delivery_time = self.model.current_time
                    self.state = "returning"
                    return
            elif self.state == "returning":
                home_node = self.model.hub_bike_nodes[self.home_hub]
                if self.location_node == home_node:
                    self._finish_route_and_idle()
                    return