"""
Alpha Dragon Charge Genesis — cleaned public release build.

This version keeps the core classes and functions from the original research
script, removes duplicate top-level function overrides, and wraps execution in
an import-safe main entry point.

AlphaDragon Charge Genesis — 118-node research simulation

Views:
- Linear Mode: pulse amplitude across indexed nodes
- Radial Mode: shell/bridge network layout

Controls:
- t : toggle view
- f : toggle focus mode
- r : reset layout
- u : toggle status HUD

This is a research prototype built in Python/Matplotlib.
"""

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import cm
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
import random
import networkx as nx
from collections import deque
from math import sqrt
phi = (1 + sqrt(5)) / 2  # Golden ratio

ENABLE_TRUTH_RESONANCE = False  # Master toggle for step 3.4 feedback
ENABLE_SHELL_LOGGING = True

show_status_panel = [True]  # Use a list for mutability inside event handlers
best_alignment_score = [float('-inf')]  # Mutable to track best so far

# Persistent memory for top cluster center over time
cluster_center_trace = []
MAX_TRACE_LEN = 200  # Show up to 200 past frames (tweak as you like)

# Atomic radii and positions based on Periodic Table
atomic_data = {
    1:  {"symbol": "H",  "group": 1, "period": 1, "radius": 25},
    2:  {"symbol": "He", "group": 18, "period": 1, "radius": 31},
    3:  {"symbol": "Li", "group": 1, "period": 2, "radius": 145},
    4:  {"symbol": "Be", "group": 2, "period": 2, "radius": 105},
    5:  {"symbol": "B",  "group": 13, "period": 2, "radius": 85},
    6:  {"symbol": "C",  "group": 14, "period": 2, "radius": 70},
    7:  {"symbol": "N",  "group": 15, "period": 2, "radius": 65},
    8:  {"symbol": "O",  "group": 16, "period": 2, "radius": 60},
    9:  {"symbol": "F",  "group": 17, "period": 2, "radius": 50},
    10: {"symbol": "Ne", "group": 18, "period": 2, "radius": 38},
    # ... continue this pattern or extend as needed ...
}

# Define a color palette for up to N clusters (pastels work well for halos)
CLUSTER_COLORS = [
    '#FFD700',  # Gold
    '#FF69B4',  # Pink
    '#00FFFF',  # Aqua
    '#90EE90',  # Light Green
    '#FFA500',  # Orange
    '#00CED1',  # Turquoise
    '#B0E0E6',  # Powder Blue
    '#FFDAB9',  # Peach Puff
    '#E6E6FA',  # Lavender
    '#E0FFFF',  # Light Cyan
    '#FFFACD',  # Lemon Chiffon
    '#FFE4E1',  # Misty Rose
    # Add more colors if you expect more clusters
]

# --- System State Container ---
system_state = type('SystemState', (), {})()
system_state.emergence_counter = 0

phi = (1 + math.sqrt(5)) / 2
pi = math.pi

truth_history = {
    "alpha_dragon": [],
    "been": []
}

alpha_truth_history = []
been_truth_history = []

alpha_truth_feedback = 0.0

# Global Truth Smoother for rhythmic modulation stability
truth_smoother = {'value': 0.0, 'alpha': 0.05, 'decay': 0.001}

# 🐞 Debug Visuals Flag
DEBUG_VISUALS = False  # Set to False to disable all debug visuals

import os, csv

random.seed(42)

def export_cluster_trace_csv(csv_path="alpha_dragon_cluster_center_trace.csv"):
    # ensure header: frame,cx,cy
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "cx", "cy"])
        for fr, cx, cy in cluster_center_trace:
            w.writerow([fr, f"{cx:.6f}", f"{cy:.6f}"])

def _save_csv_next_to_png(default_png="alpha_dragon_charge_bridges.png"):
    # put CSV next to the PNG (same folder)
    base_dir = os.path.dirname(os.path.abspath(default_png))
    csv_path = os.path.join(base_dir, "alpha_dragon_cluster_center_trace.csv")
    export_cluster_trace_csv(csv_path)
    print(f"📄 Cluster center trace saved to: {csv_path}")

def assign_cycle_ids(lattice):
    """Detects and assigns cycle IDs to nodes based on their bridges."""
    G = nx.Graph()
    for node in lattice:
        G.add_node(node)
        for bridge in getattr(node, 'bridges', []):
            G.add_edge(node, bridge)

    cycles = list(nx.cycle_basis(G))
    for i, cycle in enumerate(cycles):
        for node in cycle:
            node.cycle_id = i

def assign_echo_clusters(lattice):
    cluster_id = 0
    visited = set()

    for node in lattice:
        if node in visited or not getattr(node, 'echo_coherent', False):
            continue

        cluster = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited or not getattr(current, 'echo_coherent', False):
                continue
            visited.add(current)
            cluster.append(current)
            for bridge in current.bridges:
                if getattr(bridge, 'echo_coherent', False) and bridge not in visited:
                    stack.append(bridge)

        if len(cluster) >= 2:
            for member in cluster:
                member.echo_cluster_id = cluster_id
            cluster_id += 1

def get_cycle_color(cycle_id):
    """Returns a consistent color based on the cycle ID."""
    random.seed(cycle_id)
    return (random.random(), random.random(), random.random())

def update_discharge_history(node):
    """
    Tracks recent pulse and entropy history for the node,
    enabling smarter instability detection.
    """
    if not hasattr(node, 'pulse_history'):
        node.pulse_history = []
    
    node.pulse_history.append(node.update_pulse())
    
    # Limit history to avoid runaway memory
    if len(node.pulse_history) > 20:
        node.pulse_history.pop(0)

    # Entropy tracking
    if not hasattr(node, 'entropy_history'):
        node.entropy_history = []
    
    node.entropy_history.append(getattr(node, 'entropy', 0))

    if len(node.entropy_history) > 20:
        node.entropy_history.pop(0)
    
    # Oscillation tracking
    if not hasattr(node, 'oscillation_history'):
        node.oscillation_history = []

    if not hasattr(node, 'adaptive_dampening'):
        node.adaptive_dampening = 1.0    

    node.oscillation_history.append(getattr(node, 'pulse', 0))

    # Optional memory cap
    if len(node.oscillation_history) > 20:
        node.oscillation_history.pop(0)
    
    # Oscillation Spike Detection
        if len(node.oscillation_history) >= 5:
            recent_oscillations = node.oscillation_history[-5:]
            oscillation_spike = max(recent_oscillations) - min(recent_oscillations)

            if oscillation_spike > 0.4:  # Adjustable sensitivity
                node.adaptive_dampening *= 1.15

def detect_echo_coherence(lattice, frame, positions):
    """
    Flags nodes that are echoing in synchrony with others.
    """
    echo_snapshots = []
    for i, node in enumerate(lattice):
        if node.discharged and is_echo_match(node, frame, positions, i):
            snapshot = {
                'shell_id': getattr(node, 'shell_id', None),
                'pressure_level': getattr(node, 'pressure_level', 0),
                'bridge_count': len(node.bridges),
                'node': node
            }
            echo_snapshots.append(snapshot)

    # Compare echoes for coherence
    for i in range(len(echo_snapshots)):
        for j in range(i + 1, len(echo_snapshots)):
            a, b = echo_snapshots[i], echo_snapshots[j]
            if (
                a['shell_id'] == b['shell_id'] and
                abs(a['pressure_level'] - b['pressure_level']) < 1.0 and
                a['bridge_count'] == b['bridge_count']
            ):
                cluster_id = f"{a['shell_id']}_{a['pressure_level']}_{a['bridge_count']}"
                a['node'].echo_coherent = True
                b['node'].echo_coherent = True
                a['node'].coherence_cluster_id = cluster_id
                b['node'].coherence_cluster_id = cluster_id

def is_echo_match(node, frame, positions, i):
    """
    Returns True if the current discharge matches any in recent history.
    """
    if not node.discharged or not node.discharge_history:
        return False

    current = {
        'shell_id': getattr(node, 'shell_id', None),
        'pressure_level': getattr(node, 'pressure_level', 0),
        'bridge_count': len(node.bridges)
    }

    for past in node.discharge_history:
        if (
            current['shell_id'] == past['shell_id'] and
            abs(current['pressure_level'] - past['pressure_level']) < 1.0 and
            current['bridge_count'] == past['bridge_count']
        ):
            node.echo_count += 1
            node.element.echo_trail.append((frame, positions[i]))
            return True

    return False

class Element:
    def __init__(self, atomic_number, name, mass, density, shell_structure, electronegativity=2.0, ionization=10.0, spin_direction=1):
        self.atomic_number = atomic_number
        self.name = name
        self.mass = mass
        self.density = density
        self.shell_structure = shell_structure
        self.electronegativity = electronegativity
        self.ionization = ionization
        self.pulse_amplitude = round((self.ionization - 5.0) / 10.0, 2)
        n = sum(shell_structure)
        theta = 1
        self.energy_scalar = round((phi * pi * n) / (atomic_number * math.log(atomic_number + 1)) + 0.05, 6)
        self.energy_vector = (1j * phi * pi * theta * n) / (atomic_number * math.log(atomic_number + 1))
        self.tunneling_point = False
        self.echo_trail = []  # Stores (frame, position) tuples of echo hits
        self.position = (0, 0)  # Default for periodic table plotting
        self.radius = 0.1       # Default scaled size
        self.spin_direction = spin_direction

class LatticeNode:
    def __init__(self, position, element):
        self.position = position
        self.phase = self.determine_phase()
        self.echo_cluster_id = None  # Will be assigned if part of a coherence group
        self.trait_memory = []  # 🧠 Historical snapshots (time, pulse, velocity, echo_count)
        self.last_pulse = 0.0   # ⏪ Used for velocity calc
        self.pulse_velocity = 0.0
        self.element = element
        self.bridges = []
        self.bridge_tension = self.calculate_bridge_tension()
        self.cycle_id = None  # Will be assigned later if part of a cycle
        self.time = 0
        self.highlight = False  # 🔦 Start with no highlight; toggled during simulation
        self.discharged = False  # Tracks if node discharged this frame
        self.discharge_history = []  # Holds up to 5 recent discharge snapshots
        self.echo_count = 0  # Tracks how many times this node has echoed its past
        self.hollowed = False
        self.pressure_level = 0.0
        self.coherence_cluster_id = None
        self.pressure_threshold = self.calculate_pressure_threshold()
        self.cluster_color = random.choice(['cyan', 'magenta', 'yellow', 'violet', 'lime', 'orange'])
        self.mass = 1.0  # Default neutral mass
        self.shell_memory = deque(maxlen=100)  # Keeps last 100 shell states
        self.is_mirrored = False  # Default unless overridden
        self.pressure = 0.0
        self.truth_resonance = 0.0
        self.adaptive_dampening = 1.0
        self.shell_resonance_log = []

    def log_shell_resonance(self, resonance_value):
        if len(self.shell_resonance_log) >= 10:
            self.shell_resonance_log.pop(0)  # keep last 10
        self.shell_resonance_log.append(resonance_value)

    def update_pulse(self, raw=False):
        self.time += 0.1

        if raw:
         return self.element.pulse_amplitude * math.sin(self.time)

        shell_level = getattr(self.element, 'shell_level', 1)
        decay = 1 / shell_level if shell_level > 0 else 1
        base_amplitude = self.element.pulse_amplitude
        phase_offset = self.element.atomic_number * 0.1
        damping = 1 / (1 + len(self.bridges)) * 0.1

        pulse = base_amplitude * math.sin(self.time + phase_offset) * decay
        self.pressure_level *= 0.98
        self.pressure_level += abs(pulse) * 0.01 * damping

        # 🧠 Log traits for recursive intelligence
        self.pulse_velocity = abs(pulse - self.last_pulse) / 0.1  # ∆pulse over timestep
        self.trait_memory.append((self.time, pulse, self.pulse_velocity, self.echo_count))

        # --- Feedback Mechanism: Truth and Alignment ---
        if len(self.trait_memory) >= 5:
            recent_traits = self.trait_memory[-5:]  # Last 5 memory entries
            avg_velocity = sum(t[2] for t in recent_traits) / 5
            avg_echo = sum(t[3] for t in recent_traits) / 5

        # Truth feedback: high pulse velocity + high echo = alignment
            self.truth_feedback = avg_velocity * avg_echo

        # Alignment score ranges 0–1 for visualization
            self.alignment_score = min(1.0, self.truth_feedback)

        # Keep recent 20 for memory compression
        if len(self.trait_memory) > 20:
         self.trait_memory.pop(0)

        self.last_pulse = pulse  # Update for next frame

       # Decay shell level over time if not interacting
        if (
            self.pressure_level < 8 and
            not self.highlight and
            self.element is not None and
            hasattr(self.element, 'shell_level') and
            self.element.shell_level > 0
        ):

           self.element.shell_level -= 0.02  # Decay rate
           self.element.shell_level = max(0, self.element.shell_level)  # Clamp at 0

        return pulse
    
    def update_coherence_cluster(self, neighbors, phase_tolerance=0.1, charge_tolerance=0.1):
        for neighbor in neighbors:
            if not hasattr(neighbor, 'phase') or not hasattr(neighbor, 'charge_level'):
               continue
        
            phase_match = abs(self.phase - neighbor.phase) <= phase_tolerance
            charge_match = abs(self.charge_level - neighbor.charge_level) <= charge_tolerance
        
            if phase_match and charge_match:
                # If either has a cluster ID, use that
                cluster_id = self.coherence_cluster_id or neighbor.coherence_cluster_id
                if cluster_id is None:
                    # Create new ID if neither had one
                    cluster_id = f"cluster_{random.randint(1000, 9999)}"
                self.coherence_cluster_id = cluster_id
                neighbor.coherence_cluster_id = cluster_id

    def calculate_pressure_threshold(self):
        bridge_factor = 0.3 + len(self.bridges) * 0.1       # Pressure scales with connections
        shell_factor = 1 + len(self.element.shell_structure) * 0.2  # Deeper shells hold more
        return bridge_factor * shell_factor

    def calculate_bridge_tension(self):
        if not self.bridges:
         return 0.0
        tension = sum(abs(self.element.energy_scalar - b.element.energy_scalar) for b in self.bridges)
        return round(tension / len(self.bridges), 4)
    def determine_phase(self):
        r = math.sqrt(self.position[0]**2 + self.position[1]**2)
        if r < 2:
            return "Alpha"
        elif r < 4:
            return "Beta"
        elif r < 6:
            return "Gamma"
        elif r < 8:
            return "Delta"
        else:
            return "Omega"

