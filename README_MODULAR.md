# 🔴 RedByte HIL Verifier Suite v2.0

**Modular, Purpose-Built Hardware-in-the-Loop Testing Platform**

---

## 🎯 What is RedByte?

RedByte is a **modular suite of 5 specialized applications** for Hardware-in-the-Loop (HIL) testing of three-phase inverter systems. Each app has a distinct purpose, visual identity, and workflow — but all share a unified backend for seamless cross-app data handoff.

### Why RedByte v2.0?

**Before (v1.x):** Single monolithic app with all panels crammed together  
**After (v2.0):** 5 clean, focused apps - use only what you need

---

## 🧩 The Suite

<table>
<tr>
<td align="center" width="20%">

### 🟩
**Diagnostics**

Live Ops + Fault Injection

[Launch →](src/launchers/launch_diagnostics.py)

</td>
<td align="center" width="20%">

### 🔵
**Replay Studio**

Timeline Playback & Review

[Launch →](src/launchers/launch_replay.py)

</td>
<td align="center" width="20%">

### 🟪
**Compliance Lab**

Standards & Scoring

[Launch →](src/launchers/launch_compliance.py)

</td>
<td align="center" width="20%">

### 🟨
**Insight Studio**

AI Cognitive Analysis

[Launch →](src/launchers/launch_insights.py)

</td>
<td align="center" width="20%">

### 🟧
**Signal Sculptor**

Live Waveform Editing

[Launch →](src/launchers/launch_sculptor.py)

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Launch Main Selector
```bash
# Windows
bin\launch_redbyte.bat

# Linux/Mac
python3 src/redbyte_launcher.py
```

**Or launch individual apps directly:**
```bash
bin\diagnostics.bat          # Quick launch Diagnostics
python src/launchers/launch_replay.py     # Replay Studio
python src/launchers/launch_compliance.py # Compliance Lab
```

---

## 💎 Key Features

### ✅ Modular Architecture
- Each app loads only needed panels
- No UI clutter from unrelated features
- Independent processes with shared backend

### ✅ Visual Identity
- Unique color accent per app
- Instant brand recognition
- Cyber-industrial aesthetic throughout

### ✅ Seamless Handoff
- Export session from Diagnostics
- Open in Replay Studio with one click
- All waveforms and insights preserved

### ✅ Real-Time Performance
- 20 Hz live monitoring
- Hardware-accelerated graphics (OpenGL)
- Circular buffer efficiency (O(1) append)

### ✅ AI-Powered Insights
- Automatic THD detection
- Frequency drift monitoring
- Phase imbalance alerts
- Event clustering and pattern analysis

---

## 📋 Typical Workflows

### 🟩 Live Monitoring
1. Launch **Diagnostics**
2. Click ▶️ Start monitoring
3. Inject fault (voltage sag, phase imbalance, etc.)
4. Watch insights auto-detect anomalies

### 🔵 Timeline Review
1. From Diagnostics, click **"Open in Replay Studio"**
2. Replay Studio launches with captured session
3. Scrub timeline to review events
4. Add tags at key moments

### 🟪 Compliance Testing
1. Export from Diagnostics to **Compliance Lab**
2. Run automated validation tests
3. View pass/fail scorecard
4. Generate HTML compliance report

---

## 🏗️ Architecture

### Shared Backend (`src/hil_core/`)
```
SessionContext    → Cross-app state management
SignalEngine      → Unified signal processing
FaultEngine       → Centralized fault injection
InsightEngine     → AI event detection
ContextExporter   → Session handoff utilities
```

### App-Specific Themes (`ui/app_themes.py`)
```python
get_diagnostics_style()  # Green accent
get_replay_style()       # Cyan accent
get_compliance_style()   # Purple accent
get_insights_style()     # Amber accent
get_sculptor_style()     # Orange accent
```

### Launchers (`src/launchers/`)
```
launch_diagnostics.py  → 🟩 Green-themed live ops
launch_replay.py       → 🔵 Cyan-themed timeline
launch_compliance.py   → 🟪 Purple-themed validation
launch_insights.py     → 🟨 Amber-themed AI analysis
launch_sculptor.py     → 🟧 Orange-themed editing
```

