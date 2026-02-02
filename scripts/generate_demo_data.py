import json
import os
import math
import time
import random

DATA_DIR = "data/demo_sessions"
os.makedirs(DATA_DIR, exist_ok=True)

def generate_session(filename, scenario="baseline"):
    frames = []
    events = []
    
    # 20 seconds of data at 100Hz
    start_ts = time.time()
    fs = 100
    duration = 20.0
    num_frames = int(duration * fs)
    
    freq = 60.0
    amp = 120.0
    
    for i in range(num_frames):
        t_rel = i / fs
        ts = start_ts + t_rel
        
        # Base Simulation State
        v_mag = amp
        i_mag = 5.0
        curr_freq = freq
        
        # --- Scenarios ---
        if scenario == "fault_sag" and 5.0 <= t_rel <= 8.0:
            v_mag *= 0.4 # 60% sag
            if i == 500:
                events.append({"ts": ts, "type": "fault", "details": "Voltage Sag (L-G)"})
        
        if scenario == "freq_drift" and t_rel > 10.0:
            curr_freq += (t_rel - 10.0) * 0.5 # 0.5Hz/s drift
            if i == 1000:
                events.append({"ts": ts, "type": "event", "details": "Frequency Excursion Start"})

        # --- Signal Synthesis (3-Phase) ---
        dt = t_rel
        v_an = v_mag * math.sin(2 * math.pi * curr_freq * dt)
        v_bn = v_mag * math.sin(2 * math.pi * curr_freq * dt - 2.0944) # -120 deg
        v_cn = v_mag * math.sin(2 * math.pi * curr_freq * dt + 2.0944) # +120 deg
        
        # Add some harmonics/noise for realism
        v_an += 2.0 * math.sin(2 * math.pi * (curr_freq*3) * dt) # 3rd harmonic
        v_an += random.uniform(-0.5, 0.5)
        
        i_a = i_mag * math.sin(2 * math.pi * curr_freq * dt - 0.5) # Lagging PF
        i_b = i_mag * math.sin(2 * math.pi * curr_freq * dt - 0.5 - 2.0944)
        i_c = i_mag * math.sin(2 * math.pi * curr_freq * dt - 0.5 + 2.0944)
        
        frames.append({
            "ts": ts,
            "v_an": round(v_an, 3),
            "v_bn": round(v_bn, 3),
            "v_cn": round(v_cn, 3),
            "i_a": round(i_a, 3),
            "i_b": round(i_b, 3),
            "i_c": round(i_c, 3),
            "freq": round(curr_freq, 2),
            "status": 1
        })
        
    session = {
        "meta": {
            "scenario": scenario,
            "version": "1.2",
            "timestamp": time.ctime(start_ts)
        },
        "events": events,
        "frames": frames
    }
    
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w') as f:
        json.dump(session, f)
    print(f"Generated {path} ({len(frames)} frames)")

if __name__ == "__main__":
    generate_session("session_nominal.json", "baseline")
    generate_session("session_fault.json", "fault_sag")
    generate_session("session_drift.json", "freq_drift")
