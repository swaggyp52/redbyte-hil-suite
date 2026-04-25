# VSM Evidence Workbench — Documentation Index

> Local desktop engineering workstation for post-run analysis, replay,
> comparison, and standards-inspired evaluation of VSM / Grid-Forming
> inverter test data. See the root `README.md` for the authoritative
> product overview.

---

## Start here

| Document | What it covers |
|----------|----------------|
| [`../README.md`](../README.md) | Product overview, supported formats, end-to-end workflow, rule profiles, honesty statement. |
| [`QUICK_START_GUIDE.md`](QUICK_START_GUIDE.md) | Install + launch in under a minute. |
| [`demo_script.md`](demo_script.md) | The demo walkthrough used during the capstone presentation. |
| [`presentation_walkthrough.md`](presentation_walkthrough.md) | Slide-by-slide narration for the defense. |

## Engineering reference

| Document | What it covers |
|----------|----------------|
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | Capstone context, problem framing, software scope. |
| [`architecture.md`](architecture.md) | Module layout (src / ui), signal flow, Data Capsule schema. |
| [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) | Key design decisions and rationale. |
| [`MODULAR_ARCHITECTURE.md`](MODULAR_ARCHITECTURE.md) | Launcher-level modular structure. |
| [`api_reference.md`](api_reference.md) | Public module APIs (importer, analysis, compliance, report). |
| [`launcher_architecture.md`](launcher_architecture.md) | How the launcher menu wires the apps. |
| [`HARDWARE_INTEGRATION.md`](HARDWARE_INTEGRATION.md) | How an HIL/lab input adapter would feed this app (future integration). |
| [`protocol.md`](protocol.md) | Frame protocol assumed by the optional input-adapter path. |

## Verification & test

| Document | What it covers |
|----------|----------------|
| [`test_plan.md`](test_plan.md) | Test strategy and coverage. |
| [`fmea.md`](fmea.md) | Failure modes & effects analysis. |
| [`deployment_notes.md`](deployment_notes.md) | Run environment expectations. |

## Reports and presentation

| Document | What it covers |
|----------|----------------|
| [`final_report_outline.md`](final_report_outline.md) | Outline for the capstone paper. |
| [`QUICK_REFERENCE_CARD.md`](QUICK_REFERENCE_CARD.md) | One-page feature card. |
| [`context_workflow.md`](context_workflow.md) | Workflow quick reference. |
| [`REDBYTE_HERITAGE.md`](REDBYTE_HERITAGE.md) | Origin story of the project branding. |

## Archived

See [`archive/`](archive/) for process artifacts from the earlier
"HIL Verifier Suite" phase that are retained for history but no longer
reflect the current product.
