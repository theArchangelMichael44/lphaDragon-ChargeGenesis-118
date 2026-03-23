# lphaDragon-ChargeGenesis-118
118-element shell-network research build for pressure, discharge, resonance, and emergent clustering in Linear and Radial modes.
# AlphaDragon Charge Genesis — 118-Element Shell Network

AlphaDragon Charge Genesis is a research simulation that treats the periodic table as a structured 118-node shell network.

This is not a chemistry engine and it is not a conventional physics solver.

It is an experimental model for studying how deterministic local rules can generate larger organized behavior through:

- accumulation
- pressure
- discharge
- resonance
- memory
- clustering

## Why the periodic table?

The periodic table is used here because it is one of the clearest real-world examples of a shell-based hierarchy of matter.

This project does **not** use the periodic table as a chemistry textbook reference.

It uses it as a structured system of:

- discrete shell levels
- recurring periodic behavior
- stable and unstable configurations
- a full spectrum of material states across 118 elements

In other words, the periodic table provides a real, experimentally grounded shell architecture for testing network behavior.

## What this build does

Each element is treated as a node with:

- shell structure
- pulse behavior
- pressure state
- bridge relationships to other nodes
- participation in cluster and resonance dynamics

The build renders the same evolving system in two views:

### Linear Mode
Shows indexed pulse behavior across the 118-node network.

### Radial Mode
Shows shell relationships, bridge structure, pressure states, and emergent clustering in a spatial network view.

## Current scope

This build focuses on the dynamic layer of the system:

- shell pressure
- discharge propagation
- bridge formation
- resonance patterns
- cluster emergence
- truth / alignment overlays

Earlier Alpha Dragon experiments also explored interaction and synthesis behavior. This build should be understood as a foundational emergence layer rather than a full synthesis engine.

## Controls

Keyboard controls:

- `t` — toggle between Linear and Radial mode
- `f` — toggle focus mode
- `r` — reset layout behavior
- `u` — show/hide status HUD

Standard Matplotlib zoom/pan controls are also available in the figure window.

## Requirements

- Python 3.10+
- numpy
- matplotlib

Install dependencies:

```bash
pip install -r requirements.txt