def is_tunneling_point(element, prev_el=None, next_el=None):
    default_density = 0.0
    prev_density = prev_el.density if prev_el else default_density
    next_density = next_el.density if next_el else default_density
    relative_density_peak = element.density > prev_density and element.density > next_density
    return element.density > 1.5 or relative_density_peak

def generate_sample_lattice():
    elements = [
    Element(1, "Hydrogen", 1.008, 8.988e-05, [1]),
    Element(2, "Helium", 4.0026, 0.0001785, [2]),
    Element(3, "Lithium", 6.94, 0.534, [2, 1]),
    Element(4, "Beryllium", 9.0122, 1.85, [2, 2]),
    Element(5, "Boron", 10.81, 2.34, [2, 3]),
    Element(6, "Carbon", 12.011, 2.267, [2, 4]),
    Element(7, "Nitrogen", 14.007, 1.251, [2, 5]),
    Element(8, "Oxygen", 15.999, 1.429, [2, 6]),
    Element(9, "Fluorine", 18.998, 1.696, [2, 7]),
    Element(10, "Neon", 20.18, 0.9002, [2, 8]),
    Element(11, "Sodium", 22.99, 0.968, [2, 8, 1]),
    Element(12, "Magnesium", 24.305, 1.738, [2, 8, 2]),
    Element(13, "Aluminum", 26.982, 2.7, [2, 8, 3]),
    Element(14, "Silicon", 28.085, 2.3296, [2, 8, 4]),
    Element(15, "Phosphorus", 30.974, 1.82, [2, 8, 5]),
    Element(16, "Sulfur", 32.06, 2.067, [2, 8, 6]),
    Element(17, "Chlorine", 35.45, 3.214, [2, 8, 7]),
    Element(18, "Argon", 39.948, 1.784, [2, 8]),
    Element(19, "Potassium", 39.098, 0.862, [2, 8, 8, 1]),
    Element(20, "Calcium", 40.078, 1.55, [2, 8, 8, 2]),
    Element(21, "Scandium", 44.956, 2.985, [2, 8, 9, 2]),
    Element(22, "Titanium", 47.867, 4.506, [2, 8, 10, 2]),
    Element(23, "Vanadium", 50.942, 6.11, [2, 8, 11, 2]),
    Element(24, "Chromium", 51.996, 7.19, [2, 8, 13, 1]),
    Element(25, "Manganese", 54.938, 7.43, [2, 8, 13, 2]),
    Element(26, "Iron", 55.845, 7.87, [2, 8, 14, 2]),
    Element(27, "Cobalt", 58.933, 8.9, [2, 8, 15, 2]),
    Element(28, "Nickel", 58.693, 8.9, [2, 8, 16, 2]),
    Element(29, "Copper", 63.546, 8.96, [2, 8, 18, 1]),
    Element(30, "Zinc", 65.38, 7.14, [2, 8, 18, 2]),
    Element(31, "Gallium", 69.723, 5.91, [2, 8, 18, 3]),
    Element(32, "Germanium", 72.63, 5.323, [2, 8, 18, 4]),
    Element(33, "Arsenic", 74.922, 5.776, [2, 8, 18, 5]),
    Element(34, "Selenium", 78.971, 4.809, [2, 8, 18, 6]),
    Element(35, "Bromine", 79.904, 3.119, [2, 8, 18, 7]),
    Element(36, "Krypton", 83.798, 3.749, [2, 8, 18, 8]),
    Element(37, "Rubidium", 85.468, 1.532, [2, 8, 18, 8, 1]),
    Element(38, "Strontium", 87.62, 2.64, [2, 8, 18, 8, 2]),
    Element(39, "Yttrium", 88.906, 4.47, [2, 8, 18, 9, 2]),
    Element(40, "Zirconium", 91.224, 6.52, [2, 8, 18, 10, 2]),
    Element(41, "Niobium", 92.906, 8.57, [2, 8, 18, 12, 1]),
    Element(42, "Molybdenum", 95.95, 10.28, [2, 8, 18, 13, 1]),
    Element(43, "Technetium", 98.0, 11.5, [2, 8, 18, 13, 2]),
    Element(44, "Ruthenium", 101.07, 12.37, [2, 8, 18, 15, 1]),
    Element(45, "Rhodium", 102.91, 12.41, [2, 8, 18, 16, 1]),
    Element(46, "Palladium", 106.42, 12.02, [2, 8, 18, 18]),
    Element(47, "Silver", 107.87, 10.49, [2, 8, 18, 18, 1]),
    Element(48, "Cadmium", 112.41, 8.65, [2, 8, 18, 18, 2]),
    Element(49, "Indium", 114.82, 7.31, [2, 8, 18, 18, 3]),
    Element(50, "Tin", 118.71, 7.31, [2, 8, 18, 18, 4]),
    Element(51, "Antimony", 121.76, 6.697, [2, 8, 18, 18, 5]),
    Element(52, "Tellurium", 127.6, 6.24, [2, 8, 18, 18, 6]),
    Element(53, "Iodine", 126.9, 4.93, [2, 8, 18, 18, 7]),
    Element(54, "Xenon", 131.29, 5.9, [2, 8, 18, 18, 8]),
    Element(55, "Cesium", 132.91, 1.93, [2, 8, 18, 18, 8, 1]),
    Element(56, "Barium", 137.33, 3.62, [2, 8, 18, 18, 8, 2]),
    Element(57, "Lanthanum", 138.91, 6.15, [2, 8, 18, 18, 9, 2]),
    Element(58, "Cerium", 140.12, 6.77, [2, 8, 18, 19, 9, 2]),
    Element(59, "Praseodymium", 140.91, 6.77, [2, 8, 18, 21, 8, 2]),
    Element(60, "Neodymium", 144.24, 7.01, [2, 8, 18, 22, 8, 2]),
    Element(61, "Promethium", 145.0, 7.26, [2, 8, 18, 23, 8, 2]),
    Element(62, "Samarium", 150.36, 7.52, [2, 8, 18, 24, 8, 2]),
    Element(63, "Europium", 151.96, 5.24, [2, 8, 18, 25, 8, 2]),
    Element(64, "Gadolinium", 157.25, 7.9, [2, 8, 18, 25, 9, 2]),
    Element(65, "Terbium", 158.93, 8.23, [2, 8, 18, 27, 8, 2]),
    Element(66, "Dysprosium", 162.5, 8.55, [2, 8, 18, 28, 8, 2]),
    Element(67, "Holmium", 164.93, 8.8, [2, 8, 18, 29, 8, 2]),
    Element(68, "Erbium", 167.26, 9.07, [2, 8, 18, 30, 8, 2]),
    Element(69, "Thulium", 168.93, 9.32, [2, 8, 18, 31, 8, 2]),
    Element(70, "Ytterbium", 173.04, 6.9, [2, 8, 18, 32, 8, 2]),
    Element(71, "Lutetium", 174.97, 9.84, [2, 8, 18, 32, 9, 2]),
    Element(72, "Hafnium", 178.49, 13.31, [2, 8, 18, 32, 10, 2]),
    Element(73, "Tantalum", 180.95, 16.69, [2, 8, 18, 32, 11, 2]),
    Element(74, "Tungsten", 183.84, 19.25, [2, 8, 18, 32, 12, 2]),
    Element(75, "Rhenium", 186.21, 21.02, [2, 8, 18, 32, 13, 2]),
    Element(76, "Osmium", 190.23, 22.59, [2, 8, 18, 32, 14, 2]),
    Element(77, "Iridium", 192.22, 22.56, [2, 8, 18, 32, 15, 2]),
    Element(78, "Platinum", 195.08, 21.45, [2, 8, 18, 32, 17, 1]),
    Element(79, "Gold", 196.97, 19.32, [2, 8, 18, 32, 18, 1]),
    Element(80, "Mercury", 200.59, 13.53, [2, 8, 18, 32, 18, 2]),
    Element(81, "Thallium", 204.38, 11.85, [2, 8, 18, 32, 18, 3]),
    Element(82, "Lead", 207.2, 11.34, [2, 8, 18, 32, 18, 4]),
    Element(83, "Bismuth", 208.98, 9.78, [2, 8, 18, 32, 18, 5]),
    Element(84, "Polonium", 209.0, 9.2, [2, 8, 18, 32, 18, 6]),
    Element(85, "Astatine", 210.0, 7.0, [2, 8, 18, 32, 18, 7]),
    Element(86, "Radon", 222.0, 9.73, [2, 8, 18, 32, 18, 8]),
    Element(87, "Francium", 223.0, 1.87, [2, 8, 18, 32, 18, 8, 1]),
    Element(88, "Radium", 226.0, 5.5, [2, 8, 18, 32, 18, 8, 2]),
    Element(89, "Actinium", 227.0, 10.07, [2, 8, 18, 32, 18, 9, 2]),
    Element(90, "Thorium", 232.04, 11.72, [2, 8, 18, 32, 18, 10, 2]),
    Element(91, "Protactinium", 231.04, 15.37, [2, 8, 18, 32, 20, 9, 2]),
    Element(92, "Uranium", 238.03, 18.95, [2, 8, 18, 32, 21, 9, 2]),
    Element(93, "Neptunium", 237.0, 20.45, [2, 8, 18, 32, 22, 9, 2]),
    Element(94, "Plutonium", 244.0, 19.84, [2, 8, 18, 32, 24, 8, 2]),
    Element(95, "Americium", 243.0, 13.69, [2, 8, 18, 32, 25, 8, 2]),
    Element(96, "Curium", 247.0, 13.51, [2, 8, 18, 32, 25, 9, 2]),
    Element(97, "Berkelium", 247.0, 14.78, [2, 8, 18, 32, 27, 8, 2]),
    Element(98, "Californium", 251.0, 15.1, [2, 8, 18, 32, 28, 8, 2]),
    Element(99, "Einsteinium", 252.0, 8.84, [2, 8, 18, 32, 29, 8, 2]),
    Element(100, "Fermium", 257.0, 9.7, [2, 8, 18, 32, 30, 8, 2]),
    Element(101, "Mendelevium", 258.0, 10.3, [2, 8, 18, 32, 31, 8, 2]),
    Element(102, "Nobelium", 259.0, 9.9, [2, 8, 18, 32, 32, 8, 2]),
    Element(103, "Lawrencium", 262.0, 14.4, [2, 8, 18, 32, 32, 9, 2]),
    Element(104, "Rutherfordium", 267.0, 17.0, [2, 8, 18, 32, 32, 10, 2]),
    Element(105, "Dubnium", 270.0, 18.0, [2, 8, 18, 32, 32, 11, 2]),
    Element(106, "Seaborgium", 271.0, 18.5, [2, 8, 18, 32, 32, 12, 2]),
    Element(107, "Bohrium", 270.0, 19.0, [2, 8, 18, 32, 32, 13, 2]),
    Element(108, "Hassium", 277.0, 22.0, [2, 8, 18, 32, 32, 14, 2]),
    Element(109, "Meitnerium", 278.0, 20.0, [2, 8, 18, 32, 32, 15, 2]),
    Element(110, "Darmstadtium", 281.0, 19.0, [2, 8, 18, 32, 32, 17, 1]),
    Element(111, "Roentgenium", 282.0, 17.0, [2, 8, 18, 32, 32, 18, 1]),
    Element(112, "Copernicium", 285.0, 14.0, [2, 8, 18, 32, 32, 18, 2]),
    Element(113, "Nihonium", 286.0, 13.5, [2, 8, 18, 32, 32, 18, 3]),
    Element(114, "Flerovium", 289.0, 14.0, [2, 8, 18, 32, 32, 18, 4]),
    Element(115, "Moscovium", 290.0, 13.5, [2, 8, 18, 32, 32, 18, 5]),
    Element(116, "Livermorium", 293.0, 12.0, [2, 8, 18, 32, 32, 18, 6]),
    Element(117, "Tennessine", 294.0, 11.0, [2, 8, 18, 32, 32, 18, 7]),
    Element(118, "Oganesson", 294.0, 10.0, [2, 8, 18, 32, 32, 18, 8])
    ]
    lattice = []
    for i, el in enumerate(elements):
        if el.atomic_number in atomic_data:
            pdata = atomic_data[el.atomic_number]
            el.position = (
                pdata["group"] * 0.5,   # x-position spacing
                -pdata["period"] * 0.5  # y-position spacing
            )
            el.radius = pdata["radius"] / 100  # scale down for visualization
            # Tagging element category for future color logic or interactions
            if el.atomic_number in range(3, 13) or el.atomic_number in range(19, 31):
                el.category = "metal"
            elif el.atomic_number in range(5, 7) or el.atomic_number in range(14, 17):
                el.category = "metalloid"
            else:
                el.category = "nonmetal"

        else:
            # Fallback radial spiral for rest of periodic table
            theta = i * 0.2
            radius = 1.0 + i * 0.07
            el.position = (
                radius * math.cos(theta),
                radius * math.sin(theta)
            )
            el.radius = 0.1  # Default visual size

        node = LatticeNode((i, 0, 0), el)
        node.prev_charge = 0.0  # Default until charge is set dynamically
        node.entropy_score = 0.0
        el.pulse_amplitude *= 1.5  # Boost pulse strength for activation
        el.energy_scalar = el.mass / (el.electronegativity + 1e-6)  # Avoid divide-by-zero
        el.energy_scalar = el.pulse_amplitude * el.radius * 2.0  # Add energy metric
        prev = elements[i - 1] if i > 0 else None
        next_ = elements[i + 1] if i < len(elements) - 1 else None
        node.element.tunneling_point = is_tunneling_point(el, prev, next_)
        lattice.append(node)
    return lattice

