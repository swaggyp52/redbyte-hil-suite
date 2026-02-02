# Presentation Walkthrough Script

**Goal**: Demonstrate the "Simulator-Grade" capabilities of the HIL Verifier Suite.

## Scene 1: The "HIL" Setup (Standard Mode)

1. Launch `bin/start.bat`.
2. Show **Inverter Scope** and **Fault Injector**.
3. Explain: "This is the engineer's view. We control the inverter and monitor signals."

## Scene 2: Visualizing Phase Dynamics (PhasorView)

1. Open **Phasor Diagram** window.
2. Inject `Voltage Sag` fault.
3. **Observation**: "Notice the vector length shrink in real-time."
4. Adjust **Range Slider** to zoom in.

## Scene 3: The System Context (3D View)

1. Open **3D System** window.
2. Explain: "This digital twin represents our physical lab setup."
3. Inject `Grid Loss` fault.
4. **Observation**: "The Inverter block turns RED immediately, indicating protection trip."

## Scene 4: The "Client" View (Presentation Mode)

1. Click **Presentation Mode** in toolbar.
2. **Effect**: Dev tools vanish. Visuals expand to fill screen.
3. "This is what we show stakeholders/clients. Pure system visibility."

## Scene 5: Post-Mortem (Replay Studio)

1. Click **Presentation Mode** again to exit.
2. Load a previous session in **Replay Studio**.
3. Scrub the timeline. "We can review the exact millisecond of failure."
