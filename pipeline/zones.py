import json
import os
from typing import List, Tuple, Dict, Any, Optional

def is_point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
    """
    Ray-casting algorithm to determine if a point (x, y) is inside a polygon.
    """
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

class ZoneMapper:
    def __init__(self, layout_path: str):
        self.store_id: str = "UNKNOWN"
        self.zones: List[Dict[str, Any]] = []
        
        if os.path.exists(layout_path):
            try:
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.store_id = data.get("store_id", "UNKNOWN")
                    self.zones = data.get("zones", [])
            except Exception as e:
                print(f"Error loading layout file: {str(e)}")
        else:
            print(f"Layout file not found at: {layout_path}")

    def get_zone_at_coordinate(self, camera_id: str, x: float, y: float) -> Optional[str]:
        """
        Iterates over the loaded zones and maps the coordinate to the appropriate zone ID
        if it lies within its polygon boundary.
        """
        for zone in self.zones:
            if zone.get("camera_id") == camera_id:
                poly = zone.get("polygon")
                if poly and is_point_in_polygon(x, y, poly):
                    return zone.get("zone_id")
        return None
