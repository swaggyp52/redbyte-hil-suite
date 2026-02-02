# Command & Telemetry Protocol

## Telemetry Frames

Adapters emit JSON dictionaries with the following typical keys:

```json
{
  "ts": 1700000000.123,
  "v_an": 120.4,
  "v_bn": -60.1,
  "v_cn": -60.3,
  "i_a": 5.2,
  "i_b": -2.6,
  "i_c": -2.5,
  "freq": 60.02,
  "p_mech": 1000.0,
  "status": 0
}
```

Notes:
- `ts` is a Unix timestamp in seconds.
- Voltage and current channels are instantaneous samples.
- If `v` is present, it is treated as a single-phase or averaged value.

## Serial Command Protocol

### Format
The serial adapter sends commands using a JSON payload prefixed with `CMD:` and terminated with a newline.

```
CMD:{"cmd":"fault_sag","params":{"duration":0.5,"depth":0.5}}
```

### Supported Commands
- `fault_sag` — request a voltage sag
  - `duration` (seconds)
  - `depth` (0.0–1.0)
- `fault_drift` — request frequency drift
  - `duration` (seconds)
  - `offset` (Hz)
- `clear_fault` — clear all active faults
- `inject_waveform` — request custom waveform generation
  - `freq` (Hz)
  - `amplitude` (V pk)
  - `noise` (V)
  - `duration` (seconds)

## OpalRT TCP Protocol

### Format
TCP transport uses a 4-byte big-endian length prefix followed by a JSON payload.

```
[uint32 length][{...json...}]
```

The command payload structure matches the serial protocol.

## Demo Adapter
The Demo adapter accepts the same commands and applies them to the synthetic signal generator for local testing.
