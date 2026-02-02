# Failure Modes and Effects Analysis (FMEA)

| ID | Failure Mode | Potential Cause | System Effect | Mitigation |
|----|--------------|-----------------|---------------|------------|
| FM-01 | Serial Disconnect | Hardware unplugged | Data loss | Auto-reconnect thread; UI Status Inidcator |
| FM-02 | JSON Corruption | Baud rate mismatch | Parser Crash | Try/Except block in `SerialReader` |
| FM-03 | Disk Full | Long recording | Crash on Save | Check disk space (Planned); Buffered write |
| FM-04 | Scenario Script Error | Bad JSON syntax | Test fails to start | Validation on Load in `ScenarioController` |
| FM-05 | Analysis Mismatch | Different sample rates | Crash in Diff Calc | Truncate to shorter length; Resample (Future) |
