# Test Plan (Final)

## Level 0: Unit Tests

*Isolation tests for logic.*

| ID | Component | Description | Inputs | Expected Output | Status |
|----|-----------|-------------|--------|-----------------|--------|
| T0-01 | Data Parser | Parse valid JSON | `{"v":120}` | `{'v':120}` | **Pass** |
| T0-02 | Data Parser | Malformed JSON | `{"v":` | `ValueError` | **Pass** |
| T0-03 | Recorder | Data Capsule Format | Frames + Events | JSON file with `meta` | **Pass** |
| T0-04 | Analysis | Identical Sessions | File A, File A | RMSE = 0 | **Pass** |
| T0-05 | Analysis | Offset Sessions | File A, File B | RMSE > 0 | **Pass** |

## Level 1: Integration Tests

*Subsystem interaction.*

| ID | Interaction | Description | Status |
|----|-------------|-------------|--------|
| T1-01 | Serial->UI | Stream mock data | Graph updates | **Pass** |
| T1-02 | Scenario->Log | Trigger event | Event appears in Log | Pending |
| T1-03 | Replay->UI | Load File -> Play | Graph animates | Pending |

## Level 2: System Tests (Validation)

### Scenario Exec

- [ ] Load `voltage_sag.json`.
- [ ] Run.
- [ ] Verify "sag" event marked in recorder at t=5s.

### Comparison

- [ ] Record Run 1 (Baseline).
- [ ] Record Run 2 (Test).
- [ ] Open Analysis App.
- [ ] Load 1 & 2.
- [ ] Confirm RMSE is calculated and exported to CSV.
