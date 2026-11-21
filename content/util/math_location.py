

import math

METERS_PER_DEGREE = 111320.0


def distance_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * METERS_PER_DEGREE
    dx = (lon2 - lon1) * METERS_PER_DEGREE * math.cos(math.radians((lat1 + lat2) * 0.5))
    return math.hypot(dx, dy)


def path_length(segments):
    total = 0.0
    for seg in segments:
        for (la1, lo1), (la2, lo2) in zip(seg, seg[1:]):
            total += distance_m(la1, lo1, la2, lo2)
    return total


def is_valid_coord(lat, lon):
    return -90 <= lat <= 90 and -180 <= lon <= 180