---

## 📖 Documentation

| Document                                                     | Description                     |
| ------------------------------------------------------------ | ------------------------------- |
| [QUICK_START_MODULAR.md](docs/QUICK_START_MODULAR.md)       | Usage guide with workflows      |
| [MODULAR_ARCHITECTURE.md](docs/MODULAR_ARCHITECTURE.md)     | Technical architecture overview |
| [REDBYTE_UX_COMPLETE.md](docs/REDBYTE_UX_COMPLETE.md)       | Visual enhancement details      |
| [geometry_persistence_fix.md](docs/geometry_persistence_fix.md) | Panel position stability fix    |

---

## 🛠️ Installation

### Prerequisites
- Python 3.9+
- PyQt6
- NumPy, SciPy
- pyqtgraph

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Verify Installation
```bash
python src/redbyte_launcher.py
```

If the launcher window appears with 5 app cards, installation is successful! ✅

---

## 🧪 Testing

### Run Test Suite
```bash
python tests/test_visual_enhancements.py  # UX tests
python tests/test_system.py               # Integration tests
python scripts/test_geometry_persistence.py  # Panel stability
```

### Manual Testing Checklist
See [QUICK_START_MODULAR.md](docs/QUICK_START_MODULAR.md#-testing-checklist)

---

## 🎨 Visual Showcase

### Main Launcher
```
┌─────────────────────────────────────┐
│  🔴 RedByte HIL Verifier Suite      │
│     Select Your Application         │
├─────────────────────────────────────┤
│  🟩 Diagnostics   🔵 Replay Studio  │
│  🟪 Compliance    🟨 Insight Studio │
│  🟧 Signal Sculptor                 │
└─────────────────────────────────────┘
```

### Diagnostics Layout
```
┌─────────────┬──────┬────────┐
│             │ 💡   │  🌈    │
│  ⚙️ 3D      │Insig │Phasor  │
│  System     │hts   │        │
├─────────────┼──────┴────────┤
│             │               │
│  📊 Scope   │  💉 Injector  │
│             │               │
└─────────────┴───────────────┘
```

---

## 🔧 Customization

### Add a New App

1. **Create launcher:**
   ```python
   # src/launchers/launch_myapp.py
   from hil_core import SessionContext
   
   class MyAppWindow(QMainWindow):
       def __init__(self):
           self.session = SessionContext()
   ```

2. **Add theme:**
   ```python
   # ui/app_themes.py
   def get_myapp_style():
       return get_base_style() + """
       QPushButton { border: 2px solid #ff6b6b; }
       """
   ```

3. **Register in launcher:**
   ```python
   # src/redbyte_launcher.py
   apps.append({
       'name': 'My App',
       'accent': '#ff6b6b',
       'icon': '🔴',
       'launcher': 'launch_myapp.py'
   })
   ```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Qt/PyQt6** - Cross-platform UI framework
- **pyqtgraph** - High-performance plotting
- **NumPy/SciPy** - Scientific computing
- **JetBrains Mono** - Developer-focused monospace font

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/your-org/redbyte/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-org/redbyte/discussions)
- **Email:** support@redbyte.io

---

## 🗺️ Roadmap

### v2.1 (Next Release)
- [ ] Cloud session storage (Azure Blob)
- [ ] Remote collaboration (multi-user)
- [ ] Mobile companion app (iOS/Android)
- [ ] REST API for external tools

### v2.2
- [ ] ML-based fault prediction
- [ ] Plugin system for custom analyzers
- [ ] Real-time collaboration features
- [ ] Advanced 3D visualization modes

### v3.0
- [ ] Full cloud-native architecture
- [ ] Kubernetes deployment
- [ ] Web-based UI (React/TypeScript)
- [ ] Distributed HIL testing

---

<p align="center">
  <b>Built with ❤️ for HIL Engineers</b><br>
  <i>From monolithic mess to modular masterpiece</i><br><br>
  <sub>RedByte Suite v2.0 • 2026 • MIT Licensed</sub>
</p>