def form_charge_bridges(lattice):
    noble_gases = [2, 10, 18, 36, 54, 86, 118]
    for i, node1 in enumerate(lattice):
        e1 = node1.element
        for j, node2 in enumerate(lattice):
            if i >= j: continue
            e2 = node2.element
            dx = node1.position[0] - node2.position[0]
            dy = node1.position[1] - node2.position[1]
            dz = node1.position[2] - node2.position[2]
            distance = math.sqrt(dx**2 + dy**2 + dz**2)
            if distance > 3:
                continue
            phase_diff = abs(e1.pulse_amplitude - e2.pulse_amplitude)
            energy_diff = abs(e1.energy_scalar - e2.energy_scalar)
            if e1.atomic_number in noble_gases or e2.atomic_number in noble_gases:
                electroneg_diff = 0.0
            else:
                electroneg_diff = abs(e1.electronegativity - e2.electronegativity)
            if phase_diff < 1.0 and energy_diff < 0.5 and electroneg_diff < 2.0:
                node1.bridges.append(node2)
                node2.bridges.append(node1)

def propagate_multilayer_effects(lattice, propagation_depth=2):
    """
    Spreads influence from high atomic number nodes to nearby nodes.
    Adds 'layered_effect' to nodes influenced by higher layers.
    """
    noble_gases = [2, 10, 18, 36, 54, 86, 118]
    layered_elements = [e for e in lattice if e.element.atomic_number >= 36]  # Starting from Krypton up

    for origin in layered_elements:
        visited = set()
        queue = [(origin, 0)]
        while queue:
            current_node, depth = queue.pop(0)
            if current_node in visited or depth > propagation_depth:
                continue
            visited.add(current_node)

            # Influence diminishes with distance
            decay_factor = 1.0 / (depth + 1)
            current_node.layered_effect = current_node.layered_effect + decay_factor if hasattr(current_node, 'layered_effect') else decay_factor

            for neighbor in current_node.bridges:
                queue.append((neighbor, depth + 1))

    print(f"🔁 Layered Element Propagation completed across {len(layered_elements)} high-order nodes.")

def visualize_charge_bridges(lattice):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    # STEP 1: Compute normalized charge for colormap
    charges = [getattr(n, 'charge', 0.0) for n in lattice]
    max_charge = max(charges) or 1.0  # Avoid division by zero
    normalized_charge = [c / max_charge for c in charges]

    # STEP 2: Setup colormap
    from matplotlib import cm
    cmap = cm.get_cmap('plasma')  # Or 'viridis', 'coolwarm', 'inferno'
    charge_colors = [cmap(val) for val in normalized_charge]

    # Identify the node with the highest truth_alignment
    truth_alignments = [getattr(node.element, 'truth_alignment', 0.0) for node in lattice]
    max_truth_idx = truth_alignments.index(max(truth_alignments))

    # STEP 3: Plot nodes using color map
    for i, node in enumerate(lattice):
        x = node.position[0]
        y = node.element.pulse_amplitude
        ax.scatter(x, y, color=charge_colors[i], edgecolors='k', s=100, zorder=2)
        # Optional glow ring for active nodes
        if getattr(node, 'active', False):
            ax.plot(
                x, y,
                marker='o',
                markersize=16,
                markeredgewidth=2.5,
                markeredgecolor='deepskyblue',
                markerfacecolor='none',
                alpha=0.5,
                zorder=1.9
            )

        # Compute distance from center (for font scaling)
        distance = (x**2 + y**2)**0.5
        max_dist = 5.0  # Approximate max radial distance
        normalized_dist = min(distance / max_dist, 1.0)

        # Scale font size based on radial proximity
        font_size = 12 - (6 * normalized_dist)

        if i == max_truth_idx:
            ax.text(x, y + 0.05, node.element.name, ha='center', fontsize=font_size + 2, fontweight='bold', color='gold')
        else:
            ax.text(x, y + 0.05, node.element.name, ha='center', fontsize=font_size)

        for bridge in node.bridges:
            x2 = bridge.position[0]
            y2 = bridge.element.pulse_amplitude
            ax.plot([x, x2], [y, y2], 'b-', alpha=0.3)
    ax.set_title("AlphaDragon Charge Bridge Network")
    ax.set_xlabel("Element Index")
    ax.set_ylabel("Pulse Amplitude")
    plt.grid(True)
    plt.tight_layout()
    from matplotlib.colors import Normalize
    norm = Normalize(vmin=0.0, vmax=1.0)  # charges were normalized 0..1 above
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    cbar = plt.colorbar(sm, ax=ax, orientation='vertical', shrink=0.75, pad=0.02)
    cbar.set_label('Charge (normalized)')

    plt.savefig("alpha_dragon_charge_bridges.png")
    plt.show()

def equilibrate_pressure(lattice):
    """
    Redistributes pressure by averaging it across connected nodes.
    Helps stabilize initial system state before simulation begins.
    """
    for node in lattice:
        if not node.bridges:
            continue
        avg_pressure = sum(getattr(neighbor, 'pressure_level', 0) for neighbor in node.bridges) / len(node.bridges)
        node.pressure_level = (node.pressure_level + avg_pressure) / 2.0

def recursive_phase_stabilization(lattice, coherence_threshold=0.6):
    """
    Smooths out chaotic behavior by reinforcing dominant phase states in coherent clusters.
    """
    for node in lattice:
        if not hasattr(node, 'phase_state'):
            continue

        # Count neighboring phase agreement
        same_phase_count = 0
        total_neighbors = 0
        for neighbor in getattr(node, 'bridges', []):
            if hasattr(neighbor, 'phase_state'):
                total_neighbors += 1
                # Only count agreement if node is not in ghost state
                if node.phase_state != 'ghost' and neighbor.phase_state == node.phase_state:
                    same_phase_count += 1

        if total_neighbors == 0:
            continue

        coherence = same_phase_count / total_neighbors
        if coherence < coherence_threshold and node.phase_state == 'harmonic':
            node.phase_state = 'chaotic'
        elif coherence >= coherence_threshold and node.phase_state == 'chaotic':
            node.phase_state = 'harmonic'

def dampen_entropy_outliers(lattice, entropy_limit=0.9, damping_rate=0.1):
    """
    Dampens extreme entropy values to stabilize chaotic nodes, scaled with system truth.
    """
    global truth_smoother  # Tie damping influence to system stability

    for node in lattice:
        if hasattr(node, 'entropy'):
            stability = 0.5 + 0.5 * truth_smoother['value']  # Range 0.5 to 1.0
            dynamic_damping = damping_rate * stability

            if node.entropy > entropy_limit:
                excess = node.entropy - entropy_limit
                node.entropy -= excess * dynamic_damping

            if node.entropy < -0.01:  # Gentle clamp for negatives
                node.entropy = 0.0

def apply_phase_oscillation_modulation(lattice, base_modulation=0.05):
    """
    Slightly adjusts node pulse frequency based on phase state to introduce rhythmic coherence.
    Noise modulation now respects system stability (truth_smoother).
    """
    global truth_smoother

    phase_mods = {
        'ghost': 0.85,     # Ghost state pulls system lower, sluggish
        'harmonic': 1.0,   # Neutral baseline
        'chaotic': 1.1,    # Slightly exaggerated instability
        'reborn': 1.075    # Grows stronger as truth builds
    }

    for node in lattice:
        base_freq = getattr(node, 'base_frequency', 1.0)
        mod_factor = phase_mods.get(getattr(node, 'phase_state', 'harmonic'), 1.0)

        # Noise diminishes as truth improves
        stability = 1.0 - min(truth_smoother['value'], 1.0)
        noise = random.uniform(-base_modulation, base_modulation) * stability

        # Additional subtle modulation boost for high truth states
        if truth_smoother['value'] > 0.7:
           noise *= 1 + 0.05 * (truth_smoother['value'] - 0.7)

        # Non-linear boost scales with system truth
        truth_boost = 1 + 0.2 * (truth_smoother['value'] ** 0.5)

        # Truth-weighted noise suppression (more stability at low Truth)
        noise_damping = 1 - (0.5 * (1 - truth_smoother['value']))
        damped_noise = noise * noise_damping

        node.frequency = base_freq * mod_factor * truth_boost + damped_noise

def update_shell_recursion(lattice):
    """
    Adjusts electron shell counts with truth-aware recursion damping.
    Prevents runaway shell inflation under low system truth conditions.
    """
    max_electrons = [2, 8, 18, 32]

    for node in lattice:
        bridge_count = len(node.bridges)

        if node.element.shell_structure:
            level = len(node.element.shell_structure) - 1
            current = node.element.shell_structure[level]
            max_val = max_electrons[min(level, 3)]

            # Truth-stabilized recursion — shell growth slows at low truth
            truth_damping = 0.25 + 0.75 * truth_smoother['value']
            growth_factor = (1 + (0.03 * bridge_count) * truth_damping)

            # Truth-Weighted Soft Cap on growth
            truth_soft_cap = max_val * (0.5 + 0.5 * truth_smoother['value'])  # Allows ~50% to 100% growth range

            new_val = min(int(current * growth_factor), max_val)
            new_val = min(new_val, truth_soft_cap)

            node.element.shell_structure[level] = new_val

def detect_cycles(lattice, max_depth=6):
    cycles = []

    def dfs(path, visited, current, start, depth):
        if depth > max_depth:
            return
        for neighbor in current.bridges:
            if neighbor == start and depth >= 3:
                cycles.append(path + [start])
                return
            if neighbor not in visited:
                dfs(path + [neighbor], visited | {neighbor}, neighbor, start, depth + 1)

    for node in lattice:
        dfs([node], {node}, node, node, 0)

    return cycles

