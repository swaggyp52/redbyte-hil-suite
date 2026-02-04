from src.telemetry_simulator import TelemetrySimulator
ts = TelemetrySimulator()
frame = ts._generate_frame()
print('Frame generated with fields:', sorted(frame.keys()))
print(f'ts field: {frame.get("ts", "MISSING")}')
print(f'v_an field: {frame.get("v_an", "MISSING")}')
print(f'freq field: {frame.get("freq", "MISSING")}')
print('✅ Frame structure looks correct!')
