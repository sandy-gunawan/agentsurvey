import math

import httpx

from .auth import get_maps_token
from .config import settings

MAIN_ROAD_USES = {"LimitedAccess", "Arterial", "Ramp", "Rotary"}

# Titik asal rute hanya perlu cukup jauh agar mesin rute menarik tujuan ke jalan terdekat.
ROUTE_PROBE_OFFSET_DEG = 0.01


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_maps_token()}",
        "x-ms-client-id": settings.maps_client_id,
    }


async def reverse_geocode(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    resp = await client.get(
        f"{settings.maps_base_url}/search/address/reverse/json",
        params={
            "api-version": "1.0",
            "query": f"{lat},{lon}",
            "returnRoadUse": "true",
            "language": "id-ID",
        },
        headers=_headers(),
        timeout=20.0,
    )
    resp.raise_for_status()
    addresses = resp.json().get("addresses", [])
    if not addresses:
        return {"address": None, "roadUse": [], "street": None}
    first = addresses[0]
    return {
        "address": first.get("address", {}).get("freeformAddress"),
        "street": first.get("address", {}).get("streetName"),
        "roadUse": first.get("roadUse", []),
    }


async def geocode(client: httpx.AsyncClient, address: str) -> tuple[float, float] | None:
    resp = await client.get(
        f"{settings.maps_base_url}/search/address/json",
        params={"api-version": "1.0", "query": address, "limit": 1, "countrySet": "ID"},
        headers=_headers(),
        timeout=20.0,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    pos = results[0]["position"]
    return pos["lat"], pos["lon"]


async def car_snap(
    client: httpx.AsyncClient, lat: float, lon: float, origin: tuple[float, float]
) -> dict:
    """Titik akhir rute mobil adalah tempat terdekat yang benar-benar dapat dicapai kendaraan."""
    resp = await client.get(
        f"{settings.maps_base_url}/route/directions/json",
        params={
            "api-version": "1.0",
            "query": f"{origin[0]},{origin[1]}:{lat},{lon}",
            "travelMode": "car",
            "routeType": "shortest",
        },
        headers=_headers(),
        timeout=25.0,
    )
    if resp.status_code >= 400:
        return {"snapDistanceMeter": None, "carAccessible": "tidak_dapat_ditentukan"}

    routes = resp.json().get("routes", [])
    if not routes:
        return {"snapDistanceMeter": None, "carAccessible": "tidak_dapat_ditentukan"}

    points = routes[0]["legs"][-1]["points"]
    last = points[-1]
    snap = haversine_m(lat, lon, last["latitude"], last["longitude"])
    return {
        "snapDistanceMeter": round(snap),
        "carAccessible": "ya" if snap <= settings.gang_snap_threshold_m else "tidak",
    }


async def analyse_location(lat: float, lon: float, claimed_address: str) -> dict:
    result = {
        "reverseGeocodedAddress": None,
        "nearestStreet": None,
        "roadUse": [],
        "onMainRoad": "tidak_dapat_ditentukan",
        "addressMatch": "tidak_dapat_ditentukan",
        "addressDistanceMeter": None,
        "snapDistanceMeter": None,
        "carAccessible": "tidak_dapat_ditentukan",
        "mapCoverageLimited": False,
    }

    async with httpx.AsyncClient() as client:
        rev = await reverse_geocode(client, lat, lon)
        result["reverseGeocodedAddress"] = rev["address"]
        result["nearestStreet"] = rev["street"]
        result["roadUse"] = rev["roadUse"]
        if rev["roadUse"]:
            hit = MAIN_ROAD_USES.intersection(rev["roadUse"])
            result["onMainRoad"] = "ya" if hit else "tidak"
        if not rev["address"]:
            result["mapCoverageLimited"] = True

        claimed = await geocode(client, claimed_address) if claimed_address else None
        if claimed:
            dist = haversine_m(lat, lon, claimed[0], claimed[1])
            result["addressDistanceMeter"] = round(dist)
            if dist <= settings.address_match_radius_m:
                result["addressMatch"] = "cocok"
            elif dist <= settings.address_match_radius_m * 5:
                result["addressMatch"] = "cocok_sebagian"
            else:
                result["addressMatch"] = "tidak_cocok"

        origin = claimed or (lat + ROUTE_PROBE_OFFSET_DEG, lon + ROUTE_PROBE_OFFSET_DEG)
        result.update(await car_snap(client, lat, lon, origin))

    return result