def trigger_mass_shell_discharge(lattice, frame, discharge_threshold=5):

    """
    Identifies overloaded shell layers based on bridge count.
    Discharges excess shell mass to neighboring nodes proportionally.
    Calculates coherence leak based on pulse synchronization.
    """
    for node in lattice:
        bridge_count = len(node.bridges)
        if not node.element.shell_structure:
            continue

        # Check deepest shell level
        level = len(node.element.shell_structure) - 1
        if node.element.shell_structure[level] > discharge_threshold:
            discharge = int(0.2 * node.element.shell_structure[level])
            node.element.shell_structure[level] -= discharge
            node.highlight = True
            node.discharged = True
            node.discharge_frame = frame


            # Spread discharge to neighbors
            neighbors = node.bridges
            if neighbors:
                per_neighbor = max(1, discharge // len(neighbors))
                for neighbor in neighbors:
                    n_level = len(neighbor.element.shell_structure) - 1
                    if n_level >= 0:
                        neighbor.element.shell_structure[n_level] += per_neighbor

            # 💡 New: Coherence leak based on pulse sync
            try:
                pulse_diffs = [abs(node.update_pulse() - n.update_pulse()) for n in neighbors]
                avg_diff = sum(pulse_diffs) / len(pulse_diffs) if pulse_diffs else 1
                node.coherence_leak = 1 / (1 + avg_diff)
            except Exception as e:
                node.coherence_leak = 0.0
                print(f"⚠️ Coherence Leak Calc Error ({e}) at {node.element.name if hasattr(node.element, 'name') else 'Unknown'}")
                print(f"🌈 Coherence Leak @ {node.element.name}: {node.coherence_leak:.3f}")

                simulate_pressure_dip(lattice)

def on_key(event):
    if event.key == 'r':
        animation_mode[0] = 'radial'
        print("🔄 Switched to Radial Expansion View")
    elif event.key == 'l':
        animation_mode[0] = 'linear'
        print("📊 Switched to Linear Charge Bridge View")

def compute_pressure(lattice):
    """
    Calculates the 'pressure' for each node based on number of bridges and shell fullness.
    This value affects node color and size during visualization.
    """
    for node in lattice:
        if not node.element.shell_structure:
            node.pressure = 0
            continue

        bridge_count = len(node.bridges)
        shell_sum = sum(node.element.shell_structure)
        shell_levels = len(node.element.shell_structure)

        # Combine normalized shell fullness and bridge influence
        fullness_score = shell_sum / (shell_levels * 8)  # assuming max 8 electrons per shell
        node.pressure = round((bridge_count * 0.5) + (fullness_score * 10), 2)

def color_from_pressure(pressure):
    """Returns a gradient from green (low) to red (high) based on pressure level."""
    pressure = min(max(pressure, 0), 20)  # clamp
    ratio = pressure / 20.0
    return (ratio, 1 - ratio, 0.0)

def get_neighbors(node, nodes, radius=1.0):
    neighbors = []
    for other_node in nodes:
        if other_node is not node:
            distance = np.linalg.norm(np.array(node.position) - np.array(other_node.position))
            if distance <= radius:
                neighbors.append(other_node)
    return neighbors

class PulseTracker:
    def __init__(self):
        self.pulse_strength = 0.0
        self.decay_rate = 0.9

    def trigger(self):
        self.pulse_strength = 1.0

    def update(self):
        self.pulse_strength *= self.decay_rate
        return self.pulse_strength

def detect_resonant_clusters(lattice, threshold=3):
    clusters = []
    visited = set()

    def dfs(node, cluster):
        stack = [node]
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.add(current)
                cluster.append(current)
                for neighbor in current.bridges:
                    if neighbor not in visited and len(neighbor.bridges) >= threshold:
                        stack.append(neighbor)

    for node in lattice:
        if node not in visited:
            cluster = []
            dfs(node, cluster)
            if len(cluster) >= 3:
                clusters.append(cluster)

    for i, cluster in enumerate(clusters):
        for node in cluster:
            node.resonant = True
            node.cluster_id = i
        print(f"🌐 Resonant Cluster {i}: Size = {len(cluster)}")

    return clusters

def tag_cluster_intelligence(lattice):
    clusters = []
    visited = set()

    def dfs(start_node, cluster, threshold=3):
        stack = [start_node]
        while stack:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                cluster.append(node)
                for neighbor in node.bridges:
                    if neighbor not in visited and len(neighbor.bridges) >= threshold:
                        stack.append(neighbor)

    for node in lattice:
        if node not in visited:
            cluster = []
            dfs(node, cluster)
            if len(cluster) >= 3:
                clusters.append(cluster)

    for i, cluster in enumerate(clusters, 1):
        positions = [n.position for n in cluster]
        bridge_counts = [len(n.bridges) for n in cluster]
        shell_levels = [len(n.element.shell_structure) for n in cluster]

        center = (
            round(sum(p[0] for p in positions) / len(positions), 2),
            round(sum(p[1] for p in positions) / len(positions), 2),
            round(sum(p[2] for p in positions) / len(positions), 2),
        )

        avg_bridges = sum(bridge_counts) / len(bridge_counts)
        avg_shells = round(sum(shell_levels) / len(shell_levels), 2)
        intelligence = round(math.log(len(cluster) * avg_bridges + 1), 2)  # Logarithmic scaling

        members = [n.element.name for n in cluster]
        for n in cluster:
            n.cluster_memory = {
                'center': center,
                'avg_bridges': avg_bridges,
                'avg_shells': avg_shells,
                'intelligence': intelligence
            }

            # ✅ Step 9: Add persistent memory log
            if not hasattr(n, 'memory_log'):
                n.memory_log = []

            n.memory_log.append({
                'frame': -1,  # Update with actual frame if needed later
                'center': center,
                'avg_bridges': avg_bridges,
                'avg_shells': avg_shells,
                'intelligence': intelligence
            })

        print(f"🧠 Cluster {i}: Members: {len(cluster)}, Center: {center}, "
              f"ShellAvg: {avg_shells}, Intelligence: {intelligence} :: "
              f"{','.join(members[:6])}...")

def compute_alpha_dragon_truth(lattice, frame, T_global=1.0):
    """
    Evaluates how closely the current system aligns with the Alpha Dragon equation.
    Returns a truth-alignment score for diagnostics or overlay use.
    """
    import math

    alpha = 1 / 137.035999084  # Fine-structure constant
    alpha_term = 1 / (alpha ** 3)

    # Gather dynamic quantities from the lattice:
    n_avg = sum(len(node.element.shell_structure) for node in lattice) / len(lattice)
    θ_avg = sum(abs(getattr(node, 'pulse_velocity', 0)) for node in lattice) / len(lattice)
    t_local = frame / 60  # assuming 60fps ~ 1 sec per 60 frames

    φ = (1 + math.sqrt(5)) / 2
    π = math.pi

    # Electromagnetic constants
    ε0 = 8.8541878128e-12      # Vacuum permittivity (F/m)
    ħ = 1.054571817e-34        # Reduced Planck constant (J·s)
    c = 299792458              # Speed of light (m/s)

    # EM term as specified: √(...) * (...)
    em_root = math.sqrt(4 * π * ε0 * ħ * c**2)
    em_linear = 4 * π * ε0 * ħ * c**2
    em_term = em_root * em_linear

    # Placeholder HEnG calculation:
    # Height: avg shell depth
    # Energy: avg pulse
    # Gravity: proxy = average pressure
    shell_height = n_avg
    avg_pulse = sum(abs(node.update_pulse(raw=True)) for node in lattice) / len(lattice)
    if ENABLE_SHELL_LOGGING:
        for node in lattice:
            node.log_shell_resonance(getattr(node, "phase_value", 0.0))
    avg_pressure = sum(getattr(node, 'pressure_level', 0) for node in lattice) / len(lattice)
    HEnG = shell_height * avg_pulse * avg_pressure

    # RHS computation
    rhs = (1j * φ * π * θ_avg * n_avg) * (4 * π**2 * T_global * t_local) * em_term / (HEnG or 1e-6)

    # Compare magnitudes (real comparison for truth metric)
    alignment_score = abs(abs(alpha_term) - abs(rhs)) / abs(alpha_term)
    alignment_score = max(0.0, min(1.0, 1 - alignment_score))  # 1 = perfect alignment

    return alignment_score.real

def compute_alpha_truth_alignment(nodes, truth_field):
    """
    Computes average alignment (cosine similarity) between each node's charge vector and the 'truth' field.
    Returns a float from -1 (opposed) to +1 (aligned).
    """
    if not nodes or truth_field is None:
        return 0.0

    alignments = []
    for node in nodes:
        if hasattr(node, 'charge_vector'):
            dot = np.dot(node.charge_vector, truth_field)
            norm_product = np.linalg.norm(node.charge_vector) * np.linalg.norm(truth_field)
            if norm_product != 0:
                alignments.append(dot / norm_product)

    return np.mean(alignments) if alignments else 0.0

def compute_been_entropy(lattice, frame, area=1.0):
    """
    Computes S_total from the Alpha Dragon BEEN Equation at a given frame.
    Combines spiral mass-energy recursion and surface entropy.
    """
    import math, cmath

    # Constants
    G = 6.67430e-11               # Gravitational constant (m^3 kg^-1 s^-2)
    ε0 = 8.854187817e-12          # Vacuum permittivity (F/m)
    ħ = 1.054571817e-34           # Reduced Planck constant (J·s)
    c = 299792458                 # Speed of light (m/s)
    k_B = 1.380649e-23            # Boltzmann constant (J/K)
    l_p = 1.616255e-35            # Planck length (m)

    # Extract dynamic lattice values
    n_avg = sum(len(node.element.shell_structure) for node in lattice) / len(lattice)
    θ_avg = sum(abs(getattr(node, 'pulse_velocity', 0)) for node in lattice) / len(lattice)
    t_local = frame / 60.0  # assume 60fps ~ 1 second

    φ = (1 + math.sqrt(5)) / 2
    π = math.pi

    # === Term 1: Spiral Curvature Entropy ===
    spiral_term = cmath.exp(1j * φ * π * θ_avg * n_avg)
    spiral_term_squared = spiral_term * spiral_term

    numerator = G * spiral_term_squared * (c ** 2)
    denominator = 4 * π * ε0 * ħ * (t_local ** 2 or 1e-6)  # avoid division by zero
    entropy_spiral = numerator / denominator

    # === Term 2: Surface Entropy ===
    surface_entropy = (k_B * area) / (4 * l_p ** 2)

    # === Total Entropy ===
    S_total = entropy_spiral + surface_entropy

    return abs(S_total)

def compute_classical_been_truth(lattice, frame, A=1.0, t_global=1.0):
    """
    Computes the classical BEEN equation truth alignment score.
    Returns a normalized value to compare with simulation behavior.
    """
    import cmath

    # Constants
    G = 6.67430e-11             # Gravitational constant
    ε0 = 8.854187817e-12        # Vacuum permittivity
    ħ = 1.054571817e-34         # Reduced Planck constant
    c = 299792458               # Speed of light
    kB = 1.380649e-23           # Boltzmann constant
    l_p = 1.616255e-35          # Planck length
    φ = (1 + math.sqrt(5)) / 2  # Golden ratio
    π = math.pi

    # Shell values
    valid_shells = []
    for node in lattice:
        if hasattr(node, "element") and hasattr(node.element, "shell_structure"):
            shells = node.element.shell_structure
            if isinstance(shells, list):
                valid_shells.extend(shells)
            else:
                valid_shells.append(shells)

    s_avg = sum(valid_shells) / len(valid_shells) if valid_shells else 0

    θ = 1  # You can make this dynamic later
    pulse_avg = sum(getattr(node, 'pulse_velocity', 0) for node in lattice) / len(lattice)
    t_local = frame / 60  # seconds, assuming 60fps

    # BEEN Equation
    try:
        phase_term = cmath.exp(1j * φ * π * θ * s_avg)
    except Exception as e:
        print(f"[phase_term error] s_avg={s_avg}: {e}")
        phase_term = 0

    numerator = G * (phase_term * phase_term) * c**2
    denominator = 4 * π * ε0 * ħ * (t_local + 1e-6)**2
    hawking_term = (kB * A) / (4 * l_p**2)

    # Combine total
    S_total = (numerator / denominator) + hawking_term

    # Return normalized score (for plotting/tracking only the real part)
    return abs(S_total.real)

def on_key_press(event):
    if event.key.lower() == 'u':
        show_status_panel[0] = not show_status_panel[0]
        print(f"Status HUD toggled to: {'ON' if show_status_panel[0] else 'OFF'}")

def build_static_artists(ax, lattice, static_artists):
    # 🌈 Set color by phase
    phase_colors = {
        "Alpha": "gold",
        "Beta": "cyan",
        "Gamma": "magenta",
        "Delta": "lime",
        "Omega": "white"
    }

    for node in lattice:
        node_color = phase_colors.get(node.phase, "gray")
        for bridge in getattr(node, 'bridges', []):
            line = plt.Line2D(
                [node.position[0], bridge.position[0]],
                [node.position[1], bridge.position[1]],
                color=node_color, alpha=0.25, linewidth=0.5, zorder=0
            )
            ax.add_line(line)
            static_artists.append(line)

def animate_dual_mode(lattice):
    global overlay_alpha
    overlay_alpha = 0.0
    fig, ax = plt.subplots()
    def _on_close(_evt):
            _save_csv_next_to_png()  # adjust PNG name if you save to a different file

    fig.canvas.mpl_connect("close_event", _on_close)
    fig.canvas.mpl_connect('key_press_event', on_key_press)
    static_artists = []  # Cache for static lines (bridges)
    (ax, lattice, static_artists)
    mode = {'type': 'radial'}
    # -- Pulse Bridges --
    pulse_bridges = []
    for node in lattice:
        for bridge in getattr(node, 'bridges', []):
            pressure = getattr(bridge, 'pressure', 0)
            width = 0.5 + 1.5 * min(pressure / 12.0, 1)  # Scale width with pressure

            line = plt.Line2D(
                [node.position[0], bridge.position[0]],
                [node.position[1], bridge.position[1]],
                color='magenta',
                alpha=overlay_alpha,
                linewidth=width,
                zorder=1
            )
            pulse_bridges.append(line)
            ax.add_line(line)

    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    # After fig, ax = plt.subplots() Truth alignment over time
    rolling_ax = inset_axes(ax, width="28%", height="23%", loc='lower right', borderpad=1.5)

    # -- Shell Bridges --
    shell_bridges = []
    for node in lattice:
        for shell in getattr(node, 'shell_neighbors', []):
            line = plt.Line2D(
                [node.position[0], shell.position[0]],
                [node.position[1], shell.position[1]],
                color='cyan', alpha=0.2, linewidth=2, linestyle='dotted', zorder=0
            )
            shell_bridges.append(line)
            ax.add_line(line)

    focus_mode = {'enabled': False}
    truth_feedback_toggle = {'enabled': True}
    pulse_overlay_toggle = {'enabled': False}
    overlay_alpha = 0.0
    view_reset = {'trigger': False}
    total = len(lattice)
    angles = [2 * math.pi * i / total for i in range(total)]
    base_radius = 1.0
    phi = 1.618
    cmap = cm.get_cmap('viridis')  # Shell-level gradient coloring
    pulse_overlay_toggle['time_counter'] = 0

    def toggle_pulse_overlay(event):
        pulse_overlay_toggle['enabled'] = not pulse_overlay_toggle['enabled']
        print(f"Pulse Overlay {'Enabled' if pulse_overlay_toggle['enabled'] else 'Disabled'}")

    # Global Truth Smoother for stability
    global truth_smoother
    truth_smoother = {'value': 0.0, 'alpha': 0.05, 'decay': 0.001}

    # Top-level helper function (OUTSIDE update)
    def smooth_velocity(current, previous, smoothing=0.2):
        return previous + smoothing * (current - previous)
    

    def draw_status_text(ax, lines, start_xy=(0.05, 0.95), line_spacing=0.04, fontsize=10, color='cyan'):
        """
        Draws a list of status text lines in the top-left of the plot.
        ax: the axis object
        lines: list of strings
        start_xy: (x, y) in axis fraction coordinates (0-1)
        line_spacing: vertical space between lines
        """
        for i, line in enumerate(lines):
            ax.text(start_xy[0], start_xy[1] - i * line_spacing, line,
                    fontsize=fontsize, color=color,
                    transform=ax.transAxes, ha='left', va='top',
                    bbox=dict(facecolor='black', alpha=0.3, edgecolor='none', pad=1.0))
            
    ROLL_N = 100  # Show last 100 frames
    rolling_truth = alpha_truth_history[-ROLL_N:]
    rolling_entropy = been_truth_history[-ROLL_N:]

    rolling_ax.clear()
    rolling_ax.plot(rolling_truth, label="Alpha Dragon", color='cyan', linewidth=2)
    rolling_ax.plot(rolling_entropy, label="Classical BEEN", color='magenta', linewidth=1)
    rolling_ax.set_title("Truth Alignment Over Time", fontsize=8)
    rolling_ax.legend(fontsize=7, loc='upper right', frameon=True)
    rolling_ax.tick_params(axis='both', labelsize=6)
    rolling_ax.set_xticks([])
    rolling_ax.set_yticks([])
    rolling_ax.set_facecolor('white')
    

    def update(frame):
        # STEP 3: Ignite first 5 nodes
        if frame == 0:  # Only trigger once
            for node in lattice[:12]:
                if node.element.shell_structure:
                    node.element.shell_structure[-1] += 12  # Overload the outer shell
                    node.discharged = True
                    node.highlight = True
                    node.pressure_level += 5

        enable_feedback_flags = truth_feedback_toggle["enabled"]
        if enable_feedback_flags:
            for node in lattice:
                node.highlight = True
        else:
            for node in lattice:
                node.highlight = False
        global alpha_truth_history, been_truth_history
        ax.clear()
        compute_pressure(lattice)
        trigger_mass_shell_discharge(lattice, frame=frame)
        
        truth_alignment = compute_alpha_dragon_truth(lattice, frame)
        been_entropy = compute_been_entropy(lattice, frame)
        been_alignment = compute_classical_been_truth(lattice, frame)
        truth_history["alpha_dragon"].append(truth_alignment)
        truth_history["been"].append(been_alignment)

        # Build clusters dictionary: cycle_id -> list of nodes - the yellow dots proof the clustering logic is working and revealing emergent sync between nodes
        clusters = {}
        for node in lattice:
            cid = getattr(node, 'cycle_id', None)
            if cid is not None:
                clusters.setdefault(cid, []).append(node)

        for node in lattice:
            x, y = node.position[0], node.position[1]

            # Highlight cluster nodes (with 3 or more in the group)
            cluster_id = getattr(node, 'cycle_id', None)  # Use the attribute your clustering logic uses
            if cluster_id is not None and len(clusters[cluster_id]) >= 3:
                # Draw a translucent colored circle behind the node (cluster aura)
                cluster_color = CLUSTER_COLORS[cluster_id % len(CLUSTER_COLORS)]  # Each cluster gets its own color
                cluster_halo = plt.Circle((x, y), 0.26, color=cluster_color, alpha=0.24, linewidth=0, zorder=6)
                ax.add_patch(cluster_halo)

        # Compute cluster stats for the HUD
        cluster_sizes = [len(nodes) for nodes in clusters.values()]
        num_clusters = sum(1 for s in cluster_sizes if s >= 3)
        max_cluster_size = max(cluster_sizes) if cluster_sizes else 0
        
        # Calculate Cluster Centers and Intelligence
        cluster_centers = {}
        cluster_intelligence = {}

        for cid, nodes in clusters.items():
            if len(nodes) >= 3:
                # Center of mass
                xs = [n.position[0] for n in nodes]
                ys = [n.position[1] for n in nodes]
                cx, cy = np.mean(xs), np.mean(ys)
                cluster_centers[cid] = (cx, cy)
                # Intelligence score: mean of node alignment (customize as needed)
                mean_align = np.mean([getattr(n, 'alignment_score', 0) for n in nodes])
                cluster_intelligence[cid] = mean_align

        # Only highlight top N clusters by intelligence or size
        N = 1  # Or whatever keeps the visuals clean

        # Sort cluster ids by size or intelligence (pick one)
        sorted_cids = sorted(
            cluster_intelligence,
            key=lambda c: cluster_intelligence[c],  # or len(clusters[c]) for size
            reverse=True
        )[:N]

        # (Assume 'sorted_cids' is your sorted top clusters list)
        if sorted_cids:
            top_cid = sorted_cids[0]
            cx, cy = cluster_centers[top_cid]
            cluster_center_trace.append((frame, cx, cy))
            if len(cluster_center_trace) > MAX_TRACE_LEN:
                cluster_center_trace.pop(0)
        
        # TEST MODE: Simulate varied intelligence scores for visual debugging
        import random
        intelligence_scores = [random.uniform(1, 10) for _ in range(len(cluster_centers))]

        # === VISUAL HEARTBEAT: Cluster & Intelligence Overlay ===
        if 'cluster_centers' in locals() and 'intelligence_scores' in locals():
            try:
                # === Alpha Dragon Stability Pulse & State Awareness ===
                try:
                    active_cluster_count = len(cluster_centers)
                    avg_center_distance = np.mean([np.linalg.norm(center) for center in cluster_centers])
                    spiral_variance = np.var([np.linalg.norm(center) for center in cluster_centers])

                    # Define a "stability pulse" score
                    stability_pulse = (1 / (1 + spiral_variance)) * active_cluster_count

                    # Store for ongoing awareness
                    if 'AD_state' not in globals():
                        AD_state = {'stability_history': [], 'pulse_threshold': 0.75}
                        AD_state['stability_history'].append(stability_pulse)

                    # Rolling awareness check
                    if len(AD_state['stability_history']) > 30:
                        AD_state['stability_history'].pop(0)

                    avg_pulse_recent = np.mean(AD_state['stability_history'])

                    # Visual/log feedback (debug mode)
                    if avg_pulse_recent < AD_state['pulse_threshold']:
                        print(f"[AD Stability Alert] Pulse drop detected: {avg_pulse_recent:.3f}")
                    else:
                        print(f"[AD Stability Nominal] Pulse steady: {avg_pulse_recent:.3f}")

                except Exception as pulse_error:
                    print(f"[AD Pulse Error]: {pulse_error}")

                # === Main Visual Rendering Loop ===
                for idx, center in enumerate(cluster_centers):
                    # Ensure center is iterable with at least 3 elements
                    if not (hasattr(center, "__getitem__") and len(center) >= 3):
                        continue
                    score = intelligence_scores[idx] if idx < len(intelligence_scores) else 0     

                    # Heartbeat circle at cluster center
                    ax.scatter(center[0], center[1], center[2],
                               s=80 + (score * 10),  # pulse size with score
                               c=[[1, 0, 0]],        # bright red
                               alpha=0.8, marker='o', edgecolors='white', linewidths=1.5)
            
                    # Enhanced Heartbeat Pulse
                    pulse_size = 80 + (score * 12)  # bigger scaling
                    pulse_alpha = max(0.2, min(1.0, score / 10))  # fade based on score
                    pulse_color = (1, 0.3 + (score / 20), 0)  # red to orange gradient

                    # Main pulse
                    ax.scatter(center[0], center[1], center[2],
                               s=pulse_size,
                               c=[pulse_color],
                               alpha=pulse_alpha,
                               marker='o',
                       edgecolors='white',
                       linewidths=1.5)

                    # Ripple ring
                    ripple_size = pulse_size + 30
                    ax.scatter(center[0], center[1], center[2],
                               s=ripple_size,
                               facecolors='none',
                               edgecolors='orange',
                               alpha=0.3,
                               linewidths=1.0,
                               linestyle='--')

                    # Label with intelligence score
                    ax.text(center[0], center[1], center[2],
                            f"{score:.2f}",
                            color='white', fontsize=8, ha='center', va='center',
                            bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1))
            except Exception as e:
                print(f"[Visual Heartbeat Error]: {e}")


        # Initialize smoothed velocity safely
        previous_alpha_velocity = alpha_truth_history[-1] if alpha_truth_history else 0
        previous_been_velocity = been_truth_history[-1] if been_truth_history else 0

        raw_alpha_velocity = abs(truth_alignment - truth_history["alpha_dragon"][-1]) if truth_history["alpha_dragon"] else 0
        raw_been_velocity = abs(been_alignment - truth_history["been"][-1]) if truth_history["been"] else 0
       
        # Apply smoothing
        alpha_velocity = smooth_velocity(raw_alpha_velocity, previous_alpha_velocity)
        been_velocity = smooth_velocity(raw_been_velocity, previous_been_velocity)
        # Define feedback and alignment values for display
        truth_feedback = alpha_velocity
        alignment = been_velocity

        # Display current mode clearly on screen
        pretty_mode = "Radial" if mode['type'] == "radial" else "Linear"
        ax.text(0, -1.2, f"🌀 Mode: {pretty_mode}", fontsize=10, color='cyan', ha='left', va='top')

        # Collect per-frame truth values for dynamic comparison
        try:
            alpha_truth = get_truth_value(alpha_velocity)
            been_truth = get_truth_value(been_velocity)
            alpha_truth_history.append(alpha_truth)
            been_truth_history.append(been_truth)
        except Exception as e:
            print("Truth data collection error:", e)

        # Track short-term resonance for graceful stabilization
        if len(alpha_truth_history) >= 1:
            recent_window = alpha_truth_history[-5:]  # 5-frame memory
            alpha_truth_avg = sum(recent_window) / len(recent_window)
            global alpha_truth_feedback
            alpha_truth_feedback = smooth_velocity(alpha_truth_avg, alpha_truth_feedback)
            truth_feedback = alpha_truth_feedback  # Assign feedback for display

        # Append velocity to new history arrays
        alpha_truth_history.append(alpha_velocity)
        been_truth_history.append(been_velocity)

        # Adaptive dampening adjusts based on total truth velocity
        total_velocity = alpha_velocity + been_velocity
        velocity_threshold = 0.15  # Set this based on experimentation
        damping_boost = min(0.1, total_velocity * 0.2)

        if total_velocity > velocity_threshold:
            adaptive_dampening = 0.02 + damping_boost  # Increase baseline damping
        else:
            adaptive_dampening = 0.02  # Default baseline

        # Breathing oscillation modulates damping slightly every frame
        calm_scale = max(0, 1 - total_velocity / 0.5)  # More calm = less motion
        oscillation = 0.05 * math.sin(frame * 0.05) * calm_scale
        adaptive_dampening += oscillation
 
        # Grace buffer to reduce overreactive damping on low changes
        truth_change = abs(alpha_velocity - been_velocity)

        if truth_change < 0.01:  # Small difference? No change.
            pass  # Maintain previous smoother value
        else:
            truth_smoother['value'] = (1 - truth_smoother['decay'])

        adaptive_dampening = 0.02  # Default dampening baseline

        # Truth smoother decay prevents runaway growth
        truth_smoother['value'] *= (1 - truth_smoother['decay'])

        # Calculate unique_shells (number of unique shell IDs in the lattice)
        unique_shells = len(set(getattr(n, 'shell_id', 0) for n in lattice))

        # Calculate alignment_metric_global (average alignment_score across all nodes)
        alignment_metric_global = (
            sum(getattr(n, 'alignment_score', 0) for n in lattice) / len(lattice)
            if lattice else 0
        )

        active_nodes = []
        positions = []

        for i, node in enumerate(lattice):
            node.highlight = False
            update_discharge_history(node)

            if not hasattr(node, 'velocity_history'):
                node.velocity_history = []

            node.velocity_history.append(getattr(node, 'pulse_velocity', 0))

            if len(node.velocity_history) > 20:
                node.velocity_history.pop(0)

            # NEW Safe Spike Detection
            if len(node.velocity_history) >= 5:
                recent_velocities = node.velocity_history[-5:]
                velocity_spike = max(recent_velocities) - min(recent_velocities)

                if velocity_spike > 0.3:  # Adjustable sensitivity
                    adaptive_dampening *= 1.15

            pulse = node.update_pulse()
            triad_index = i // 3
            shell_level = getattr(node, 'shell_level', 0)
            # Normalize shell height to scale with system truth, prevents runaway effects
            normalized_shell = shell_level / (1 + 0.5 * truth_smoother['value'])
            node.pulse_velocity = pulse - getattr(node, 'last_pulse', 0)
            # Clamp extreme negative velocity to stabilize structure
            if node.pulse_velocity < -0.5:
                node.pulse_velocity = -0.5
            node.last_pulse = pulse

            # --- Track entropy delta per node ---
            # Use 'charge' if present; fall back to 'charge_level' to avoid NameError in this build.
            current_charge = getattr(node, 'charge', getattr(node, 'charge_level', 0.0))
            charge_delta = abs(current_charge - getattr(node, 'prev_charge', 0.0))
            node.entropy_score = getattr(node, 'entropy_score', 0.0) + charge_delta
            node.prev_charge = current_charge

            # --- Shell Affinity Memory Logic ---
            if not hasattr(node, 'shell_memory') or not isinstance(node.shell_memory, dict):
                node.shell_memory = {}

            key = (shell_level, triad_index)

            # If this shell+triad combo is already stored, blend it
            if key in node.shell_memory:
                prev_pulse = node.shell_memory[key]
                node.pulse_velocity = 0.5 * node.pulse_velocity + 0.5 * prev_pulse
            else:
                node.shell_memory[key] = node.pulse_velocity

            # --- Surprise Trigger Logic ---
            pulse_jump = abs(node.pulse_velocity - node.last_pulse)
            surprise_threshold = 0.4  # You can adjust this
            node.surprised = pulse_jump > surprise_threshold
           
            # Coherence cluster alignment logic
            neighbors = get_neighbors(node, lattice)  # Replace with your actual neighbor function
            node.update_coherence_cluster(neighbors)

            # --- Emergence Check ---
            surprised_nodes = [n for n in lattice if getattr(n, 'surprised', False)]
            if len(surprised_nodes) > len(lattice) * 0.1:  # More than 10% surprised
                if not hasattr(system_state, 'emergence_counter'):
                    system_state.emergence_counter = 0
                system_state.emergence_counter += 1
            else:
                if hasattr(system_state, 'emergence_counter'):
                    system_state.emergence_counter = max(system_state.emergence_counter - 1, 0)

            # Defer filtering until just before rendering — safer
            is_active = node.pulse_velocity >= 0.05 and node.echo_count >= 5

            damped_shell = math.log(1 + normalized_shell)
            amplification = 1 + (0.07 * damped_shell)
            decay_factor = 1 / (1 + 0.05 * normalized_shell + 0.05)
            modulated_pulse = pulse * amplification * decay_factor
            # Pulse curve correction for smoother amplitude behavior
            pulse_curve = 0.6 / (1 + abs(pulse))  # Keeps outer structure growth linear as amplitude scales

            radius = base_radius + math.log(1 + triad_index * phi) + (modulated_pulse * pulse_curve)

            if mode['type'] == 'linear':
                x = i
                y = pulse
            else:
                theta = angles[i]
                radius = base_radius * math.log(1 + triad_index * phi) + (pulse * 0.6 / (1 + abs(pulse)))
                x = radius * math.cos(theta)
                y = radius * math.sin(theta)

            radius_from_center = math.sqrt(x**2 + y**2)
            shell_width = 0.5
            node.shell_id = int(radius_from_center / shell_width)

            truth_metric = calculate_truth_metric(lattice)
            
            positions.append((x, y))

            if is_active and (abs(pulse) > 0.4 or node.element.tunneling_point):
                node.highlight = True
                active_nodes.append((x, y))

            # Step 6: Dynamic Connections Between Active Nodes
            if is_active:
                for other_node in active_nodes:
                    if other_node is not node:
                        dx = other_node.x - x
                        dy = other_node.y - y
                        dist_sq = dx**2 + dy**2

                        # Draw if close enough and both are coherent
                        if dist_sq < 6.0 and other_node.pulse_velocity > 0.4:
                           link_alpha = 0.2 + 0.1 * min(node.echo_count, other_node.echo_count)
                           ax.plot([x, other_node.x], [y, other_node.y],
                           color='magenta', linewidth=0.5, alpha=link_alpha, zorder=1)

            if abs(pulse) > 0.95:
                ring_radius = 0.2 + 0.05 * abs(pulse)
                ax.add_patch(plt.Circle((x, y), ring_radius, color='deeppink', fill=False, linewidth=2.0, alpha=0.8, zorder=5))

            if node.discharged:
                color = 'white'
            elif node.element.tunneling_point:
                color = 'green'
            elif node.cycle_id is not None:
                color = color_from_pressure(getattr(node, 'pressure_level', 0))
            elif hasattr(node, 'pressure') and node.pressure > 12:
                color = 'red'
            elif hasattr(node, 'pressure') and node.pressure > 8:
                color = 'orange'
            else:
                norm_level = min(getattr(node, 'shell_id', 0) / 10.0, 1.0)
                color = cmap(norm_level)

            # Edge color logic (resonant-aware)
            if hasattr(node, 'resonant') and node.resonant:
                edgecolor = 'cyan'
            elif node.highlight:
                edgecolor = 'yellow'
            else:
                edgecolor = 'none'

            size = 200 if node.highlight else 100
            edgecolor = 'yellow' if node.highlight else 'none'
            ax.scatter(x, y, s=size, color=color, edgecolors=edgecolor, linewidths=1.5, zorder=3)

            # --- Overlay Cluster Centers and Intelligence ---
            for cid in sorted_cids:
                cx, cy = cluster_centers[cid]
                color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]
                ax.scatter(cx, cy, s=180, color=color, alpha=0.12, marker='o', zorder=7)
                intelligence = cluster_intelligence[cid]
                ax.text(
                    cx, cy, f"{intelligence:.2f}", fontsize=12, color=color,
                    ha='center', va='center', weight='bold', zorder=11,
                    bbox=dict(facecolor='black', alpha=0.2, boxstyle='round,pad=0.17')
                )

            # Step 8: Final Output Rendering
            for i, (x, y) in enumerate(positions):
                node = lattice[i]
                size = 200 if node.highlight else 100

            # Final edge color logic
            if hasattr(node, 'resonant') and node.resonant:
                edgecolor = 'cyan'
            elif node.highlight:
                edgecolor = 'yellow'
            else:
                edgecolor = 'none'

            # Final point render
            ax.scatter(x, y,
                       s=size,
                       color=color,  # Comes from previous logic (e.g. pressure, state)
                       edgecolors=edgecolor,
                       linewidths=1.5,
                       zorder=3)
            
            # Calculate alignment for this node (replace with your exact metric variable!)
            alignment = getattr(node, 'alignment_score', 0)

            # Golden halo if breakthrough
            if alignment > best_alignment_score[0]:
                best_alignment_score[0] = alignment
                # Draw a golden halo (thick, low-alpha circle)
                halo = plt.Circle((x, y), 0.18, color='gold', alpha=0.7, linewidth=0, zorder=15)
                ax.add_patch(halo)
                # Optional: print/log breakthrough
                print(f"Breakthrough! Node {getattr(node, 'element', None)} at ({x:.2f},{y:.2f}) reached alignment {alignment:.3f}")
            
            # Step 9: Velocity Vector Trail
            if hasattr(node, 'pulse_velocity') and node.pulse_velocity > 0.2:
                vx = 0.1 * node.pulse_velocity * math.cos(node.phase)
                vy = 0.1 * node.pulse_velocity * math.sin(node.phase)
                ax.plot([x, x - vx], [y, y - vy],
                        color='cyan', alpha=0.3, linewidth=1.0, zorder=1)
                
            # Step 8.5: Self-Energy Reflection Pulse (Resonance Ring)
            if hasattr(node, 'self_energy') and node.self_energy > 0.5:
                pulse_alpha = min(0.8, 0.2 + 0.6 * node.self_energy)
                pulse_ring = plt.Circle(
                    (x, y), 
                    0.5 + 0.3 * node.self_energy, 
                    edgecolor='magenta', 
                    facecolor='none',
                    linestyle='dashed',
                    linewidth=1.5,
                    alpha=pulse_alpha,
                    zorder=5
                )
                ax.add_patch(pulse_ring)

            # ⚡ Step C: Discharge Flash Ring
            if hasattr(node, 'discharge_frame') and node.discharge_frame == frame:
                flash_ring = plt.Circle((x, y), 0.3,
                            edgecolor='white',
                            facecolor='none',
                            linewidth=2.5,
                            alpha=0.9,
                            zorder=6)
                ax.add_patch(flash_ring)

            # 🔴 Step 2.0.5: Pressure Ring Visual Cue
            if hasattr(node, 'pressure') and node.pressure > 8:
                ring_color = 'orange' if node.pressure < 12 else 'red'
                pressure_radius = 0.15 + 0.01 * node.pressure
                ax.add_patch(plt.Circle((x, y), pressure_radius, color=ring_color,
                            fill=False, linewidth=1.0, alpha=0.4, zorder=2))

            # 🌀 Step 2.1: Coherence Glow for Echo Count ≥ 3
            if node.echo_count >= 6:
                glow_radius = 200 + node.echo_count * 8
                glow_alpha = min(0.15 + 0.03 * node.echo_count, 0.5)
                ax.scatter(x, y, s=glow_radius, facecolors='none', edgecolors='cyan',
               linewidths=2.0, alpha=glow_alpha, zorder=1)

            # 🌟 Step 2.2: Quasar Flare for Deep Coherence
            if getattr(node, 'echo_coherent', False) and node.echo_count >=8:
                flare_size = 200 + node.echo_count * 10
                ax.scatter(x, y, s=flare_size, facecolors='none', edgecolors='cyan', linewidths=2.5, alpha=0.25, zorder=1)

            if node.echo_count >= 10:
                ax.scatter(
                    node.position[0],
                    node.position[1],
                    s=flare_size,
                    facecolors='none',
                    edgecolors='cyan',
                    linewidths=2.5,
                    alpha=0.5,
                    zorder=10  # bump to sit above base visuals
                )

                ax.scatter(
                    x, y,
                    s=flare_size + 20,
                     facecolors='none',
                     edgecolors='cyan',
                     linewidths=1.5,
                     alpha=0.15,
                     zorder=6
                 )

            # 🔵 Echo Marker
            if is_echo_match(node, frame, positions, i):
                capped_echo = min(node.echo_count, 20)  # Limit max size to prevent slowdown
                # Limit max size to prevent slowdown
                capped_echo = min(node.echo_count, 20)
                pulse_speed = getattr(node, 'pulse_velocity', 0.0)

                # Smarter scaling for ring visuals
                ring_size = 50 * (capped_echo ** 0.5)
                ring_alpha = max(0.15, 1.0 - (capped_echo * 0.05)) + (pulse_speed * 0.2)
                ring_alpha = min(ring_alpha, 1.0)  # Clamp max

                ax.scatter(x, y, s=ring_size, facecolors='none',
                edgecolors=(0, 0, 1, ring_alpha), linewidths=2.0, zorder=4)
                # Only show "Echo" label if echo count is present and non-zero
                if getattr(node, 'echo_count', 0) > 0:
                   ax.text(x, y + 0.25, "Echo", fontsize=6, color=(0, 0, 1, ring_alpha), ha='center')

                # Draw Truth and Alignment per node
                truth_text = f"T:{node.truth_feedback:.2f}" if hasattr(node, 'truth_feedback') else "T:?"
                align_text = f"A:{node.alignment_score:.2f}" if hasattr(node, 'alignment_score') else "A:?"
                ax.text(x, y - 0.45, truth_text, fontsize=5, color='cyan', ha='center')
                ax.text(x, y - 0.52, align_text, fontsize=5, color='magenta', ha='center')

            theta = math.atan2(y, x)  # Needed for arc orientation  
  
            # 🌌 Echo Memory Arc Trail (Step 4)
            if node.echo_count > 0:
                fade_strength = max(0.1, 1.0 - node.echo_count * 0.05)
                mem_radius = radius + 0.1
                mem_theta = theta + math.sin(frame * 0.05 + i) * 0.2  # subtle oscillation
                arc_x = [mem_radius * math.cos(mem_theta + t * 0.15 * math.pi) for t in [0, 1]]
                arc_y = [mem_radius * math.sin(mem_theta + t * 0.15 * math.pi) for t in [0, 1]]
                ax.plot(arc_x, arc_y, color='cyan', linewidth=0.6, alpha=fade_strength, zorder=2)

            # Echo Count Label
            if node.echo_count > 0:
              ax.text(x, y - 0.35, f"×{node.echo_count}", fontsize=6, color='blue', ha='center', va='top')

            # Only run this if node is defined
            if node is not None:
                if i % (len(lattice) // 4 or 1) == 0:
                    is_active = getattr(node, 'highlight', False) or getattr(node, 'discharged', False)

                    ax.text(
                        x, y + 0.15, node.element.name,
                        fontsize=9 if is_active else 7,
                        color='cyan' if is_active else 'white',
                        fontweight='bold' if is_active else 'normal',
                        ha='center',
                        va='center',
                        zorder=11 if is_active else 5,
                        rotation=math.degrees(theta) if mode['type'] == 'radial' else 0,
                        rotation_mode='anchor'
                    )

            arc_text = f"S:{getattr(node, 'shell_id', 0)}"
            ax.text(x, y - 0.2, arc_text, fontsize=6, ha='center', va='top', color='cyan')

            if node.highlight or node.discharged or (hasattr(node, 'pressure') and node.pressure > 8):
                if mode['type'] == 'radial':
                    arc_angle = 0.3 * math.pi
                    arc_radius = radius + 0.1
                    arc_theta = theta
                    arc_x = [arc_radius * math.cos(arc_theta + t * arc_angle) for t in [0, 1]]
                    arc_y = [arc_radius * math.sin(arc_theta + t * arc_angle) for t in [0, 1]]
                    ax.plot(arc_x, arc_y, color='magenta', linewidth=2.0, alpha=0.8)
                else:
                    ax.plot([x, x], [y - 0.4, y + 0.4], color='magenta', linewidth=2.0, alpha=0.8)

            # 🔄 Pulse Direction Arc (Step 2)
            if DEBUG_VISUALS:
                pulse_draw_threshold = 0.02
                if mode['type'] == 'radial' and abs(node.pulse_velocity) > pulse_draw_threshold:
                    arc_angle = 0.15 * math.pi
                    arc_radius = radius + 0.05
                    arc_theta = theta + (0.1 if node.pulse_velocity > 0 else -0.1)
                    arc_x = [arc_radius * math.cos(arc_theta + t * arc_angle) for t in [0, 1]]
                    arc_y = [arc_radius * math.sin(arc_theta + t * arc_angle) for t in [0, 1]]
                    velocity = abs(node.pulse_velocity)
                    arc_opacity = min(0.05 + velocity * 2.5, 0.7)  # Range: 0.1 to 1.0
                    ax.plot(arc_x, arc_y, color='blue', linewidth=1.2, alpha=arc_opacity)

            # 🌟 Step 4: Core Pulse Bloom (Hydrogen Pulse Signature)
            if node.element.name == "Hydrogen" and mode['type'] == 'radial':
                pulse_strength = abs(getattr(node, 'pulse_velocity', 0))
                bloom_radius = 0.2 + (pulse_strength * 0.5)
                bloom_alpha = min(0.1 + 0.03 * node.echo_count, 0.6)
                bloom_ring = plt.Circle((x, y), bloom_radius, color='gold', alpha=bloom_alpha, fill=False, linewidth=2.5, zorder=1)
                ax.add_patch(bloom_ring)

            # Gradually increase smoothing if system stable
            if len(active_nodes) == 0:
                truth_smoother['alpha'] = min(truth_smoother['alpha'] + 0.01, 0.2)
            else:
                truth_smoother['alpha'] = max(truth_smoother['alpha'] - 0.005, 0.05)

            # --- Global entropy tracking for current frame ---
            global_entropy = (sum(getattr(n, 'entropy_score', 0.0) for n in lattice)
                              / max(1, len(lattice)))
            print(f"Frame {frame}: Global Entropy = {global_entropy:.4f}")

        detect_echo_coherence(lattice, frame, positions)

        # --- Top-Left Unified HUD Overlay with Coupling Index Fail-Safe ---

        # --- Pulse Tracking ---
        if 'pulse_history' in locals() and len(pulse_history) >= 1:
            current_pulse = pulse_history[-1]  # Latest value
            if len(pulse_history) >= 2:
                if pulse_history[-1] > pulse_history[-2]:
                    stability_dir = ("↑", 'lime')      # Rising
                elif pulse_history[-1] < pulse_history[-2]:
                    stability_dir = ("↓", 'red')       # Falling
                else:
                    stability_dir = ("=", 'yellow')   # Steady
            else:
                stability_dir = ("?", 'white')        # No comparison yet
        else:
            current_pulse = 0.0
            stability_dir = ("?", 'white')            # No data yet

        # --- Coupling Index Tracking (Fail-Safe) ---
        ci_value = coupling_index if 'coupling_index' in locals() else 0.0

        if 'coupling_history' not in locals():
            coupling_history = []
        coupling_history.append(ci_value)

        if len(coupling_history) >= 2:
            if coupling_history[-1] > coupling_history[-2]:
                coupling_dir = ("↑", 'red')        # Instability growing
            elif coupling_history[-1] < coupling_history[-2]:
                coupling_dir = ("↓", 'lime')       # Stability improving
            else:
                coupling_dir = ("=", 'yellow')     # No change
        else:
            coupling_dir = ("?", 'white')          # First frame

        # --- Status Lines ---
        status_lines = [
            f"Frame: {frame}",
            f"Mode: {pretty_mode}",
            f"Active Nodes: {len(active_nodes)}",
            f"Shells: {unique_shells}",
            f"Truth: {truth_alignment:.3f} AD Align, {been_alignment:.3f} BEEN",
            f"Truth Feedback: {truth_feedback:.4f}",
            f"Alignment: {alignment_metric_global:.4f}",
            f"Global Entropy: {global_entropy:.3f}",
            f"Clusters: {num_clusters} (max: {max_cluster_size})",
            f"Pulse: {current_pulse:.3f} {stability_dir[0]}",
            f"Coupling Index: {ci_value:.3f} {coupling_dir[0]}"
        ]

        # --- Draw Status Lines ---
        for i, line in enumerate(status_lines):
            color = (
                stability_dir[1] if "Pulse:" in line
                else coupling_dir[1] if "Coupling Index:" in line
                else 'white'
            )
            ax.text(
                0.02, 0.92 - i * 0.04, line,
                transform=ax.transAxes,
                fontsize=8,
                color=color,
                verticalalignment='top',
                bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1)
            )


        # 🌀 Echo Pulse Memory Trails + Frequency Labels
        for i, node in enumerate(lattice):
            if not hasattr(node, 'echo_trail'):
                node.echo_trail = []

            # Store recent (x, y) for trail — capped memory
            node.echo_trail.append(positions[i])
            if len(node.echo_trail) > 12:
              node.echo_trail.pop(0)

            # Draw trail if coherence is active
            if getattr(node, 'echo_coherent', False):
               xs, ys = zip(*node.echo_trail)
               ax.plot(xs, ys, linestyle='dotted', linewidth=1.0, color='blue', alpha=0.3)

               # Optional: resonance frequency label
               freq_label = f"ƒ={node.echo_count}"
               ax.text(xs[-1], ys[-1] + 0.15, freq_label, fontsize=6, color='navy',
                       ha='center', va='bottom', alpha=0.5)

        # 🔷 Echo Trail Lines (after all positions and coherence checks)
        for node in lattice:
            if hasattr(node.element, 'echo_trail') and len(node.element.echo_trail) > 1:
                trail_points = [(positions[i]) for (f, i) in node.element.echo_trail if isinstance(i, int) and i < len(positions)]
                if len(trail_points) >= 2:
                   xs, ys = zip(*trail_points)
                   ax.plot(xs, ys, linestyle='dashed', linewidth=1.0, color='blue', alpha=0.3)

                # Limit trail history to prevent slowdowns
                max_trail_points = 50
                trail_points = trail_points[-max_trail_points:]
     
        # Dynamic Echo Trail Cap
        if hasattr(node.element, 'echo_trail'):
            max_echoes = max(4, int(frame / 10))  # Gradually allows more echoes over time
            node.element.echo_trail = node.element.echo_trail[-max_echoes:]

        # Recursive Learning Arcs 🔁
        for node in lattice:
            if not node.discharged or node.cycle_id is None:
                continue
            for bridge in node.bridges:
                if bridge.cycle_id == node.cycle_id and bridge.discharged:
                    i1 = lattice.index(node)
                    i2 = lattice.index(bridge)
                    x1, y1 = positions[i1]
                    x2, y2 = positions[i2]
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    adjusted_truth = 0.0  # Safe default
                    local_truth = min(getattr(node, 'truth_metric', 0), getattr(bridge, 'truth_metric', 0))
                    truth_smoother['value'] += 0.1 * (local_truth - truth_smoother['value'])
                    truth_metric = min(getattr(node, 'truth_metric', 0), getattr(bridge, 'truth_metric', 0))
                    adjusted_truth = truth_metric * (1 + 0.2 * truth_smoother['value'])
                    ripple_strength = 0.1 + 0.4 * abs(math.sin(5 * truth_smoother['value'] * math.pi)) * (1 + random.uniform(-0.05, 0.05) * phi)
                    adjusted_truth *= ripple_strength  # Now adjusted_truth exists before we modify it
                    soft_alpha = 0.3 + 0.7 * adjusted_truth
                    soft_width = 0.5 + 1.5 * adjusted_truth
                    ax.plot([x1, mid_x, x2], [y1, mid_y, y2], color=node.cluster_color, linewidth=soft_width, alpha=soft_alpha, linestyle='--')

        # === Feedback Loop Arcs (Truth-Alignment Coupling) ===
        for node in lattice:
            if not getattr(node, 'feedback_enabled', False):
                continue

            for bridge in node.bridges:
                if not getattr(bridge, 'feedback_enabled', False):
                    continue

                i1 = lattice.index(node)
                i2 = lattice.index(bridge)
                x1, y1 = positions[i1]
                x2, y2 = positions[i2]

                truth = getattr(node, 'truth_metric', 0)
                align = getattr(node, 'alignment_score', 0)
                feedback_strength = 0.5 * (truth + align)

                if feedback_strength > 0.5:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    ax.plot(
                        [x1, mid_x, x2], 
                        [y1, mid_y + 0.25, y2],
                        color='deeppink',
                        alpha=0.6,
                        linewidth=1 + 1.5 * feedback_strength,
                        linestyle=':',
                        zorder=0
                    )

        # Ripple effect modulates with smoother value
        ripple_strength = 0.1 + 0.4 * abs(math.sin(5 * truth_smoother['value'] * math.pi))
                   
        # 🔷 Echo Coherence Arcs
        for i, node in enumerate(lattice):
            if not getattr(node, 'echo_coherent', False):
             continue
            for bridge in node.bridges:
                 if getattr(bridge, 'echo_coherent', False):
                    x1, y1 = positions[i]
                    x2, y2 = positions[lattice.index(bridge)]
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    ax.plot([x1, mid_x, x2], [y1, mid_y + 0.2, y2],
                             color='blue', linewidth=1.8, alpha=0.4, linestyle='dotted')


        # 🔗 Step 5: Pulse Chain Tension Arcs (Bridge Reactivity Curves)
        for i, node in enumerate(lattice):
            x1, y1 = positions[i]
            for bridge in node.bridges:
                if bridge in lattice:
                    j = lattice.index(bridge)
                    x2, y2 = positions[j]

                    pulse_delta = abs(getattr(node, 'pulse_velocity', 0) - getattr(bridge, 'pulse_velocity', 0))
                    tension = min(pulse_delta, 1.0)

                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2 + (0.2 * tension)  # Curve height

                    ax.plot([x1, mid_x, x2], [y1, mid_y, y2], color=node.cluster_color, linewidth=1.2 + tension * 1.5, alpha=0.4, linestyle='-')

        # 💫 Step E: Echo Charge Streamlines (Flow Feedback Loops)
        for i, node in enumerate(lattice):
            if not getattr(node, 'echo_coherent', False):
                continue
            for bridge in node.bridges:
                if not getattr(bridge, 'echo_coherent', False):
                    continue

                j = lattice.index(bridge)
                x1, y1 = positions[i]
                x2, y2 = positions[j]

                # Vector midpoint and soft curvature
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2 + 0.1  # lift for curvature

                ax.plot([x1, mid_x, x2], [y1, mid_y, y2],
                        color='magenta',
                        linewidth=0.5,
                        alpha=0.15,
                        linestyle='solid')

        
        # === Step 13.5: Pythagorean Triplet Detection ===
        epsilon = 0.05
        for node in lattice:
             connected = node.bridges
             if len(connected) >= 2:
                for i in range(len(connected)):
                    for j in range(i + 1, len(connected)):
                        A = positions[lattice.index(node)]
                        B = positions[lattice.index(connected[i])]
                        C = positions[lattice.index(connected[j])]

                        a = math.dist(B, C)
                        b = math.dist(A, C)
                        c = math.dist(A, B)

                        # Check if right triangle: a² ≈ b² + c²
                        if abs(a**2 - (b**2 + c**2)) < epsilon:
                            ax.plot([B[0], C[0]], [B[1], C[1]], color='cyan', linestyle='-.', linewidth=1.2, alpha=0.6)

        # Check if right triangle: a² ≈ b² + c²
        if abs(a**2 - (b**2 + c**2)) < epsilon:
            ax.plot([B[0], C[0]], [B[1], C[1]], color='cyan', linestyle='-.', linewidth=1.2, alpha=0.6)

            # Midpoint for hypotenuse label
            mx = (B[0] + C[0]) / 2
            my = (B[1] + C[1]) / 2

            # Color code by size of gap
            color = 'lime' if c < 1 else 'orange' if c < 2 else 'red'
            ax.text(mx, my + 0.05, f"{c:.2f}", fontsize=7, color=color, ha='center', fontweight='bold')

        # Discharged intelligent arcs (triadic + coherent)
        if node.discharged and getattr(node, 'cycle_id', None) is not None and truth_metric > 0.9:
          if mode['type'] == 'radial':
              arc_angle = 0.25 * math.pi
              arc_radius = radius + 0.15
              arc_theta = angles[i]
              arc_x = [arc_radius * math.cos(arc_theta + t * arc_angle) for t in [0, 1]]
              arc_y = [arc_radius * math.sin(arc_theta + t * arc_angle) for t in [0, 1]]
              ax.plot(arc_x, arc_y, color='cyan', linewidth=2.0, linestyle='--', alpha=0.6)
        else:
              ax.plot([x - 0.4, x + 0.4], [y, y], color='cyan', linewidth=2.0, linestyle='--', alpha=0.6)

        # View logic
        if view_reset['trigger']:
         xs, ys = zip(*positions) if positions else ([0], [0])
         view_reset['trigger'] = False  # Reset the flag
        elif focus_mode['enabled'] and active_nodes:
         xs, ys = zip(*active_nodes)
        else:
         xs, ys = zip(*positions) if positions else ([0], [0])

        ax.set_xlim(min(xs) - 1, max(xs) + 1)
        ax.set_ylim(min(ys) - 1, max(ys) + 1)

        ax.set_title(f"🐉 AlphaDragon Charge Network 🧠 {mode['type'].capitalize()} Mode")
        ax.set_xlabel("Element Index" if mode['type'] == 'linear' else "X")
        ax.set_ylabel("Pulse Amplitude" if mode['type'] == 'linear' else "Y")
        ax.grid(True)

        legend_patches = [
            Line2D([0], [0], marker='o', color='w', label='Discharged', markerfacecolor='white', markersize=10, markeredgecolor='black'),
            Line2D([0], [0], marker='o', color='w', label='Tunneling', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Pressure > 12', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Pressure > 8', markerfacecolor='orange', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Normal/Shell Gradient', markerfacecolor=cmap(0.5), markersize=10)
        ]
        ax.legend(handles=legend_patches, loc='upper right', fontsize='small')
        # Compute truth feedback and alignment
        alpha_truth_feedback = compute_alpha_dragon_truth(lattice, frame)
        truth_field = np.array([1.0, 0.0])  # Example: horizontal unit vector
        alpha_truth_alignment = compute_alpha_truth_alignment(lattice, truth_field)
        # --- Record shell memory for each node ---
        for node in lattice:
            if hasattr(node, 'charge_vector'):
                magnitude = np.linalg.norm(node.charge_vector)

    if len(cluster_center_trace) > 1:
        _, xs, ys = zip(*cluster_center_trace)
        # Fading alpha for the trace (optional)
        for i in range(1, len(xs)):
            alpha = 0.10 + 0.45 * (i / len(xs))  # Newer segments are brighter
            ax.plot(xs[i-1:i+1], ys[i-1:i+1], color='gold', linewidth=3, alpha=alpha, zorder=3)
            

    # Key handling
    def toggle_mode(event):
        if event.key == 't':
            mode['type'] = 'radial' if mode['type'] == 'linear' else 'linear'
            print(f"\nSwitched Mode to: {mode['type'].capitalize()}")
        elif event.key == 'f':
            focus_mode['enabled'] = not focus_mode['enabled']
            print(f"\nFocus Mode {'Enabled' if focus_mode['enabled'] else 'Disabled'}")
        elif event.key == 'r':
           focus_mode['enabled'] = False
           print("🔄 Reset to shell-bounded layout")
        elif event.key == 't':
           truth_feedback_toggle['enabled'] = not truth_feedback_toggle['enabled']
           print(f"Truth Feedback {'Enabled' if truth_feedback_toggle['enabled'] else 'Disabled'}")
           print(f"🧠 Truth Feedback {'Enabled' if truth_feedback_toggle['enabled'] else 'Disabled'}")

    fig.canvas.mpl_connect('key_press_event', toggle_mode)
    fig.canvas.mpl_connect('key_press_event', toggle_pulse_overlay)
    # Build cycles before animation setup
    assign_cycle_ids(lattice)

    # ⏱️ Smart interval calculation based on node + echo load
    load_factor = len(lattice) + sum(node.echo_count for node in lattice)
    interval_ms = min(200, max(30, int(load_factor / 1.1)))  # Adjustable throttle

    print(f"⚙️ Using interval: {interval_ms}ms for animation")

    # Initialize animation
    ani = animation.FuncAnimation(
    fig, update, frames=200, interval=interval_ms, blit=False
    )

    plt.show()
    plt.close(fig)

def plot_truth_comparison():
    plt.figure(figsize=(10, 5))
    plt.plot(truth_history["alpha_dragon"], label="Alpha Dragon", color="cyan")
    plt.plot(truth_history["been"], label="Classical BEEN", color="magenta")
    plt.xlabel("Frame")
    plt.ylabel("Alignment Score")
    plt.title("Truth Alignment Over Time")
    plt.legend()
    plt.grid(True)

def get_truth_value(velocity):
    """Returns a normalized 'truth' value based on velocity magnitude."""
    return min(1.0, abs(velocity))

def apply_entropy_gradient_balance(lattice, gradient_factor=0.02):
    """
    Balances entropy across the lattice by nudging nodes towards system-average entropy.
    Prevents asymmetric drift from dominant clusters, with stabilizer for smoother response.
    """
    entropies = [getattr(node, 'entropy', 0) for node in lattice if hasattr(node, 'entropy')]
    if not entropies:
        return  # Skip if no entropy present

    avg_entropy = sum(entropies) / len(entropies)

    for node in lattice:
        if hasattr(node, 'entropy'):
            # Gentle bias toward average entropy, tuned by Truth
            neighbor_entropies = [getattr(n, 'entropy', 0) for n in getattr(node, 'bridges', []) if hasattr(n, 'entropy')]
            if neighbor_entropies:
                local_avg_entropy = sum(neighbor_entropies) / len(neighbor_entropies)
                entropy_diff = local_avg_entropy - node.entropy
            else:
                entropy_diff = 0

            neighbor_count = len(neighbor_entropies) if neighbor_entropies else 0
            stabilizer = 1 / (1 + abs(entropy_diff)) * (1 + 0.1 * neighbor_count) * (1 + 0.05 * truth_metric)

            adaptive_factor = 0.02 + (0.08 * (1 - truth_metric))  # Ranges 0.02 - 0.10 based on Truth

            node.entropy += entropy_diff * adaptive_factor * stabilizer

            # Optional clamp to prevent extreme entropy runaway
            node.entropy = max(min(node.entropy, 20), -20)
            # Absolute hard clamp to catch extreme cases
            node.entropy = max(min(node.entropy, 50), -50)

def recursive_charge_dampening(lattice, base_dampening=0.02):
    """
    Applies recursive dampening to prevent runaway charge buildup,
    with scaling based on system Truth metric for adaptive stability.
    Enhanced to detect local entropy instability and amplify dampening accordingly.
    """
    global truth_metric  # Ensures live Truth metric influences dampening

    for node in lattice:
        if hasattr(node, 'charge_level'):
            # Dampening strength adjusts with Truth (stronger at low Truth)
            node.adaptive_dampening = base_dampening * (1.2 - min(1, truth_metric / 10))

            if node.phase_state == 'chaotic':
                # Extra suppression during chaos phases
                adaptive_dampening *= 1.5

            # NEW: Local Entropy Variance Check
            if hasattr(node, 'entropy_history'):
                recent_entropy = node.entropy_history[-5:] if len(node.entropy_history) >= 5 else node.entropy_history
                entropy_variance = max(recent_entropy) - min(recent_entropy)

                if entropy_variance > 0.5:  # Adjustable threshold
                    adaptive_dampening *= 1.25  # Amplify dampening in unstable pockets

            # Apply dampening to charge level
            node.charge_level *= node.adaptive_dampening * compute_intelligence_weight(node)

def compute_intelligence_weight(node):
    # Modify this logic as you like—this is a good starting baseline
    if node.state == "active":
        return 0.85  # Allow a bit more energy to flow
    elif node.state == "idle":
        return 1.0   # Neutral weight
    elif node.state == "pulsing":
        return 1.1   # Dampens slightly more aggressively to avoid buildup
    return 1.0

def compute_pressure_weight(node):
    """
    Dynamically adjusts how much pressure a node can tolerate or push,
    based on its current state or shell position.
    """
    # Example logic — feel free to modify:
    if hasattr(node, 'state'):
        if node.state == "active":
            return 1.15  # Slightly more tolerant under load
        elif node.state == "idle":
            return 0.95  # Slightly more conservative
        elif node.state == "pulsing":
            return 1.25  # Pushes more aggressively
    # Optionally: Shell-based pressure tuning
    if hasattr(node, 'shell_index'):
        return 1.0 + (0.01 * node.shell_index)  # Outer shells tolerate more pressure

    return 1.0

def equilibrate_mass(lattice, smoothing=0.2, iterations=2):
    for _ in range(iterations):
        for node in lattice:
            neighbors = getattr(node, 'bridges', [])
            if not neighbors:
                continue
            avg_mass = sum(getattr(n, 'mass', 1.0) for n in neighbors) / len(neighbors)
            new_mass_val = (1 - smoothing) * node.mass + smoothing * avg_mass
            node.mass = new_mass_val * compute_mass_weight(node)

def compute_mass_weight(node):
    if hasattr(node, 'mass') and node.mass is not None:
        return 1.0 + 0.1 * node.mass
    return 1.0

def simulate_pressure_dip(lattice, damping_factor=0.05):
    """
    Applies a pressure dip to the center node (index 0) based on pulse interference,
    scaled by shell gradient to stabilize outer influence.
    """
    center_node = lattice[0]  # Assuming 'H' or central mass
    interference_sum = 0

    for neighbor in center_node.bridges:
        try:
            delta = abs(neighbor.update_pulse() - center_node.update_pulse())
            
            # Shell gradient dampens influence of unstable outer nodes
            shell_diff = abs(neighbor.shell_level - center_node.shell_level)
            gradient_damping = 1 / (1 + 0.5 * shell_diff)

            scaled_delta = delta * gradient_damping
            interference_sum -= scaled_delta

        except AttributeError:
            continue

    center_node.pressure_level += damping_factor * interference_sum

    # More stable damping calculation
    center_node.pressure_level += damping_factor * interference_sum

def calculate_truth_metric(lattice):
    """
    Calculates a universal truth metric based on coherence, shell depth consistency,
    and pressure turbulence. Represents recursive harmony across the system.
    """
    total_nodes = len(lattice)
    if total_nodes == 0:
        return 0.0

    pressure_variance = 0.0
    shell_depth_error = 0.0
    bridge_variance = 0.0

    avg_shells = sum(len(n.element.shell_structure) for n in lattice) / total_nodes
    avg_bridges = sum(len(n.bridges) for n in lattice) / total_nodes
    avg_pressure = sum(n.pressure_level for n in lattice) / total_nodes

    for node in lattice:
        # Shell consistency penalty
        shell_depth_error += abs(len(node.element.shell_structure) - avg_shells)

        # Pressure turbulence penalty
        pressure_variance += (node.pressure_level - avg_pressure) ** 2

        # Bridge coherence penalty
        bridge_variance += (len(node.bridges) - avg_bridges) ** 2

    # Normalize and invert: higher stability = higher truth
    stability_score = (
        1.0 /
        (1.0 + 0.1 * shell_depth_error + 0.05 * bridge_variance + 0.05 * pressure_variance)
    )

    return round(stability_score * 10.0, 3)

def detect_discharge_clusters(lattice, threshold=3):
    clusters = []
    visited = set()

    for node in lattice:
        if node.discharged and node not in visited:
            stack = [node]
            cluster = []

            while stack:
                current = stack.pop()
                if current in visited or not current.discharged:
                    continue
                visited.add(current)
                cluster.append(current)
                stack.extend([n for n in current.bridges if n.discharged and n not in visited])

            if len(cluster) >= threshold:
                clusters.append(cluster)

    return clusters

def build_and_prepare_lattice():
    """
    Build the default 118-element Alpha Dragon lattice and run the
    core preparation passes needed before animation.
    """
    lattice = generate_sample_lattice()
    form_charge_bridges(lattice)
    update_shell_recursion(lattice)
    trigger_mass_shell_discharge(lattice, frame=0)
    detect_resonant_clusters(lattice)
    tag_cluster_intelligence(lattice)
    compute_pressure(lattice)
    return lattice


def main():
    """
    Public entry point for the research build.

    Returns the prepared lattice so the model can also be imported and reused
    from notebooks or other Python scripts without auto-running on import.
    """
    lattice = build_and_prepare_lattice()
    animate_dual_mode(lattice)
    return lattice


if __name__ == "__main__":
    main()
