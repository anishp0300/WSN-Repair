import random
from enum import Enum
import sys
# insert at 1, 0 is the script path (or '' in REPL)
sys.path.insert(1, '.')
from source import wsnlab_vis as wsn
import math
from source import config

Roles = Enum('Roles', 'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD ROUTER')   #Added by Anish
"""Enumeration of roles"""

###########################################################
class SensorNode(wsn.Node):
    """SensorNode class is inherited from Node class in wsnlab.py.
    It will run data collection tree construction algorithms.

    Attributes:
        role (Roles): role of node
        is_root_eligible (bool): keeps eligibility to be root
        c_probe (int): probe message counter
        th_probe (int): probe message threshold
        neighbors_table (Dict): keeps the neighbor information with received heart beat messages
    """

    ###################
    def init(self):
        """Initialization of node. Setting all attributes of node.
        At the beginning node needs to be sleeping and its role should be UNDISCOVERED.

        Args:

        Returns:

        """
        self.scene.nodecolor(self.id, 1, 1, 1) # sets self color to white
        self.sleep()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.role = Roles.UNDISCOVERED
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0  # c means counter and probe is the name of counter
        self.th_probe = 10  # th means threshold and probe is the name of threshold
        self.hop_count = 99999
        self.neighbors_table = {}  # keeps neighbor information with received HB messages
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        self.router = False
        self.Router_members = []

    ###################
    def run(self):
        """Setting the arrival timer to wake up after firing.

        Args:

        Returns:

        """
        self.set_timer('TIMER_ARRIVAL', self.arrival)
        if self.id == 20:
                self.set_timer('TIMER_DEAD', 300)

    ###################
    def become_unregistered(self):
        if self.role != Roles.UNDISCOVERED:
            self.kill_all_timers()
            self.log('I became UNREGISTERED')
        self.scene.nodecolor(self.id, 1, 1, 0)
        self.erase_parent()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.role = Roles.UNREGISTERED
        self.c_probe = 0
        self.th_probe = 10
        self.hop_count = 99999
        self.neighbors_table = {}
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        self.send_probe()
        self.set_timer('TIMER_JOIN_REQUEST', 20)

    ###################
    def update_neighbor(self, pck):
        pck['arrival_time'] = self.now
        self.neighbors_table[pck['gui']] = pck
        if pck['gui'] not in self.child_networks_table.keys() or pck['gui'] not in self.members_table:
            if pck['gui'] not in self.candidate_parents_table:
                self.candidate_parents_table.append(pck['gui'])
                # NEWLY ADDED
        if pck['gui'] == self.parent_gui and self.hop_count != pck['hop_count'] + 1:  # if parent's hop count is changed
            self.hop_count = pck['hop_count'] + 1
            self.send_heart_beat()
            
    ###################  NEWLY ADDED
    def check_neighbors(self):
        """Checks neighbors if they are still alive or not. If not, updates necessary tables.
        Sends heartbeat and network update messages in need.

        Args:

        Returns:

        """
        childs_updated = False
        parent_dead = False
        will_be_removed = []
        for gui, pck in self.neighbors_table.items():
            if self.now - pck['arrival_time'] > 3 * config.HEARTH_BEAT_TIME_INTERVAL:
                will_be_removed.append(gui)
                if gui == self.parent_gui:
                    parent_dead = True
                if gui in self.child_networks_table.keys():
                    del self.child_networks_table[gui]
                    childs_updated = True
                if gui in self.candidate_parents_table:
                    self.candidate_parents_table.remove(gui)
        for gui in will_be_removed:
            del self.neighbors_table[gui]
        if self.role != Roles.UNREGISTERED:
            if parent_dead:
                self.repair()
            else:
                self.send_heart_beat()
                self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                if childs_updated:
                    if self.role != Roles.ROOT:
                        self.send_network_update()

    ###################
    def select_and_join(self):
        min_hop = 99999
        min_hop_gui = 99999
        for gui in self.candidate_parents_table:
            if self.neighbors_table[gui]['hop_count'] < min_hop or (self.neighbors_table[gui]['hop_count'] == min_hop and gui < min_hop_gui):
                min_hop = self.neighbors_table[gui]['hop_count']
                min_hop_gui = gui
        selected_addr = self.neighbors_table[min_hop_gui]['source']
        #if(selected_addr is None) :
            #self.log({'id':self.id,'role':self.role})
        self.send_join_request(selected_addr)
        self.set_timer('TIMER_JOIN_REQUEST', 5)


    ################### NEWLY ADDED
    def repair(self):
        """Executes chosen repairing instructions.

        Args:

        Returns:

        """
        if self.role == Roles.REGISTERED:
            self.become_unregistered()
        else:
            if config.REPAIRING_METHOD == 'ALL_ORPHAN':
                self.repair_all_orphan()
            elif config.REPAIRING_METHOD == 'FIND_ANOTHER_PARENT':
                self.repair_find_another_parent()
                
    ################### NEWLY ADDED
    def repair_all_orphan(self):
        """Becomes unregistered and sends I am orphan message.

        Args:

        Returns:

        """
        self.send_i_am_orphan()
        self.become_unregistered()
                
    ################### NEWLY ADDED
    def repair_find_another_parent(self):
        """If it has potential parent in its table, tries to connect any of them. Otherwise becomes unregistered.

        Args:

        Returns:

        """
        if self.parent_gui in self.candidate_parents_table:
            self.candidate_parents_table.remove(self.parent_gui)
            del self.neighbors_table[self.parent_gui]
        if len(self.candidate_parents_table) != 0:
            self.kill_all_timers()
            self.erase_parent()
            self.role = Roles.UNREGISTERED
            self.select_and_join()
        else:
            self.send_i_am_orphan()
            self.become_unregistered()
            
    ###################
    def send_probe(self):
        """Sending probe message to be discovered and registered.

        Args:

        Returns:
        """
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE', 'source':self.addr})

    ###################
    def send_heart_beat(self):
        """Sending heart beat message

        Args:

        Returns:

        """
        self.send({'dest': wsn.BROADCAST_ADDR,
                   'type': 'HEART_BEAT',
                   'source': self.ch_addr if self.ch_addr is not None else self.addr,
                   'gui': self.id,
                   'role': self.role,
                   'addr': self.addr,
                   'ch_addr': self.ch_addr,
                   'hop_count': self.hop_count,
                   'is_router': self.router})

    ###################
    def send_join_request(self, dest):
        """Sending join request message to given destination address to join destination network

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id})

    ###################
    def send_join_reply(self, gui, addr, AssignClusterHeadAddr = False):
        """Sending join reply message to register the node requested to join.
        The message includes a gui to determine which node will take this reply, an addr to be assigned to the node
        and a root_addr.

        Args:
            gui (int): Global unique ID
            addr (Addr): Address that will be assigned to new registered node
        Returns:

        """
        AssignedChAddr = None
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1,"dest_ch_adr": AssignClusterHeadAddr, "JoinReplyFromRouter":self.router})

    ###################
    def send_join_ack(self, dest):
        """Sending join acknowledgement message to given destination address.

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        self.log({'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr, 'gui': self.id})
        self.send({'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr, 'gui': self.id})

    ###################
    def route_and_forward_package(self, pck):
        """Routing and forwarding given package

        Args:
            pck (Dict): package to route and forward it should contain dest, source and type.
        Returns:

        """
        if self.role != Roles.ROOT:
            pck['next_hop'] = self.neighbors_table[self.parent_gui]['ch_addr']
        if self.ch_addr is not None:
            if pck['dest'].net_addr == self.ch_addr.net_addr:
                pck['next_hop'] = pck['dest']
            else:
                for child_gui, child_networks in self.child_networks_table.items():
                    if pck['dest'].net_addr in child_networks:
                        pck['next_hop'] = self.neighbors_table[child_gui]['addr']
                        break
                    
        # Added by Anish
        if self.role == Roles.REGISTERED:
            if self.addr.node_addr == 254:
                pck['next_hop'] = self.neighbors_table[self.parent_gui]['addr']
                
        if self.role == Roles.CLUSTER_HEAD:
            if pck['dest'].net_addr == ROOT_ID:
                print(self.neighbors_table[self.parent_gui]['addr'])
                if pck['type'] == 'NETWORK_REQUEST':
                    pck['next_hop'] = self.neighbors_table[self.parent_gui]['addr']
                elif pck['type'] == 'NETWORK_REPLY':
                    pck['next_hop'] = pck['source']
            else:
                for child_gui, child_networks in self.child_networks_table.items():
                    if pck['dest'].net_addr in child_networks:
                        pck['next_hop'] = self.neighbors_table[child_gui]['addr']
                        
        if self.role == Roles.ROUTER:
            pck['next_hop'] == self.neighbors_table[self.parent_gui]['addr']
            if pck['type'] == 'NETWORK_REPLY':
                for child_gui, child_networks in self.child_networks_table.items():
                    if pck['dest'].net_addr in child_networks:
                        pck['next_hop'] = self.neighbors_table[child_gui]['ch_addr']
        
        if self.role == Roles.ROOT and pck['type'] == 'NETWORK_REPLY' :
            # dest_id = pck['dest'].net_addr
            for child_gui, child_networks in self.child_networks_table.items():
                if pck['dest'].net_addr in child_networks:
                    pck['next_hop'] = self.neighbors_table[child_gui]['addr']                
        # End Added by Anish

        self.send(pck)
        
    ################### NEWLY ADDED
    def send_i_am_orphan(self):
        """Sends i am orphan message to inform its neighbors.

        Args:

        Returns:

        """
        self.send({'dest': wsn.BROADCAST_ADDR,
                   'type': 'I_AM_ORPHAN',
                   'source': self.ch_addr})

    ################### Added by Anish
    def isRouterEligible(self):
        if self.received_JR_guis is not None :
            return True
        else:
            return False
        
    ###################
    def send_network_request(self):
        """Sending network request message to root address to be cluster head

        Args:

        Returns:

        """
        self.route_and_forward_package({'dest': self.root_addr, 'type': 'NETWORK_REQUEST', 'source': self.addr})

    ###################
    def send_network_reply(self, dest, addr):
        """Sending network reply message to dest address to be cluster head with a new address

        Args:
            dest (Addr): destination address
            addr (Addr): cluster head address of new network

        Returns:

        """
        self.route_and_forward_package({'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr, 'NetworkReplyRole':self.role, "DestIsRouterEligible": True if self.role == Roles.ROUTER else False})

    ###################
    def send_network_update(self):
        """Sending network update message to parent

        Args:

        Returns:

        """
        # Added by Anish
        if self.role == Roles.ROUTER:
            child_networks= []
            for networks in self.child_networks_table.values():
                child_networks.extend(networks)
            self.send({'dest': self.neighbors_table[self.parent_gui]['addr'], 'type': 'NETWORK_UPDATE', 'source': self.addr,
                   'gui': self.id, 'child_networks': child_networks})
        else:
            print("[ID", self.id,"]--->", self.role,"","--> addr",self.addr)
            child_networks = []
            if self.ch_addr is not None:
                child_networks = [self.ch_addr.net_addr]
                for networks in self.child_networks_table.values():
                    child_networks.extend(networks)
            # if child_networks is not
            self.send({'dest': self.neighbors_table[self.parent_gui]['addr'], 'type': 'NETWORK_UPDATE', 'source': self.addr,
                   'gui': self.id, 'child_networks': child_networks})

    ###################
    def on_receive(self, pck):
        """Executes when a package received.

        Args:
            pck (Dict): received package
        Returns:

        """
        if self.role == Roles.ROOT or self.role == Roles.CLUSTER_HEAD or self.role == Roles.ROUTER:  # if the node is root or cluster head or router
            if 'next_hop' in pck.keys() and pck['dest'] != self.addr:  # forwards message if destination is not itself
                if self.ch_addr is not None:
                    if pck['dest'] != self.ch_addr:
                        self.route_and_forward_package(pck)
                        return
                elif self.router == True:
                    self.route_and_forward_package(pck)
                    return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'PROBE':  # it waits and sends heart beat message once received probe message
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it waits and sends join reply message once received join request
                # yield self.timeout(.5)
                new_addr = None
                if(self.role == Roles.ROOT):
                    new_addr = wsn.Addr(self.root_addr.net_addr, pck['gui'])
                elif(self.role == Roles.CLUSTER_HEAD):
                    new_addr = wsn.Addr(self.ch_addr.net_addr, pck['gui'])
                self.send_join_reply(pck['gui'], new_addr)
                
            if pck['type'] == 'NETWORK_REQUEST':
                if self.role == Roles.ROOT:
                    new_addr = wsn.Addr(pck['source'].net_addr,self.id)
                    self.send_network_reply(pck['source'],new_addr)
            if pck['type'] == 'JOIN_ACK':
                self.members_table.append(pck['gui'])
            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                if self.role != Roles.ROOT:
                    self.send_network_update()
            if pck['type'] == 'SENSOR':
                pass
                # self.log(str(pck['source'])+'--'+str(pck['sensor_value']))

        elif self.role == Roles.REGISTERED:  # if the node is registered
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'PROBE':
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it sends a network request to the root
                self.received_JR_guis.append(pck['gui'])
                # yield self.timeout(.5)
                self.send_network_request()
            if pck['type'] == 'NETWORK_REPLY':  # it becomes cluster head and send join reply to the candidates
                self.role = Roles.ROUTER
                self.scene.nodecolor(self.id, 1, 0, 1)
                self.router = True
                self.send_heart_beat()
                self.send_network_update()
                # yield self.timeout(.5)
                for gui in self.received_JR_guis:
                    # yield self.timeout(random.uniform(.1,.5))
                    self.log(wsn.Addr(gui,254))
                    self.send_join_reply(gui, wsn.Addr(gui,254))

        elif self.role == Roles.UNDISCOVERED:  # if the node is undiscovered
            if pck['type'] == 'HEART_BEAT':  # it kills probe timer, becomes unregistered and sets join request timer once received heart beat
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        if self.role == Roles.UNREGISTERED:  # if the node is unregistered
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'JOIN_REPLY': 
                if pck['dest_gui'] == self.id:
                    self.log(pck)
                    self.addr = pck['addr']
                    self.parent_gui = pck['gui']
                    self.root_addr = pck['root_addr']
                    self.hop_count = pck['hop_count']
                    self.draw_parent()
                    self.kill_timer('TIMER_JOIN_REQUEST')
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if 'gui' in pck.keys() and self.neighbors_table[self.parent_gui]['role'] == Roles.ROUTER :
                        self.role = Roles.CLUSTER_HEAD
                        self.addr = wsn.Addr(self.id,254)
                        self.ch_addr = self.addr
                        self.scene.nodecolor(self.id, 0, 0, 1)
                        self.send_heart_beat()
                        self.send_network_update()
                    else:
                        self.role = Roles.REGISTERED
                        self.scene.nodecolor(self.id, 0, 1, 0)
                        self.send_heart_beat()
                    # # sensor implementation
                    # timer_duration =  self.id % 20
                    # if timer_duration == 0: timer_duration = 1
                    # self.set_timer('TIMER_SENSOR', timer_duration)

    ###################
    def on_timer_fired(self, name, *args, **kwargs):
        """Executes when a timer fired.

        Args:
            name (string): Name of timer.
            *args (string): Additional args.
            **kwargs (string): Additional key word args.
        Returns:

        """
        if name == 'TIMER_ARRIVAL':  # it wakes up and set timer probe once time arrival timer fired
            self.scene.nodecolor(self.id, 1, 0, 0)  # sets self color to red
            self.wake_up()
            self.set_timer('TIMER_PROBE', 1)

        elif name == 'TIMER_PROBE':  # it sends probe if counter didn't reach the threshold once timer probe fired.
            if self.c_probe < self.th_probe:
                self.send_probe()
                self.c_probe += 1
                self.set_timer('TIMER_PROBE', 1) 
            else:  # if the counter reached the threshold
                if self.is_root_eligible:  # if the node is root eligible, it becomes root
                    self.role = Roles.ROOT
                    self.scene.nodecolor(self.id, 0, 0, 0)
                    self.addr = wsn.Addr(self.id, 254)
                    self.ch_addr = wsn.Addr(self.id, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                else:  # otherwise it keeps trying to sending probe after a long time
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            self.send_heart_beat()
            self.check_neighbors()
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)

        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            self.check_neighbors()
            if len(self.candidate_parents_table) == 0:
                if self.ch_addr is not None: # if it has a cluster head address. (if it is in repairing phase)
                    self.send_i_am_orphan()
                self.become_unregistered()
            else:  # otherwise it chose one of them and sends join request
                self.select_and_join()

        elif name == 'TIMER_SENSOR':
            self.route_and_forward_package({'dest': self.root_addr, 'type': 'SENSOR', 'source': self.addr, 'sensor_value': random.uniform(10,50)})
            timer_duration =  self.id % 20
            if timer_duration == 0: timer_duration = 1
            self.set_timer('TIMER_SENSOR', timer_duration)
            
        elif name == 'TIMER_DEAD':
            if self.id == 20:
                
                self.sleep()
                self.log('I AM DEAD')
                self.scene.nodecolor(self.id, 1, 1, 1)  # sets self color to red
                self.erase_parent()
                self.kill_all_timers()







ROOT_ID = random.randint(0, config.SIM_NODE_COUNT)


###########################################################
def create_network(node_class, number_of_nodes=100):
    """Creates given number of nodes at random positions with random arrival times.

    Args:
        node_class (Class): Node class to be created.
        number_of_nodes (int): Number of nodes.
    Returns:

    """
    edge = math.ceil(math.sqrt(number_of_nodes))
    for i in range(number_of_nodes):
        x = i / edge
        y = i % edge
        px = 50 + x * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        py = 50 + y * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        node = sim.add_node(node_class, (px, py))
        node.tx_range = config.NODE_TX_RANGE
        node.logging = True
        node.arrival = random.uniform(0, config.NODE_ARRIVAL_MAX)
        if node.id == ROOT_ID:
            node.arrival = 0.1


sim = wsn.Simulator(
    duration=config.SIM_DURATION,
    timescale=config.SIM_TIME_SCALE,
    visual=config.SIM_VISUALIZATION,
    terrain_size=config.SIM_TERRAIN_SIZE,
    title=config.SIM_TITLE)

# creating random network
create_network(SensorNode, config.SIM_NODE_COUNT)

# start the simulation
sim.run()

# Created 100 nodes at random locations with random arrival times.
# When nodes are created they appear in white
# Activated nodes becomes red
# Routers will become pink
# Discovered nodes will be yellow
# Registered nodes will be green.
# Root node will be black.
# Routers/Cluster Heads should be blue
