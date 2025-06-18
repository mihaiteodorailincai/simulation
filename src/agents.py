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
    
    UPDATED: Now picks up multiple parcels up to capacity for efficient batch deliveries.
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
        self.delivery_stops = []  # List of (destination_hub, parcels_for_that_hub)
        self.current_stop_index = 0

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
        self.delivery_stops = []
        self.current_stop_index = 0

    def _plan_multi_delivery_route(self, parcels):
        """
        Plan an efficient route to deliver multiple parcels.
        Groups parcels by destination and creates a route visiting each destination.
        """
        # Group parcels by destination hub
        destination_groups = {}
        for parcel in parcels:
            dest = parcel.destination
            if dest not in destination_groups:
                destination_groups[dest] = []
            destination_groups[dest].append(parcel)
        
        # Create delivery stops
        self.delivery_stops = [(dest, parcels) for dest, parcels in destination_groups.items()]
        
        # Plan route visiting each destination hub in order, then returning home
        home_node = self.model.hub_bike_nodes[self.home_hub]
        route = [home_node]
        
        for dest_hub, _ in self.delivery_stops:
            dest_node = self.model.hub_bike_nodes[dest_hub]
            if dest_node != route[-1]:  # Avoid duplicate nodes
                try:
                    segment = shortest_path_route(self.model.G_bike, route[-1], dest_node)
                    route.extend(segment[1:])  # Skip first node to avoid duplication
                except:
                    print(f"Warning: Could not route from {route[-1]} to {dest_node}")
        
        # Add return route to home
        if route[-1] != home_node:
            try:
                return_segment = shortest_path_route(self.model.G_bike, route[-1], home_node)
                route.extend(return_segment[1:])
            except:
                print(f"Warning: Could not route back to home from {route[-1]}")
        
        return route

    def step(self):
        hub = self.home_hub
        bike_queue = self.model.hub_queues[hub]["bike"]

        # Debug for first bike
        if self.unique_id == min([b.unique_id for b in self.model.bikes]) and self.model.current_time % 50 == 0:
            real_time = minutes_to_time_string(self.model.current_time)
            print(f"Time {real_time}: Bike {self.unique_id} at {hub} - State: {self.state}, Queue: {len(bike_queue)}, Load: {len(self.load)}/{self.capacity}")

        # CASE 1: Idle & pick up multiple parcels up to capacity
        if self.state == "idle":
            if len(bike_queue) > 0:
                # NEW LOGIC: Pick up multiple parcels up to capacity
                parcels_to_pick = []
                
                # Collect parcels up to capacity
                while len(bike_queue) > 0 and len(parcels_to_pick) < self.capacity:
                    parcel = bike_queue.popleft()
                    parcel.pickup_time = self.model.current_time
                    parcel.current_vehicle = self
                    parcels_to_pick.append(parcel)
                
                # Plan multi-delivery route
                self.load = parcels_to_pick
                self.route = self._plan_multi_delivery_route(parcels_to_pick)
                self.state = "delivering"
                self.location_index = 0
                self.current_stop_index = 0
                self.current_edge_length = None
                self.edge_progress = 0.0
                self.current_edge = None
                
                # Debug output
                if self.unique_id == min([b.unique_id for b in self.model.bikes]):
                    real_time = minutes_to_time_string(self.model.current_time)
                    destinations = [p.destination for p in parcels_to_pick]
                    print(f"{real_time} - Bike {self.unique_id} picked up {len(parcels_to_pick)} parcels to: {destinations}")
            else:
                return

        # CASE 2: Delivering to multiple destinations
        if self.state == "delivering":
            if self.current_edge_length is None:
                self.start_next_edge()
                if self.current_edge_length is None:
                    # Route finished, switch to returning
                    self.state = "returning"
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

            # Edge finished - check if we're at a delivery destination
            curr_node, next_node = self.current_edge
            self.location_node = next_node
            self.location_index += 1
            self.edge_progress = 0.0
            self.current_edge_length = None
            self.current_edge = None

            # Check if we've reached any delivery destination
            for dest_hub, parcels_for_dest in self.delivery_stops:
                dest_node = self.model.hub_bike_nodes[dest_hub]
                if self.location_node == dest_node:
                    # Deliver all parcels for this destination
                    for parcel in parcels_for_dest:
                        if parcel in self.load:
                            parcel.delivery_time = self.model.current_time
                            self.load.remove(parcel)
                    
                    # Remove this stop from our list
                    self.delivery_stops = [(d, p) for d, p in self.delivery_stops if d != dest_hub]
                    
                    if self.unique_id == min([b.unique_id for b in self.model.bikes]):
                        real_time = minutes_to_time_string(self.model.current_time)
                        print(f"{real_time} - Bike {self.unique_id} delivered {len(parcels_for_dest)} parcels at {dest_hub}")
                    break

            # If all deliveries complete, head home
            if not self.load:
                self.state = "returning"

        # CASE 3: Returning home
        elif self.state == "returning":
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

            # Check if we're home
            home_node = self.model.hub_bike_nodes[self.home_hub]
            if self.location_node == home_node:
                self._finish_route_and_idle()
                if self.unique_id == min([b.unique_id for b in self.model.bikes]):
                    real_time = minutes_to_time_string(self.model.current_time)
                    print(f"{real_time} - Bike {self.unique_id} returned home")
                return