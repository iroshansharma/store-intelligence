import hashlib

class VisitorTracker:
    """
    Maintains entity tracking logic, associating OpenCV/YOLO tracking IDs
    with stable, schema-compliant visitor IDs.
    """
    def __init__(self):
        self.track_to_visitor = {}

    def get_visitor_id(self, track_id: int) -> str:
        """
        Retrieves or generates a unique visitor ID from a tracking ID.
        Uses a stable MD5 hash truncated to 6 hex characters to generate ids
        that mirror Purplle requirements (e.g. VIS_a1b2c3).
        """
        if track_id not in self.track_to_visitor:
            hs = hashlib.md5(f"track_{track_id}".encode("utf-8")).hexdigest()[:6]
            self.track_to_visitor[track_id] = f"VIS_{hs}"
        return self.track_to_visitor[track_id]
