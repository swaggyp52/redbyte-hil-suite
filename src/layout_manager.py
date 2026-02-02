import time


class LayoutManager:
    def __init__(self, window):
        self.window = window
        self._last_switch = 0.0
        self._cooldown = 1.5

    def on_metrics(self, thd):
        now = time.time()
        if thd > 5.0 and now - self._last_switch > self._cooldown:
            self.window.replay_studio.tabs.setCurrentIndex(2)
            self._last_switch = now

    def on_frame(self, frame):
        # Disabled automatic layout switching to prevent UI resets
        pass
