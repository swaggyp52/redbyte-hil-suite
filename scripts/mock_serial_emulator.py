import time
import json
import math
import sys

def run_emulator(port="COM4"):
    """
    Simulates the microcontroller by writing JSON to a file or stream.
    For MVP demo: We assume this script might print to STDOUT or write to a pipe.
    Ideally, use Com0Com pairs (e.g. COM3 <-> COM4).
    """
    print(f"Starting emulator on {port}...")
    print("Press Ctrl+C to stop.")
    
    try:
        # Just loop printing for now (Standard IO usage)
        start_t = time.time()
        while True:
            t = time.time() - start_t
            
            # Simulated VSM Signals
            v = 120.0 + 2.0 * math.sin(t)
            i = 10.0 + 0.5 * math.cos(t)
            freq = 60.0 + 0.05 * math.sin(t*0.5)
            
            frame = {
                "ts": t,
                "v": round(v, 2),
                "i": round(i, 2),
                "freq": round(freq, 3),
                "Vabc": [round(v, 2), round(v*0.99, 2), round(v*1.01, 2)]
            }
            
            json_str = json.dumps(frame)
            sys.stdout.write(json_str + "\n")
            sys.stdout.flush()
            
            time.sleep(0.01) # 100Hz
            
    except KeyboardInterrupt:
        print("\nEmulator stopped.")

if __name__ == "__main__":
    run_emulator()
