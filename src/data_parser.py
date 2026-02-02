import json

def parse_telemetry_line(line: str) -> dict:
    """
    Parses a JSON-formatted telemetry line.
    
    Args:
        line (str): Raw string from serial port.
        
    Returns:
        dict: Parsed key-value pairs.
        
    Raises:
        ValueError: If JSON is malformed.
    """
    try:
        data = json.loads(line)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
