from math import radians, sin, cos, sqrt, atan2


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の距離をキロメートルで返す（ハーバーサイン公式）"""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def within_radius(rest_lat: float, rest_lon: float,
                  station_lat: float, station_lon: float,
                  radius_km: float = 0.5) -> bool:
    """レストランが駅から radius_km 以内かどうかを判定する"""
    return haversine_km(rest_lat, rest_lon, station_lat, station_lon) <= radius_km


def nearest_station(rest_lat: float, rest_lon: float,
                    stations: dict) -> tuple[str, float]:
    """
    stations: {station_name: (lat, lon), ...}
    最寄り駅名とその距離(km)を返す
    """
    best_name = ""
    best_dist = float("inf")
    for name, (slat, slon) in stations.items():
        d = haversine_km(rest_lat, rest_lon, slat, slon)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name, best_dist
