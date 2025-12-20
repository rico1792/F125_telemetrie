# telemetry_store.py
import collections

# Buffer partagé pour la télémétrie (accessible par la capture ET Dash)
telemetry_buf = collections.deque(maxlen=5000)  # ~30–60 s de données
