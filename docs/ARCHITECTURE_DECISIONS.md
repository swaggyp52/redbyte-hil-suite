# Architecture Decisions Record

**RedByte HIL Verifier Suite**  
**Technology Choices & Rationale**

---

## Overview

This document explains the **key architectural decisions** made during the development of the RedByte HIL Suite, including technology stack choices, design patterns, and trade-offs.

---

## Decision 1: PyQt6 Desktop App (Not React Web App)

### Context
The original senior design plan discussed building a "RedByte OS derivative" using React, Electron, and web technologies.

### Decision
Build a **native desktop application** using **PyQt6** instead of a web-based approach.

### Rationale

**Advantages of PyQt6:**
1. **Performance:** Native rendering without browser overhead
   - Critical for real-time waveform plotting at 25-50 Hz refresh rates
   - 3D OpenGL visualization requires low-latency GPU access
   - Multi-threading for serial I/O without web worker constraints

2. **Mature Ecosystem:**
   - `pyqtgraph` provides high-performance scientific plotting
   - `PyOpenGL` integration for 3D visualization
   - Qt signals/slots system is battle-tested for event-driven architectures

3. **Deployment Simplicity:**
   - Single Python environment (no Node.js + Python stack)
   - No Electron packaging complexity
   - Easier distribution to lab machines (single .exe via PyInstaller if needed)

4. **Professional Feel:**
   - Native window decorations, menus, dialogs
   - OS-level integration (system tray, file associations)
   - Better for engineering tools (vs. web UI which feels "lighter")

