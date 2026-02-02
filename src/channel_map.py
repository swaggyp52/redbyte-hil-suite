from src.config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)

class ChannelMapper:
    """
    Renames and scales raw signal keys to human-readable labels.
    """
    def __init__(self):
        ConfigManager.load()
        self.config = ConfigManager.get_channel_config()
        self.map_table = ConfigManager.get_opal_map()

    def process(self, frame):
        """
        Input: Raw dict (e.g. {"UserFloat1": 120.0})
        Output: Processed dict (e.g. {"v_an": 120.0})
        """
        clean_frame = {}
        # Keep timestamp if present
        if 'ts' in frame:
            clean_frame['ts'] = frame['ts']
            
        for k, v in frame.items():
            if k == 'ts': continue
            
            # Check map
            if k in self.map_table:
                target_key = self.map_table[k]['key']
                scale = self.map_table[k].get('scale', 1.0)
                clean_frame[target_key] = v * scale
            elif k in self.config:
                # Already clean key
                clean_frame[k] = v
            else:
                # Pass through unknown keys for debugging
                clean_frame[k] = v
                
        return clean_frame

    def get_label(self, key):
        if key in self.config:
            return self.config[key].get("label", key)
        return key

    def get_unit(self, key):
        if key in self.config:
            return self.config[key].get("unit", "")
        return ""
