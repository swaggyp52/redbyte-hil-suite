def evaluate_system_status(thd, fault_active=False, freq=60.0, freq_nom=60.0):
    """Return system status string based on thresholds."""
    freq_dev = abs(freq - freq_nom)
    if fault_active or thd >= 10.0 or freq_dev >= 3.0:
        return "CRITICAL"
    if thd >= 5.0 or freq_dev >= 1.0:
        return "DEGRADED"
    return "NOMINAL"