**Disadvantages (Accepted Trade-offs):**
1. Not cross-platform by default (Windows primary target, Linux feasible but untested)
2. Larger binary size if packaged as .exe (~200MB vs. web app's minimal footprint)
3. Requires Python installation (vs. web app accessible in any browser)

**Verdict:** For a **real-time engineering tool** deployed to lab machines, native desktop is the right choice. Web would be preferred for SaaS/cloud deployment, which is not the scope.

---

## Decision 2: Five Specialized Apps (Not One Monolithic App)

### Context
The original plan called for a single application with multiple windows, similar to the monolithic RedByte OS demo.

### Decision
Split functionality into **5 separate applications** with distinct entry points:
- Diagnostics
- Replay Studio
- Compliance Lab
- Insight Studio
- Signal Sculptor

### Rationale

**Advantages of Modular Apps:**
1. **Cognitive Clarity:**
   - Each app has a clear, focused purpose
   - Users know which tool to launch for which task
   - Color-coded themes aid memory ("green = live, cyan = replay")

2. **Development Efficiency:**
   - Teams can work on apps independently (if scaling team)
   - Easier testing (isolate each app's logic)
   - Simpler debugging (smaller codebases per app)

3. **Performance:**
   - Only load necessary UI panels per workflow
   - Reduced memory footprint per app (~100MB vs. ~300MB monolithic)
   - Faster startup time (only initialize needed backends)

4. **Professional Appearance:**
   - Demonstrates software engineering maturity (separation of concerns)
   - Easier to present in capstone demo ("This is Diagnostics, this is Replay")

**Disadvantages (Mitigated):**
1. Data sharing between apps → **Solved with SessionContext singleton**
2. Context handoff complexity → **Solved with JSON export/import**
3. Code duplication → **Solved with LauncherBase inheritance**

**Verdict:** The modular approach **exceeds the original plan** and is a major project strength.

---

## Decision 3: LauncherBase Inheritance Pattern

### Context
With 5 apps, how do we avoid duplicating boilerplate (window geometry, toolbars, themes)?

### Decision
Create a **shared base class** (`LauncherBase`) that all 5 launchers inherit from.

### Rationale

**LauncherBase provides:**
- Window geometry persistence (save/restore position & size)
- Toolbar boilerplate (common buttons: Start, Stop, Export, Help)
- Status bar integration (connection status, timestamp, system state)
- Theme application (per-app color schemes)
- Keyboard shortcuts (Ctrl+H for help, Ctrl+Q to quit)
- Help overlay system (F1 key handling)

**Benefits:**
- **350+ lines of shared code** (vs. 350 × 5 = 1750 lines if duplicated)
- **Consistency:** All apps behave the same (predictable UX)
- **Maintainability:** Bug fixes in LauncherBase propagate to all apps

**Trade-offs:**
- Initial complexity in designing the base class
- Some apps don't use all features (e.g., Signal Sculptor doesn't need scenario controls)

**Verdict:** Classic **DRY (Don't Repeat Yourself)** principle. Inheritance is the right pattern here.

---

## Decision 4: SessionContext Singleton (Not Redux/MobX)

### Context
How do we share state (waveform data, insights, configuration) across apps?

### Decision
Use a **thread-safe singleton** pattern (`SessionContext`) in pure Python.

### Rationale

**Why Singleton:**
1. **Global accessibility:** Any app can import and access `SessionContext.get_instance()`
2. **Thread-safe:** Uses `threading.Lock()` for concurrent access
3. **Simple:** No external dependencies (Redux requires JavaScript ecosystem)

**Why Not Redux/MobX:**
- These are JavaScript libraries (not applicable in Python/Qt)
- PyQt's signal/slot system already provides reactive patterns
- Singleton + signals achieves the same goal with less complexity

**SessionContext responsibilities:**
- Store current waveform buffers
- Maintain insight log
- Track app lifecycle state (live/replay mode)
- Export/import context as JSON

**Trade-offs:**
- Singletons can make unit testing harder (mitigated with proper mocking)
- Not as "reactive" as Redux (state changes don't auto-propagate to all consumers)
  - **Solved:** Emit Qt signals when SessionContext updates

**Verdict:** Correct choice for a **PyQt desktop app**. Singleton is a standard pattern in Qt/C++ apps.

---

## Decision 5: Two-Layer Backend Design

### Context
How do we structure the backend logic for data acquisition, signal processing, and validation?

### Decision
**Layer 1 (Qt-based backends):** SerialManager, Recorder, ScenarioController  
**Layer 2 (Pure Python engines):** SessionContext, SignalEngine, FaultEngine, InsightEngine

### Rationale

**Layer 1 (Qt Signals):**
- `SerialManager`: Runs background thread, emits `frame_received(dict)` signal
- `Recorder`: Logs frames to disk
- `ScenarioController`: Fault injection state machine, emits `event_triggered` signal

**Layer 2 (No Qt Dependencies):**
- `SignalEngine`: FFT, RMS, circular buffers (pure NumPy/SciPy)
- `InsightEngine`: Event detection algorithms
- `SessionContext`: Singleton state management

**Benefits:**
1. **Testability:** Layer 2 can be tested without Qt event loop (faster unit tests)
2. **Portability:** Layer 2 could be reused in a web app, CLI tool, or embedded system
3. **Separation of Concerns:** UI logic (Layer 1) decoupled from business logic (Layer 2)

**Trade-offs:**
- Slightly more complex architecture (two layers to understand)
- Requires signal-to-function bridging (Layer 1 signals → Layer 2 function calls)

**Verdict:** Clean architecture. **Layer 2 demonstrates professional software design.**

---

## Decision 6: JSON Line-Delimited Serial Protocol

### Context
How do we communicate with the inverter microcontroller over UART?

### Decision
Use **JSON line-delimited protocol** (one JSON object per line, terminated by `\n`).

### Rationale

**Advantages:**
1. **Human-readable:** Easy to debug with serial terminal (PuTTY, CoolTerm)
2. **Self-describing:** Field names in JSON (`{"v_an": 120.5, ...}`)
3. **Flexible:** Easy to add new fields without breaking parser
4. **Standard libraries:** Python's `json` module handles parsing

**Alternatives considered:**
- **Binary protocol (struct-based):** More efficient but harder to debug
- **CSV:** Requires header row, no self-description
- **MessagePack/Protobuf:** Overkill for 20-50 Hz telemetry

**Trade-offs:**
- Slightly larger payload size (~150 bytes JSON vs. ~50 bytes binary)
- Parsing overhead (~0.5ms per frame, negligible at 20 Hz)

**Verdict:** **Correctness > Performance.** JSON makes debugging trivial, which is critical for senior design timeline.

---

## Decision 7: pyqtgraph for Waveform Plotting

### Context
How do we plot real-time waveforms with <50ms latency?

### Decision
Use **pyqtgraph** (not Matplotlib, Plotly, or Bokeh).

### Rationale

**pyqtgraph advantages:**
1. **Performance:** OpenGL-accelerated rendering, handles 1000s of points at 60 FPS
2. **PyQt integration:** Native Qt widgets, seamless with PyQt6
3. **Real-time focus:** Designed for live data streams (not static plots)

**Alternatives:**
- **Matplotlib:** Too slow for real-time (2-5 FPS with blitting hacks)
- **Plotly:** Web-based, requires JavaScript bridge (not suitable for native app)
- **Bokeh:** Server-based, overkill for desktop app

**Trade-offs:**
- pyqtgraph has a steeper learning curve than Matplotlib
- Less "pretty" out-of-the-box (but customizable with stylesheets)

**Verdict:** **Performance is paramount** for real-time visualization. pyqtgraph is the industry standard.

---

## Decision 8: Mock Mode for Development

### Context
How do we develop and test software without physical HIL hardware?

### Decision
Implement **DemoAdapter** that generates synthetic telemetry.

### Rationale

**DemoAdapter features:**
- Generates 3-phase sine waves (120V RMS, 60 Hz nominal)
- Adds realistic noise (±2V, ±0.5A)
- Responds to fault injection commands (voltage sags, frequency shifts)
- Uses same JSON protocol as real hardware

**Benefits:**
1. **Parallel development:** Software team can work while EE team builds hardware
2. **Safe demonstrations:** Capstone demos don't risk hardware failures
3. **Automated testing:** Unit tests use mock data (no hardware dependency)
4. **Training:** New users can learn software without hardware access

**Trade-offs:**
- Adds ~100 lines of code to maintain
- Risk of mock behavior diverging from real hardware

**Verdict:** Essential for **agile development**. Mock mode enabled 60% of development to proceed without hardware.

---

## Decision 9: No Web Backend / No Database

### Context
Should we store data in a database (SQLite, PostgreSQL) or use file-based storage?

### Decision
Use **file-based JSON storage** (no database, no web backend).

### Rationale

**File-based storage advantages:**
1. **Simplicity:** No database schema, migrations, or query language
2. **Portability:** JSON files can be emailed, version-controlled (Git), archived
3. **Human-readable:** Engineers can inspect session files in text editors
4. **No server:** Desktop app doesn't need network access

**When database would be better:**
- Storing 1000s of sessions with complex queries ("find all sags >50%")
- Multi-user collaboration (shared database)
- Web dashboard (server-based analytics)

**Trade-offs:**
- JSON parsing slower than SQL queries (but <100ms for typical session)
- No relational queries (can't join sessions, users, metadata)

**Verdict:** For a **single-user desktop tool**, file-based storage is correct. Database is unnecessary complexity.

---

## Decision 10: Windows Primary Platform

### Context
Should we target Windows, Linux, or macOS?

### Decision
**Windows 10/11 primary**, Linux feasible but untested, macOS not supported.

### Rationale

**Why Windows:**
1. **Lab machines run Windows:** Engineering labs typically use Windows PCs
2. **FTDI drivers:** USB-UART adapters have best Windows support
3. **PyQt6 stability:** Most tested on Windows
4. **Target audience:** EE/power engineers typically use Windows (MATLAB, LTspice, etc.)

**Linux feasibility:**
- PyQt6 works on Linux
- Serial ports are `/dev/ttyUSB*` instead of `COM*`
- 3D visualization requires OpenGL drivers (NVIDIA proprietary may be needed)

**macOS challenges:**
- PyQt6 on macOS has quirks (menu bar placement, permissions)
- Serial port naming different (`/dev/cu.usbserial-*`)
- Not worth the effort for <5% potential users

**Trade-offs:**
- Platform lock-in (but mitigated by Python/Qt cross-platform nature)

**Verdict:** Focus on **Windows first**, port to Linux if needed. Don't spend time on macOS.

---

## Decision 11: Pytest for Testing (Not Unittest)

### Context
Which testing framework for 54 unit tests?

### Decision
Use **pytest** (not Python's built-in `unittest`).

### Rationale

**pytest advantages:**
1. **Less boilerplate:** No need to subclass `unittest.TestCase`
2. **Better assertions:** `assert x == 5` instead of `self.assertEqual(x, 5)`
3. **Fixtures:** Powerful setup/teardown with dependency injection
4. **Plugins:** `pytest-qt` for Qt event loop handling
5. **Parallel execution:** `pytest-xdist` for faster test runs

**unittest disadvantages:**
- More verbose (class-based structure)
- No built-in Qt support
- Harder to mock complex objects

**Trade-offs:**
- pytest is an external dependency (vs. unittest in stdlib)

**Verdict:** pytest is the **modern Python standard**. `pytest-qt` is essential for Qt testing.

---

## Decision 12: Type Hints Throughout

### Context
Should we use Python type hints (PEP 484)?

### Decision
Yes, **add type hints to all function signatures**.

### Rationale

**Benefits:**
1. **IDE support:** Autocomplete, refactoring, inline error detection
2. **Self-documentation:** Function signatures are clearer
3. **Catch bugs early:** Linters (mypy, Pylance) find type errors before runtime

**Example:**
```python
def compute_rms(samples: List[float]) -> float:
    return np.sqrt(np.mean(np.square(samples)))
```

**Trade-offs:**
- Slightly more verbose code
- Learning curve for junior developers

**Verdict:** Type hints are **industry best practice** in modern Python (3.9+). Essential for large codebases.

---

## Summary Table

| Decision | Choice | Key Rationale |
|----------|--------|---------------|
| **1. Platform** | PyQt6 desktop | Performance, mature ecosystem, professional feel |
| **2. Modularity** | 5 specialized apps | Cognitive clarity, development efficiency |
| **3. Code reuse** | LauncherBase inheritance | DRY principle, 350 lines shared |
| **4. State management** | SessionContext singleton | Thread-safe, simple, global access |
| **5. Architecture** | Two-layer backend | Testability, portability, separation of concerns |
| **6. Protocol** | JSON line-delimited | Human-readable, flexible, easy to debug |
| **7. Plotting** | pyqtgraph | Performance, OpenGL acceleration, real-time focus |
| **8. Development** | Mock mode (DemoAdapter) | Parallel dev, safe demos, automated testing |
| **9. Storage** | File-based JSON | Simplicity, portability, human-readable |
| **10. Platform** | Windows primary | Lab machines, FTDI support, target audience |
| **11. Testing** | pytest + pytest-qt | Less boilerplate, better assertions, Qt support |
| **12. Type hints** | Yes, throughout | IDE support, self-documentation, catch bugs early |

---

## Lessons Learned

### What Worked Well
1. **LauncherBase inheritance** - Saved weeks of development time
2. **Mock mode** - Enabled rapid prototyping without hardware
3. **Two-layer backend** - Clean separation made testing easy
4. **pyqtgraph** - Real-time plotting was trivial with right tool

### What Would We Change
1. **Earlier integration testing** - Found Qt event loop issues late in development
2. **More session comparison features** - Only basic replay implemented, not diff/comparison
3. **Database for large datasets** - File-based storage starts to struggle with 100+ sessions
4. **Linux testing** - Didn't validate on Linux until late (discovered minor serial port issues)

### Advice for Future Projects
- **Choose native over web** for real-time engineering tools
- **Invest in mock/demo mode early** - Pays dividends throughout development
- **Singleton + signals** works great for desktop apps (don't over-engineer with Redux-like patterns)
- **Type hints from day 1** - Refactoring is painful without them

---

## Related Documentation

- **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** - Senior design project context
- **[REDBYTE_HERITAGE.md](REDBYTE_HERITAGE.md)** - Why PyQt6 instead of React
- **[MODULAR_ARCHITECTURE.md](MODULAR_ARCHITECTURE.md)** - 5-app suite design
- **[HARDWARE_INTEGRATION.md](HARDWARE_INTEGRATION.md)** - Serial protocol specification

---

*Last Updated: February 1, 2026*
