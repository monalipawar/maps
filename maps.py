import math
import json
import os

import streamlit as st
import streamlit.components.v1 as components
import requests
import folium

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from timezonefinder import TimezoneFinder
from streamlit_autorefresh import st_autorefresh


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Map Explorer V4",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS (rendered after session state so it can react to dark mode)
# ============================================================

def render_css():

    dark = st.session_state.dark_mode

    if dark:

        bg = "#0f172a"
        card_bg = "#1e293b"
        text = "#f1f5f9"
        subtext = "#94a3b8"
        shadow = "rgba(0,0,0,0.35)"
        traffic_bg = "#14532d"

    else:

        bg = "#f5f7fb"
        card_bg = "white"
        text = "#1a1a1a"
        subtext = "#687080"
        shadow = "rgba(0,0,0,0.08)"
        traffic_bg = "#e9f7ef"

    st.markdown(
        f"""
        <style>

        .stApp {{
            background: {bg};
        }}

        .main-title {{
            font-size: 44px;
            font-weight: 800;
            margin-bottom: 0;
            color: {text};
        }}

        .subtitle {{
            color: {subtext};
            font-size: 17px;
            margin-bottom: 20px;
        }}

        .eta-card {{
            background: {card_bg};
            padding: 24px;
            border-radius: 18px;
            box-shadow: 0 4px 18px {shadow};
            text-align: center;
            margin-top: 18px;
        }}

        .eta-label {{
            color: {subtext};
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .eta-time {{
            font-size: 42px;
            font-weight: 800;
            margin-top: 5px;
            color: {text};
        }}

        .eta-date {{
            color: {subtext};
            font-size: 14px;
        }}

        .route-card {{
            background: {card_bg};
            padding: 18px;
            border-radius: 15px;
            margin-bottom: 10px;
            box-shadow: 0 2px 10px {shadow};
            color: {text};
        }}

        .traffic-normal {{
            background: {traffic_bg};
            padding: 12px;
            border-radius: 12px;
            margin-top: 12px;
            color: {text};
        }}

        .info-card {{
            background: {card_bg};
            padding: 18px;
            border-radius: 15px;
            margin-top: 12px;
            box-shadow: 0 2px 10px {shadow};
            color: {text};
        }}

        .place-card {{
            background: {card_bg};
            padding: 14px;
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 2px 8px {shadow};
            color: {text};
        }}

        .closest-badge {{
            display: inline-block;
            background: #22c55e;
            color: white;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 8px;
            margin-left: 6px;
            letter-spacing: 0.3px;
        }}

        .eta-skeleton {{
            background: {card_bg};
            padding: 24px;
            border-radius: 18px;
            box-shadow: 0 4px 18px {shadow};
            text-align: center;
            margin-top: 18px;
        }}

        div[data-testid="stMetric"] {{
            background: {card_bg};
            border-radius: 12px;
            padding: 12px;
            box-shadow: 0 2px 8px {shadow};
        }}

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] div {{
            color: {text} !important;
        }}

        /* Tighten spacing between the location search result buttons */
        section[data-testid="stSidebar"] div[data-testid="stButton"] {{
            margin-bottom: -14px;
        }}

        section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
            padding-top: 6px;
            padding-bottom: 6px;
            min-height: 0;
            line-height: 1.2;
        }}

        /* Mobile tightening: smaller headline/ETA text, less
           padding, so the app doesn't feel oversized on phones. */
        @media (max-width: 640px) {{

            .main-title {{
                font-size: 30px;
            }}

            .subtitle {{
                font-size: 14px;
                margin-bottom: 12px;
            }}

            .eta-card, .eta-skeleton {{
                padding: 16px;
            }}

            .eta-time {{
                font-size: 32px;
            }}

            .route-card, .info-card, .place-card {{
                padding: 12px;
            }}

            div[data-testid="stMetric"] {{
                padding: 8px;
            }}

            div[data-testid="stMetricValue"] {{
                font-size: 18px;
            }}
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "current_lat": None,
    "current_lon": None,

    "search_lat": None,
    "search_lon": None,
    "search_address": None,

    "search_results": [],
    "last_search_debug": [],

    "routes": [],

    "favorites": [],

    "map_click": None,

    "nearby_places": [],

    "map_style": "OpenStreetMap",

    "route_mode": "driving",

    "recent_searches": [],

    "dark_mode": False,

    "arrive_by": None,

    "waypoints": [],

    "google_api_call_count": 0,

    "last_removed_favorite": None,
    "last_removed_waypoint": None,

    "route_presets": [],

    "optimize_stop_order": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

render_css()


# ============================================================
# LOCAL PERSISTENCE (favorites, recent searches, presets)
#
# Note: this saves to a JSON file on the app's local disk. On
# Streamlit Cloud this persists between reruns/reboots as long
# as the container isn't rebuilt (e.g. a fresh deploy from a
# git push), but it is NOT per-visitor — if multiple people use
# the same deployed app, they'd share this file. Fine for a
# personal single-user app; not a substitute for a real database
# if this app is ever shared with others.
# ============================================================

PERSISTENCE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "map_explorer_data.json",
)


def save_persisted_data():

    try:

        data = {
            "favorites": st.session_state.favorites,
            "recent_searches": st.session_state.recent_searches,
            "route_presets": st.session_state.route_presets,
        }

        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(data, f)

    except Exception:
        pass


def load_persisted_data():

    try:

        if not os.path.exists(PERSISTENCE_FILE):
            return

        with open(PERSISTENCE_FILE, "r") as f:
            data = json.load(f)

        if not st.session_state.favorites:
            st.session_state.favorites = data.get("favorites", [])

        if not st.session_state.recent_searches:
            st.session_state.recent_searches = data.get(
                "recent_searches", []
            )

        if not st.session_state.route_presets:
            st.session_state.route_presets = data.get(
                "route_presets", []
            )

    except Exception:
        pass


if "persisted_data_loaded" not in st.session_state:

    load_persisted_data()
    st.session_state.persisted_data_loaded = True


# ============================================================
# LOAD SHARED ROUTE FROM URL (if the app was opened via a
# shared link with dest_lat/dest_lon/dest_name params)
# ============================================================

if (
    "shared_link_loaded" not in st.session_state
    and "dest_lat" in st.query_params
    and "dest_lon" in st.query_params
):

    try:

        st.session_state.search_lat = float(
            st.query_params["dest_lat"]
        )

        st.session_state.search_lon = float(
            st.query_params["dest_lon"]
        )

        st.session_state.search_address = st.query_params.get(
            "dest_name",
            "Shared destination",
        )

    except (ValueError, TypeError):

        pass

    st.session_state.shared_link_loaded = True


# ============================================================
# SERVICES
# ============================================================

geolocator = Nominatim(
    user_agent="MapExplorerV4/1.0"
)

timezone_finder = TimezoneFinder()

GOOGLE_MAPS_API_KEY = st.secrets.get(
    "GOOGLE_MAPS_API_KEY",
    "",
)


# ============================================================
# AUTOMATIC ETA REFRESH
# ============================================================

# Refresh every 30 seconds once a route exists, to keep the
# metrics/map in sync. The big ETA clock itself ticks live via
# client-side JavaScript below, so it doesn't need a full rerun
# every second.

if st.session_state.routes:

    st_autorefresh(
        interval=30 * 1000,
        key="eta_refresh",
    )


# ============================================================
# DISTANCE HELPER
# ============================================================

def haversine_miles(lat1, lon1, lat2, lon2):

    R = 3958.8  # Earth radius in miles

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lambda / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return R * c


# ============================================================
# GOOGLE PLACES AUTOCOMPLETE (legacy endpoint) - shown below
# the search box as the user types. Uses the legacy Autocomplete
# API specifically because it can return an actual distance
# from the origin per suggestion, so results can be ranked
# closest to farthest (the newer Autocomplete API omits this).
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def get_autocomplete_suggestions(query, origin_lat=None, origin_lon=None):

    if not GOOGLE_MAPS_API_KEY or len(query.strip()) < 3:
        return []

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"

    params = {
        "input": query,
        "key": GOOGLE_MAPS_API_KEY,
    }

    if origin_lat is not None and origin_lon is not None:

        # "origin" enables distance_meters on each prediction.
        # "location" + "radius" bias results toward that area.
        params["origin"] = f"{origin_lat},{origin_lon}"
        params["location"] = f"{origin_lat},{origin_lon}"
        params["radius"] = 50000

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        st.session_state.google_api_call_count += 1

        data = response.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            return []

        suggestions = []

        for prediction in data.get("predictions", [])[:5]:

            text = prediction.get("description", "")

            if not text:
                continue

            distance_meters = prediction.get("distance_meters")

            suggestions.append(
                {
                    "text": text,
                    "distance_miles": (
                        distance_meters / 1609.344
                        if distance_meters is not None
                        else None
                    ),
                }
            )

        # Rank closest to farthest. Suggestions without a
        # distance (e.g. no origin known) sort to the end.
        suggestions.sort(
            key=lambda s: (
                s["distance_miles"] is None,
                s["distance_miles"] or 0,
            )
        )

        return suggestions

    except Exception:

        return []


# ============================================================
# GOOGLE PLACES SEARCH (Text Search - New) - proximity-biased,
# uses Google's business listing data instead of OSM, so it
# reliably finds the actual closest match.
# ============================================================

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def search_places(query, origin_lat=None, origin_lon=None, limit=5):

    debug_notes = []

    if not GOOGLE_MAPS_API_KEY:

        st.session_state.last_search_debug = [
            "No GOOGLE_MAPS_API_KEY found in Streamlit secrets."
        ]

        return []

    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location"
        ),
    }

    body = {
        "textQuery": query,
        "pageSize": 20,
    }

    if origin_lat is not None and origin_lon is not None:

        # Bias (not restrict) results toward the user's area,
        # so nearby matches are preferred without excluding a
        # genuinely relevant distant match entirely.
        body["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": origin_lat,
                    "longitude": origin_lon,
                },
                "radius": 50000.0,  # meters, ~31 miles
            }
        }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=15,
        )

        response.raise_for_status()

        st.session_state.google_api_call_count += 1

        data = response.json()

        places = data.get("places", [])

        if not places:

            debug_notes.append(
                "Google Places returned no matches."
            )

            st.session_state.last_search_debug = debug_notes

            return []

        results = []

        for place in places:

            location = place.get("location", {})

            place_lat = location.get("latitude")
            place_lon = location.get("longitude")

            if place_lat is None or place_lon is None:
                continue

            display_name = place.get(
                "displayName", {}
            ).get("text", "")

            address = place.get(
                "formattedAddress", ""
            )

            full_address = (
                f"{display_name}, {address}"
                if display_name
                else address
            )

            results.append(
                {
                    "lat": place_lat,
                    "lon": place_lon,
                    "address": full_address,
                }
            )

        if origin_lat is not None and origin_lon is not None:

            for result in results:

                result["distance_miles"] = haversine_miles(
                    origin_lat,
                    origin_lon,
                    result["lat"],
                    result["lon"],
                )

            results.sort(
                key=lambda r: r["distance_miles"]
            )

        else:

            for result in results:
                result["distance_miles"] = None

        st.session_state.last_search_debug = debug_notes

        return results[:limit]

    except Exception as exc:

        # Graceful degradation: if Google Places errors out
        # (quota hit, network issue, bad key), fall back to
        # the free Nominatim stack rather than showing nothing.
        try:

            fallback_kwargs = dict(
                timeout=10,
                addressdetails=True,
                exactly_one=False,
                limit=20,
            )

            locations = geolocator.geocode(
                query,
                **fallback_kwargs,
            )

            if locations:

                fallback_results = [
                    {
                        "lat": loc.latitude,
                        "lon": loc.longitude,
                        "address": loc.address,
                    }
                    for loc in locations
                ]

                if origin_lat is not None and origin_lon is not None:

                    for result in fallback_results:

                        result["distance_miles"] = haversine_miles(
                            origin_lat,
                            origin_lon,
                            result["lat"],
                            result["lon"],
                        )

                    fallback_results.sort(
                        key=lambda r: r["distance_miles"]
                    )

                else:

                    for result in fallback_results:
                        result["distance_miles"] = None

                st.session_state.last_search_debug = [
                    f"Google Places error: {exc}",
                    "Fell back to free OpenStreetMap search.",
                ]

                return fallback_results[:limit]

        except Exception:
            pass

        st.session_state.last_search_debug = [
            f"Google Places error: {exc}",
            "Fallback search also failed.",
        ]

        return []


# ============================================================
# REVERSE GEOCODING
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat, lon):

    try:

        location = geolocator.reverse(
            (lat, lon),
            timeout=10,
            addressdetails=True,
        )

        if location:
            return location.address

    except Exception:

        return None

    return None


# ============================================================
# TIMEZONE
# ============================================================

@st.cache_data(ttl=86400)
def get_timezone(lat, lon):

    try:

        return timezone_finder.timezone_at(
            lat=lat,
            lng=lon,
        )

    except Exception:

        return None


# ============================================================
# CURRENT TIME AT DESTINATION
# ============================================================

def get_destination_time(lat, lon):

    timezone_name = get_timezone(
        lat,
        lon,
    )

    if timezone_name:

        try:

            return datetime.now(
                ZoneInfo(timezone_name)
            )

        except Exception:
            pass

    return datetime.now()


# ============================================================
# ELEVATION PROFILE (Google Elevation API)
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_elevation_profile(sampled_points):

    if not GOOGLE_MAPS_API_KEY or not sampled_points:
        return []

    locations = "|".join(
        f"{lat},{lon}" for lat, lon in sampled_points
    )

    url = "https://maps.googleapis.com/maps/api/elevation/json"

    params = {
        "locations": locations,
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:

        response = requests.get(url, params=params, timeout=15)

        response.raise_for_status()

        st.session_state.google_api_call_count += 1

        data = response.json()

        if data.get("status") != "OK":
            return []

        return [
            result["elevation"] * 3.28084  # meters -> feet
            for result in data.get("results", [])
        ]

    except Exception:

        return []


# ============================================================
# DESTINATION WEATHER (free, Open-Meteo — no key required)
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def get_destination_weather(lat, lon):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "temperature_unit": "fahrenheit",
    }

    weather_code_map = {
        0: ("☀️", "Clear"),
        1: ("🌤️", "Mostly clear"),
        2: ("⛅", "Partly cloudy"),
        3: ("☁️", "Overcast"),
        45: ("🌫️", "Fog"),
        48: ("🌫️", "Fog"),
        51: ("🌦️", "Light drizzle"),
        53: ("🌦️", "Drizzle"),
        55: ("🌧️", "Heavy drizzle"),
        61: ("🌦️", "Light rain"),
        63: ("🌧️", "Rain"),
        65: ("🌧️", "Heavy rain"),
        71: ("🌨️", "Light snow"),
        73: ("🌨️", "Snow"),
        75: ("❄️", "Heavy snow"),
        80: ("🌦️", "Rain showers"),
        81: ("🌧️", "Rain showers"),
        82: ("⛈️", "Violent showers"),
        95: ("⛈️", "Thunderstorm"),
    }

    try:

        response = requests.get(url, params=params, timeout=10)

        response.raise_for_status()

        data = response.json()

        current = data.get("current", {})

        temperature = current.get("temperature_2m")
        code = current.get("weather_code")

        if temperature is None:
            return None

        icon, label = weather_code_map.get(code, ("🌡️", "—"))

        return {
            "temperature": round(temperature),
            "icon": icon,
            "label": label,
        }

    except Exception:

        return None


# ============================================================
# POLYLINE DECODER (Google's encoded polyline algorithm)
# ============================================================

def decode_polyline(encoded):

    points = []
    index = 0
    lat = 0
    lon = 0

    while index < len(encoded):

        for field in ["lat", "lon"]:

            shift = 0
            result = 0

            while True:

                byte = ord(encoded[index]) - 63
                index += 1

                result |= (byte & 0x1f) << shift
                shift += 5

                if byte < 0x20:
                    break

            delta = (
                ~(result >> 1)
                if (result & 1)
                else (result >> 1)
            )

            if field == "lat":
                lat += delta
            else:
                lon += delta

        points.append([lat / 1e5, lon / 1e5])

    return points


# ============================================================
# GOOGLE ROUTES API
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_osrm_routes(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    mode,
    waypoints=None,
    optimize_order=False,
):

    if not GOOGLE_MAPS_API_KEY:

        try:
            return get_osrm_fallback_routes(
                start_lat, start_lon, end_lat, end_lon, mode
            )
        except Exception:
            return []

    travel_mode_map = {
        "driving": "DRIVE",
        "walking": "WALK",
        "cycling": "BICYCLE",
    }

    travel_mode = travel_mode_map.get(
        mode,
        "DRIVE",
    )

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": (
            "routes.distanceMeters,"
            "routes.duration,"
            "routes.polyline.encodedPolyline"
        ),
    }

    body = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": start_lat,
                    "longitude": start_lon,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": end_lat,
                    "longitude": end_lon,
                }
            }
        },
        "travelMode": travel_mode,
        "computeAlternativeRoutes": (
            not waypoints
        ),
    }

    # Multi-stop routing: intermediate waypoints, visited in
    # the order given (unless optimize_order is requested).
    if waypoints:

        body["intermediates"] = [
            {
                "location": {
                    "latLng": {
                        "latitude": wp["lat"],
                        "longitude": wp["lon"],
                    }
                }
            }
            for wp in waypoints
        ]

        if optimize_order:
            body["optimizeWaypointOrder"] = True

    # Driving-only options (routing preference doesn't apply
    # to walking/cycling)
    if travel_mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"

    field_mask = (
        "routes.distanceMeters,"
        "routes.duration,"
        "routes.polyline.encodedPolyline,"
        "routes.optimizedIntermediateWaypointIndex"
    )

    if travel_mode == "DRIVE":

        field_mask += ",routes.travelAdvisory.speedReadingIntervals"

    headers["X-Goog-FieldMask"] = field_mask

    try:

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=30,
        )

        response.raise_for_status()

        st.session_state.google_api_call_count += 1

        data = response.json()

        routes = []

        for route in data.get("routes", []):

            distance_meters = route.get(
                "distanceMeters", 0
            )

            duration_str = route.get(
                "duration", "0s"
            )

            duration_seconds = float(
                duration_str.rstrip("s")
            )

            encoded_polyline = route.get(
                "polyline", {}
            ).get("encodedPolyline", "")

            geometry = (
                decode_polyline(encoded_polyline)
                if encoded_polyline
                else []
            )

            speed_intervals = route.get(
                "travelAdvisory", {}
            ).get("speedReadingIntervals", [])

            optimized_order = route.get(
                "optimizedIntermediateWaypointIndex"
            )

            routes.append(
                {
                    "distance_meters": distance_meters,
                    "distance_miles": distance_meters / 1609.344,
                    "distance_km": distance_meters / 1000,
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_seconds / 60,
                    "geometry": geometry,
                    "legs": [],
                    "speed_intervals": speed_intervals,
                    "optimized_order": optimized_order,
                }
            )

        return routes

    except Exception:

        # Graceful degradation: fall back to the free OSRM
        # router if Google Routes errors out.
        try:

            return get_osrm_fallback_routes(
                start_lat,
                start_lon,
                end_lat,
                end_lon,
                mode,
            )

        except Exception:

            return []


# ============================================================
# FREE OSRM FALLBACK ROUTING (used only if Google Routes fails)
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_osrm_fallback_routes(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    mode,
):

    profile_map = {
        "driving": "driving",
        "walking": "foot",
        "cycling": "bike",
    }

    profile = profile_map.get(mode, "driving")

    url = (
        "https://router.project-osrm.org/"
        f"route/v1/{profile}/"
        f"{start_lon},{start_lat};"
        f"{end_lon},{end_lat}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": "true",
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "MapExplorerV4/1.0"},
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            return []

        routes = []

        for route in data.get("routes", []):

            routes.append(
                {
                    "distance_meters": route.get("distance", 0),
                    "distance_miles": route.get("distance", 0) / 1609.344,
                    "distance_km": route.get("distance", 0) / 1000,
                    "duration_seconds": route.get("duration", 0),
                    "duration_minutes": route.get("duration", 0) / 60,
                    "geometry": [
                        [point[1], point[0]]
                        for point in route["geometry"]["coordinates"]
                    ],
                    "legs": [],
                    "speed_intervals": [],
                    "optimized_order": None,
                }
            )

        return routes

    except Exception:

        return []

# ============================================================
# NEARBY PLACES
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_nearby_places(
    lat,
    lon,
    category,
):

    # Google place "included types" per category. Google's
    # Nearby Search uses its business/POI database, which is
    # far more complete than OSM for real-world places (same
    # reason we switched destination search over earlier).
    google_type_map = {
        "🍕 Restaurants": ["restaurant"],
        "☕ Cafes": ["cafe"],
        "⛽ Gas Stations": ["gas_station"],
        "🏥 Hospitals": ["hospital"],
        "🏨 Hotels": ["lodging"],
        "🛒 Shops": ["store"],
        "🏫 Schools": ["school"],
        "🏦 Banks": ["bank"],
    }

    included_types = google_type_map.get(
        category,
        ["restaurant"],
    )

    if GOOGLE_MAPS_API_KEY:

        places = get_nearby_places_google(
            lat,
            lon,
            category,
            tuple(included_types),
        )

        if places:
            return places

    # Fall back to the free OSM/Overpass search if Google
    # is unavailable or returns nothing.
    return get_nearby_places_overpass(lat, lon, category)


def get_nearby_places_google(
    lat,
    lon,
    category,
    included_types,
):

    url = "https://places.googleapis.com/v1/places:searchNearby"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.formattedAddress,"
            "places.location"
        ),
    }

    body = {
        "includedTypes": list(included_types),
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lon,
                },
                "radius": 5000.0,
            }
        },
        "rankPreference": "DISTANCE",
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=15,
        )

        response.raise_for_status()

        st.session_state.google_api_call_count += 1

        data = response.json()

        places = []

        for place in data.get("places", []):

            location = place.get("location", {})

            place_lat = location.get("latitude")
            place_lon = location.get("longitude")

            if place_lat is None or place_lon is None:
                continue

            name = place.get(
                "displayName", {}
            ).get("text", "Unnamed place")

            places.append(
                {
                    "name": name,
                    "lat": place_lat,
                    "lon": place_lon,
                    "type": category,
                    "address": place.get("formattedAddress", ""),
                }
            )

        return places

    except Exception:

        return []


def get_nearby_places_overpass(
    lat,
    lon,
    category,
):

    queries = {

        "🍕 Restaurants":
            "amenity=restaurant",

        "☕ Cafes":
            "amenity=cafe",

        "⛽ Gas Stations":
            "amenity=fuel",

        "🏥 Hospitals":
            "amenity=hospital",

        "🏨 Hotels":
            "tourism=hotel",

        "🛒 Shops":
            "shop",

        "🏫 Schools":
            "amenity=school",

        "🏦 Banks":
            "amenity=bank",
    }

    query = queries.get(
        category,
        "amenity=restaurant",
    )

    overpass_query = f"""
    [out:json];

    (
        node[{query}]
        (around:5000,{lat},{lon});

        way[{query}]
        (around:5000,{lat},{lon});
    );

    out center;
    """

    headers = {
        "User-Agent":
            "MapExplorerV4/1.0"
    }

    try:

        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        places = []

        for element in data.get(
            "elements",
            []
        ):

            tags = element.get(
                "tags",
                {}
            )

            if element["type"] == "node":

                place_lat = element.get(
                    "lat"
                )

                place_lon = element.get(
                    "lon"
                )

            else:

                center = element.get(
                    "center",
                    {}
                )

                place_lat = center.get(
                    "lat"
                )

                place_lon = center.get(
                    "lon"
                )

            if (
                place_lat is None
                or place_lon is None
            ):
                continue

            places.append(
                {
                    "name":
                        tags.get(
                            "name",
                            "Unnamed place"
                        ),

                    "lat":
                        place_lat,

                    "lon":
                        place_lon,

                    "type":
                        category,
                }
            )

        return places[:40]

    except Exception:

        return []


# ============================================================
# FORMAT DURATION
# ============================================================

def format_duration(minutes):

    if minutes < 1:

        return "<1 min"

    if minutes < 60:

        return f"{round(minutes)} min"

    hours = int(
        minutes // 60
    )

    remaining = int(
        minutes % 60
    )

    if remaining == 0:

        return f"{hours} hr"

    return (
        f"{hours} hr "
        f"{remaining} min"
    )


# ============================================================
# FORMAT DISTANCE
# ============================================================

def format_distance(miles):

    if miles < 0.1:

        return (
            f"{miles * 5280:.0f} ft"
        )

    return f"{miles:.1f} mi"


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    "🗺️ Map Explorer V4"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Free routing • Automatic ETA • No API key required"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    toggle_col1, toggle_col2 = st.columns([3, 1])

    with toggle_col1:
        st.header("🔎 Search")

    with toggle_col2:

        dark_icon = "☀️" if st.session_state.dark_mode else "🌙"

        if st.button(dark_icon, key="dark_mode_toggle"):

            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    search_query = st.text_input(
        "Where do you want to go?",
        placeholder=(
            "New York City, Times Square..."
        ),
        key="search_query_input",
    )

    if search_query and len(search_query.strip()) >= 3:

        suggestions = get_autocomplete_suggestions(
            search_query,
            origin_lat=st.session_state.current_lat,
            origin_lon=st.session_state.current_lon,
        )

        if suggestions:

            for sugg_index, suggestion in enumerate(suggestions):

                if suggestion["distance_miles"] is not None:

                    label = (
                        f"💡 {suggestion['distance_miles']:.1f} mi — "
                        f"{suggestion['text']}"
                    )

                else:

                    label = f"💡 {suggestion['text']}"

                if st.button(
                    label,
                    key=f"autocomplete_{sugg_index}",
                    use_container_width=True,
                ):

                    with st.spinner("Searching..."):

                        results = search_places(
                            suggestion["text"],
                            origin_lat=st.session_state.current_lat,
                            origin_lon=st.session_state.current_lon,
                        )

                    st.session_state.search_results = results

                    recents = [
                        q for q in st.session_state.recent_searches
                        if q.lower() != suggestion["text"].lower()
                    ]

                    recents.insert(0, suggestion["text"])

                    st.session_state.recent_searches = recents[:5]

                    save_persisted_data()

                    st.rerun()

    if st.button(
        "🔍 Search",
        use_container_width=True,
    ):

        if search_query.strip():

            with st.spinner(
                "Searching..."
            ):

                results = search_places(
                    search_query,
                    origin_lat=st.session_state.current_lat,
                    origin_lon=st.session_state.current_lon,
                )

            if results:

                st.session_state.search_results = results

                # Track recent searches (most recent first,
                # deduplicated, capped at 5).
                recents = [
                    q for q in st.session_state.recent_searches
                    if q.lower() != search_query.strip().lower()
                ]

                recents.insert(0, search_query.strip())

                st.session_state.recent_searches = recents[:5]

                save_persisted_data()

            else:

                st.session_state.search_results = []

                st.error(
                    "Location not found. "
                    "Try a city, street address, "
                    "or landmark."
                )

        if st.session_state.last_search_debug:

            with st.expander("🔧 Search debug info"):

                for note in st.session_state.last_search_debug:

                    st.caption(note)

    if (
        st.session_state.recent_searches
        and not st.session_state.search_results
    ):

        with st.expander("🕘 Recent searches"):

            for index, recent_query in enumerate(
                st.session_state.recent_searches
            ):

                if st.button(
                    recent_query,
                    key=f"recent_{index}",
                    use_container_width=True,
                ):

                    with st.spinner("Searching..."):

                        results = search_places(
                            recent_query,
                            origin_lat=st.session_state.current_lat,
                            origin_lon=st.session_state.current_lon,
                        )

                    st.session_state.search_results = results
                    st.rerun()

    if st.session_state.search_results:

        st.write("**Select a location:**")

        for index, result in enumerate(
            st.session_state.search_results
        ):

            closest_badge = (
                " ⭐ CLOSEST"
                if index == 0
                and result["distance_miles"] is not None
                else ""
            )

            if result["distance_miles"] is not None:

                label = (
                    f"📍 {result['distance_miles']:.1f} mi{closest_badge} — "
                    f"{result['address']}"
                )

            else:

                label = f"📍 {result['address']}"

            if st.button(
                label,
                key=f"result_{index}",
                use_container_width=True,
            ):

                st.session_state.search_lat = result["lat"]
                st.session_state.search_lon = result["lon"]
                st.session_state.search_address = result["address"]

                st.session_state.search_results = []
                st.session_state.routes = []

                st.rerun()

    st.divider()

    st.header("📍 Your Location")

    location_tab = st.radio(
        "How to set your location",
        ["Auto-detect", "Type it in"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if location_tab == "Auto-detect":

        location = streamlit_geolocation()

        if location:

            lat = location.get(
                "latitude"
            )

            lon = location.get(
                "longitude"
            )

            if (
                lat is not None
                and lon is not None
            ):

                st.session_state.current_lat = lat
                st.session_state.current_lon = lon

                st.success(
                    "Location detected!"
                )

                st.caption(
                    f"{lat:.5f}, {lon:.5f}"
                )

    else:

        manual_location = st.text_input(
            "Enter your address or city",
            placeholder="Plainsboro, NJ",
            key="manual_location_input",
        )

        if st.button(
            "📍 Set Location",
            use_container_width=True,
        ):

            if manual_location.strip():

                with st.spinner("Finding that location..."):

                    manual_results = search_places(
                        manual_location.strip(),
                        limit=1,
                    )

                if manual_results:

                    st.session_state.current_lat = manual_results[0]["lat"]
                    st.session_state.current_lon = manual_results[0]["lon"]

                    st.success(
                        f"Location set: {manual_results[0]['address']}"
                    )

                else:

                    st.error(
                        "Couldn't find that location. "
                        "Try a more specific address or city."
                    )

        if st.session_state.current_lat is not None:

            st.caption(
                f"Current: {st.session_state.current_lat:.5f}, "
                f"{st.session_state.current_lon:.5f}"
            )

    st.divider()

    st.header("🚗 Travel Mode")

    mode_display = st.radio(
        "Choose transportation",
        [
            "🚗 Driving",
            "🚶 Walking",
            "🚴 Cycling",
        ],
    )

    if mode_display.startswith("🚗"):

        st.session_state.route_mode = (
            "driving"
        )

    elif mode_display.startswith("🚶"):

        st.session_state.route_mode = (
            "walking"
        )

    else:

        st.session_state.route_mode = (
            "cycling"
        )

    if st.button(
        "🛣️ Calculate Route",
        use_container_width=True,
    ):

        if (
            st.session_state.current_lat is None
            or st.session_state.search_lat is None
        ):

            st.warning(
                "First allow location access "
                "and search for a destination."
            )

        else:

            with st.spinner(
                "Finding the best route..."
            ):

                routes = get_osrm_routes(
                    st.session_state.current_lat,
                    st.session_state.current_lon,
                    st.session_state.search_lat,
                    st.session_state.search_lon,
                    st.session_state.route_mode,
                )

            if routes:

                st.session_state.routes = (
                    routes
                )

                st.success(
                    f"{len(routes)} route(s) found!"
                )

            else:

                st.error(
                    "No route could be found."
                )

    st.divider()

    st.header("⏰ Arrive By")

    use_arrive_by = st.toggle(
        "Set a target arrival time",
        value=st.session_state.arrive_by is not None,
    )

    if use_arrive_by:

        arrive_by_time = st.time_input(
            "Arrive by",
            value=(
                st.session_state.arrive_by
                if st.session_state.arrive_by
                else datetime.now().time()
            ),
        )

        st.session_state.arrive_by = arrive_by_time

    else:

        st.session_state.arrive_by = None

    if st.session_state.search_address:

        st.divider()

        st.header("🔗 Share")

        share_url = (
            "?dest_lat="
            f"{st.session_state.search_lat}"
            "&dest_lon="
            f"{st.session_state.search_lon}"
            "&dest_name="
            f"{st.session_state.search_address}"
        )

        st.text_input(
            "Shareable link (append to your app's base URL)",
            value=share_url,
            key="share_url_display",
        )

    st.divider()

    st.header("📍 Multi-Stop Route")

    if st.session_state.search_lat is not None:

        if st.button(
            "➕ Add current destination as a stop",
            use_container_width=True,
        ):

            st.session_state.waypoints.append(
                {
                    "lat": st.session_state.search_lat,
                    "lon": st.session_state.search_lon,
                    "name": st.session_state.search_address,
                }
            )

            st.rerun()

    if st.session_state.last_removed_waypoint is not None:

        undo_col1, undo_col2 = st.columns([4, 1])

        with undo_col1:

            st.caption(
                f"Removed \"{st.session_state.last_removed_waypoint['name']}\""
            )

        with undo_col2:

            if st.button("↩️ Undo", key="undo_waypoint"):

                st.session_state.waypoints.append(
                    st.session_state.last_removed_waypoint
                )

                st.session_state.last_removed_waypoint = None

                st.rerun()

    if st.session_state.waypoints:

        st.caption(
            f"{len(st.session_state.waypoints)} stop(s), "
            "visited in this order:"
        )

        for wp_index, waypoint in enumerate(
            st.session_state.waypoints
        ):

            wp_col1, wp_col2 = st.columns([5, 1])

            with wp_col1:

                st.write(
                    f"{wp_index + 1}. {waypoint['name']}"
                )

            with wp_col2:

                if st.button(
                    "✕",
                    key=f"remove_waypoint_{wp_index}",
                ):

                    st.session_state.last_removed_waypoint = (
                        st.session_state.waypoints.pop(wp_index)
                    )
                    st.rerun()

        st.session_state.optimize_stop_order = st.checkbox(
            "🧭 Optimize stop order (shortest total trip)",
            value=st.session_state.optimize_stop_order,
        )

        if (
            st.session_state.current_lat is not None
            and st.session_state.search_lat is not None
        ):

            if st.button(
                "🛣️ Route through all stops",
                use_container_width=True,
            ):

                with st.spinner(
                    "Finding the best multi-stop route..."
                ):

                    multi_routes = get_osrm_routes(
                        st.session_state.current_lat,
                        st.session_state.current_lon,
                        st.session_state.search_lat,
                        st.session_state.search_lon,
                        st.session_state.route_mode,
                        waypoints=st.session_state.waypoints,
                        optimize_order=st.session_state.optimize_stop_order,
                    )

                if multi_routes:

                    st.session_state.routes = multi_routes

                    st.success("Multi-stop route found!")

                else:

                    st.error(
                        "Couldn't find a route through all stops."
                    )

        if st.button(
            "🗑️ Clear all stops",
            use_container_width=True,
        ):

            st.session_state.waypoints = []
            st.rerun()

    st.divider()

    st.header("🔁 Route Presets")

    st.caption(
        "Save a destination as a one-tap preset, e.g. "
        "\"Commute to Work.\""
    )

    if st.session_state.search_lat is not None:

        preset_name = st.text_input(
            "Preset name",
            placeholder="Commute to Work",
            key="preset_name_input",
        )

        if st.button(
            "💾 Save current destination as preset",
            use_container_width=True,
        ):

            if preset_name.strip():

                st.session_state.route_presets.append(
                    {
                        "name": preset_name.strip(),
                        "lat": st.session_state.search_lat,
                        "lon": st.session_state.search_lon,
                        "address": st.session_state.search_address,
                    }
                )

                save_persisted_data()

                st.success(f"Saved preset \"{preset_name.strip()}\"")

            else:

                st.warning("Give the preset a name first.")

    if st.session_state.route_presets:

        for preset_index, preset in enumerate(
            st.session_state.route_presets
        ):

            preset_col1, preset_col2, preset_col3 = st.columns(
                [3, 1.3, 1]
            )

            with preset_col1:

                st.write(f"📌 {preset['name']}")

            with preset_col2:

                if st.button(
                    "🛣️ Go",
                    key=f"go_preset_{preset_index}",
                ):

                    st.session_state.search_lat = preset["lat"]
                    st.session_state.search_lon = preset["lon"]
                    st.session_state.search_address = preset["address"]

                    st.session_state.routes = []

                    if st.session_state.current_lat is not None:

                        with st.spinner("Finding the best route..."):

                            preset_routes = get_osrm_routes(
                                st.session_state.current_lat,
                                st.session_state.current_lon,
                                preset["lat"],
                                preset["lon"],
                                st.session_state.route_mode,
                            )

                        st.session_state.routes = preset_routes

                    st.rerun()

            with preset_col3:

                if st.button(
                    "✕",
                    key=f"remove_preset_{preset_index}",
                ):

                    st.session_state.route_presets.pop(preset_index)
                    save_persisted_data()
                    st.rerun()

    st.divider()

    st.header("🗺️ Map Style")

    map_style = st.selectbox(
        "Choose map",
        [
            "OpenStreetMap",
            "CartoDB positron",
            "CartoDB dark_matter",
        ],
    )

    st.session_state.map_style = (
        map_style
    )

    st.divider()

    st.header("🏪 Nearby Places")

    nearby_category = st.selectbox(
        "Find nearby",
        [
            "🍕 Restaurants",
            "☕ Cafes",
            "⛽ Gas Stations",
            "🏥 Hospitals",
            "🏨 Hotels",
            "🛒 Shops",
            "🏫 Schools",
            "🏦 Banks",
        ],
    )

    if st.button(
        "🔎 Find Nearby",
        use_container_width=True,
    ):

        target_lat = (
            st.session_state.current_lat
            if st.session_state.current_lat
            is not None
            else st.session_state.search_lat
        )

        target_lon = (
            st.session_state.current_lon
            if st.session_state.current_lon
            is not None
            else st.session_state.search_lon
        )

        if target_lat is not None:

            with st.spinner(
                "Finding nearby places..."
            ):

                st.session_state.nearby_places = (
                    get_nearby_places(
                        target_lat,
                        target_lon,
                        nearby_category,
                    )
                )

        else:

            st.warning(
                "Search for a location first."
            )


# ============================================================
# MAP CENTER
# ============================================================

if st.session_state.search_lat is not None:

    center_lat = (
        st.session_state.search_lat
    )

    center_lon = (
        st.session_state.search_lon
    )

elif st.session_state.current_lat is not None:

    center_lat = (
        st.session_state.current_lat
    )

    center_lon = (
        st.session_state.current_lon
    )

else:

    # Initial location
    # Princeton Junction, NJ

    center_lat = 40.3173
    center_lon = -74.6199


# ============================================================
# CREATE MAP
# ============================================================

m = folium.Map(
    location=[
        center_lat,
        center_lon,
    ],
    zoom_start=13,
    control_scale=True,
    tiles=None,
)


# ============================================================
# MAP TILE
# ============================================================

folium.TileLayer(
    tiles=st.session_state.map_style,
    name="Map",
).add_to(m)


# ============================================================
# CURRENT LOCATION
# ============================================================

if (
    st.session_state.current_lat is not None
    and st.session_state.current_lon is not None
):

    folium.Marker(
        [
            st.session_state.current_lat,
            st.session_state.current_lon,
        ],
        tooltip="📍 You are here",
        popup=(
            "<b>Your current location</b>"
        ),
        icon=folium.Icon(
            color="blue",
            icon="user",
            prefix="fa",
        ),
    ).add_to(m)


# ============================================================
# DESTINATION MARKER
# ============================================================

if st.session_state.search_lat is not None:

    folium.Marker(
        [
            st.session_state.search_lat,
            st.session_state.search_lon,
        ],
        tooltip="📍 Destination",
        popup=(
            f"<b>Destination</b><br>"
            f"{st.session_state.search_address}"
        ),
        icon=folium.Icon(
            color="red",
            icon="flag",
            prefix="fa",
        ),
    ).add_to(m)


# ============================================================
# NEARBY PLACES
# ============================================================

for place in st.session_state.nearby_places:

    folium.Marker(
        [
            place["lat"],
            place["lon"],
        ],
        tooltip=place["name"],
        popup=(
            f"<b>{place['name']}</b>"
            f"<br>{place['type']}"
        ),
        icon=folium.Icon(
            color="green",
            icon="map-marker",
            prefix="fa",
        ),
    ).add_to(m)


# ============================================================
# DRAW ROUTES
# ============================================================

if st.session_state.routes:

    for index, route in enumerate(
        st.session_state.routes
    ):

        if not route["geometry"]:
            continue

        if index == 0:

            # Traffic-aware coloring on the primary route:
            # Google's speedReadingIntervals classify segments
            # of the polyline as NORMAL / SLOW / TRAFFIC_JAM.
            speed_intervals = route.get("speed_intervals", [])

            speed_color_map = {
                "NORMAL": "#22c55e",
                "SLOW": "#f59e0b",
                "TRAFFIC_JAM": "#ef4444",
            }

            if speed_intervals:

                geometry = route["geometry"]

                for interval in speed_intervals:

                    start_i = interval.get("startPolylinePointIndex", 0)
                    end_i = interval.get(
                        "endPolylinePointIndex", len(geometry) - 1
                    )
                    speed_label = interval.get("speed", "NORMAL")

                    segment = geometry[start_i:end_i + 1]

                    if len(segment) < 2:
                        continue

                    folium.PolyLine(
                        segment,
                        color=speed_color_map.get(speed_label, "#4285F4"),
                        weight=8,
                        opacity=0.9,
                        tooltip=f"⭐ Recommended route ({speed_label.title()})",
                    ).add_to(m)

            else:

                folium.PolyLine(
                    route["geometry"],
                    color="#4285F4",
                    weight=8,
                    opacity=0.90,
                    tooltip="⭐ Recommended route",
                ).add_to(m)

        else:

            folium.PolyLine(
                route["geometry"],
                color="#7b8794",
                weight=5,
                opacity=0.50,
                tooltip=f"Alternative route {index + 1}",
            ).add_to(m)

    main_route = (
        st.session_state.routes[0]
    )

    if main_route["geometry"]:

        m.fit_bounds(
            main_route["geometry"]
        )


# ============================================================
# MAP LAYER CONTROL
# ============================================================

folium.LayerControl().add_to(m)


# ============================================================
# DISPLAY MAP
# ============================================================

map_data = st_folium(
    m,
    width=None,
    height=650,
    returned_objects=[
        "last_clicked"
    ],
)


# ============================================================
# MAP CLICK
# ============================================================

if map_data:

    clicked = map_data.get(
        "last_clicked"
    )

    if clicked:

        st.session_state.map_click = (
            clicked["lat"],
            clicked["lng"],
        )


# ============================================================
# ROUTE / ETA
# ============================================================

if st.session_state.routes:

    # Silently re-fetch the route on each autorefresh so the
    # ETA reflects current traffic conditions, not just a
    # stale snapshot from when the route was first calculated.
    # get_osrm_routes is cached for 30s (matching the
    # autorefresh interval), so this doesn't add extra calls
    # beyond one per refresh tick.
    if (
        st.session_state.current_lat is not None
        and st.session_state.search_lat is not None
    ):

        try:

            refreshed_routes = get_osrm_routes(
                st.session_state.current_lat,
                st.session_state.current_lon,
                st.session_state.search_lat,
                st.session_state.search_lon,
                st.session_state.route_mode,
                waypoints=(
                    st.session_state.waypoints
                    if st.session_state.waypoints
                    else None
                ),
            )

            if refreshed_routes:

                st.session_state.routes = refreshed_routes

        except Exception:

            # Keep showing the last known route rather than
            # breaking the page if a background refresh fails.
            pass

    main_route = (
        st.session_state.routes[0]
    )

    duration_minutes = (
        main_route[
            "duration_minutes"
        ]
    )

    distance_miles = (
        main_route[
            "distance_miles"
        ]
    )

    distance_km = (
        main_route[
            "distance_km"
        ]
    )

    duration_text = format_duration(
        duration_minutes
    )

    distance_text = format_distance(
        distance_miles
    )

    destination_timezone_name = get_timezone(
        st.session_state.search_lat,
        st.session_state.search_lon,
    ) or "UTC"

    eta_card_bg = "#1e293b" if st.session_state.dark_mode else "white"
    eta_text_color = "#f1f5f9" if st.session_state.dark_mode else "#1a1a1a"

    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    font-family: Arial, sans-serif;
                }}
                .eta-card {{
                    background: {eta_card_bg};
                    padding: 24px;
                    border-radius: 18px;
                    box-shadow: 0 4px 18px rgba(0,0,0,0.08);
                    text-align: center;
                }}
                .eta-time {{
                    font-size: 42px;
                    font-weight: 800;
                    color: {eta_text_color};
                }}
                .eta-time.skeleton {{
                    color: transparent;
                    background: linear-gradient(
                        90deg,
                        rgba(150,150,150,0.15) 25%,
                        rgba(150,150,150,0.3) 37%,
                        rgba(150,150,150,0.15) 63%
                    );
                    background-size: 400% 100%;
                    border-radius: 8px;
                    animation: skeleton-pulse 1.4s ease infinite;
                }}
                @keyframes skeleton-pulse {{
                    0% {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}
            </style>
        </head>
        <body>
            <div class="eta-card">
                <div class="eta-time skeleton" id="eta-time">
                    --:-- --
                </div>
            </div>
            <script>
                const durationSeconds = {main_route["duration_seconds"]};
                const destinationTimeZone = "{destination_timezone_name}";

                function updateEta() {{
                    const now = new Date();
                    const etaMs = now.getTime() + durationSeconds * 1000;
                    const etaDate = new Date(etaMs);

                    const timeOptions = {{
                        timeZone: destinationTimeZone,
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true
                    }};

                    const etaElement = document.getElementById("eta-time");

                    etaElement.textContent =
                        new Intl.DateTimeFormat("en-US", timeOptions).format(etaDate);

                    etaElement.classList.remove("skeleton");
                }}

                updateEta();
                setInterval(updateEta, 1000);
            </script>
        </body>
        </html>
        """,
        height=130,
    )

    # Keep a Python-side ETA value too, for the metrics below
    # and anything else that reads it (won't tick live, but
    # stays accurate as of each rerun).
    destination_now = (
        get_destination_time(
            st.session_state.search_lat,
            st.session_state.search_lon,
        )
    )

    eta = (
        destination_now
        + timedelta(
            seconds=main_route[
                "duration_seconds"
            ]
        )
    )

    # --------------------------------------------------------
    # DESTINATION WEATHER
    # --------------------------------------------------------

    weather = get_destination_weather(
        st.session_state.search_lat,
        st.session_state.search_lon,
    )

    if weather:

        st.caption(
            f"{weather['icon']} {weather['temperature']}°F, "
            f"{weather['label']} at destination"
        )

    # --------------------------------------------------------
    # LEAVE BY (if the user set a target arrival time)
    # --------------------------------------------------------

    leave_by_text = None

    if st.session_state.arrive_by is not None:

        target_arrival = datetime.combine(
            destination_now.date(),
            st.session_state.arrive_by,
            tzinfo=destination_now.tzinfo,
        )

        # If that time has already passed today, assume they
        # mean tomorrow.
        if target_arrival < destination_now:

            target_arrival += timedelta(days=1)

        leave_by = target_arrival - timedelta(
            seconds=main_route["duration_seconds"]
        )

        leave_by_text = leave_by.strftime("%I:%M %p")

        if leave_by < destination_now:

            st.warning(
                f"⚠️ You should have already left to make your "
                f"{target_arrival.strftime('%I:%M %p')} target — "
                f"this trip takes {duration_text}."
            )

        else:

            st.info(
                f"🚗 Leave by **{leave_by_text}** to arrive by "
                f"{target_arrival.strftime('%I:%M %p')}."
            )

    st.write("")

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "📏 Distance",
            distance_text,
        )

    with col2:

        st.metric(
            "⏱️ Travel Time",
            duration_text,
        )

    with col3:

        st.metric(
            "🕐 ETA",
            eta.strftime("%I:%M %p"),
        )

    with col4:

        st.metric(
            "🌎 Distance",
            f"{distance_km:.1f} km",
        )

    timezone_name = get_timezone(
        st.session_state.search_lat,
        st.session_state.search_lon,
    )

    traffic_label = (
        "🚦 Traffic-Aware ETA"
        if st.session_state.route_mode == "driving"
        else "🟢 Road-network ETA"
    )

    st.markdown(
        f"""
        <div class="traffic-normal">

        {traffic_label}

        <br><br>

        Estimated driving time:
        <b>{duration_text}</b>

        <br>

        Estimated arrival:
        <b>{eta.strftime("%I:%M %p")}</b>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if timezone_name:

        st.caption(
            f"🕐 Destination timezone: "
            f"{timezone_name}"
        )

    st.caption(
        "ETA clock ticks live every second. "
        "Route & traffic conditions refresh every 30 seconds."
    )

    if len(
        st.session_state.routes
    ) > 1:

        st.divider()

        st.subheader(
            "🛣️ Route Options"
        )

        # Quick visual comparison of alternatives before the
        # detail cards.
        chart_labels = [
            "⭐ Recommended" if i == 0 else f"Route {i + 1}"
            for i in range(len(st.session_state.routes))
        ]

        chart_minutes = [
            round(r["duration_minutes"], 1)
            for r in st.session_state.routes
        ]

        chart_distance = [
            round(r["distance_miles"], 1)
            for r in st.session_state.routes
        ]

        chart_data = {
            "Route": chart_labels,
            "Minutes": chart_minutes,
            "Miles": chart_distance,
        }

        st.bar_chart(
            chart_data,
            x="Route",
            y="Minutes",
            height=200,
        )

        for index, route in enumerate(
            st.session_state.routes
        ):

            route_time = format_duration(
                route[
                    "duration_minutes"
                ]
            )

            route_distance = format_distance(
                route[
                    "distance_miles"
                ]
            )

            if index == 0:

                label = (
                    "⭐ Recommended"
                )

            else:

                label = (
                    f"Route {index + 1}"
                )

            st.markdown(
                f"""
                <div class="route-card">

                <b>{label}</b>

                <br><br>

                🚗 {route_time}

                &nbsp;&nbsp;•&nbsp;&nbsp;

                📏 {route_distance}

                </div>
                """,
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------
    # ELEVATION PROFILE (useful for walking/cycling especially)
    # --------------------------------------------------------

    if (
        st.session_state.route_mode in ("walking", "cycling")
        and main_route["geometry"]
    ):

        st.divider()

        st.subheader("⛰️ Elevation Profile")

        with st.spinner("Loading elevation data..."):

            elevation_points = get_elevation_profile(
                tuple(
                    tuple(pt)
                    for pt in main_route["geometry"][::max(
                        1, len(main_route["geometry"]) // 30
                    )]
                )
            )

        if elevation_points:

            st.line_chart(
                {"Elevation (ft)": elevation_points},
                height=180,
            )

        else:

            st.caption(
                "Elevation data unavailable for this route."
            )


# ============================================================
# SELECTED LOCATION
# ============================================================

if st.session_state.map_click:

    clicked_lat, clicked_lon = (
        st.session_state.map_click
    )

    st.divider()

    st.subheader(
        "📌 Selected Location"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Latitude",
            f"{clicked_lat:.6f}",
        )

    with col2:

        st.metric(
            "Longitude",
            f"{clicked_lon:.6f}",
        )

    if st.button(
        "📍 Find Address",
    ):

        with st.spinner(
            "Finding address..."
        ):

            address = reverse_geocode(
                clicked_lat,
                clicked_lon,
            )

        if address:

            st.success(
                address
            )

        else:

            st.warning(
                "Address not found."
            )


# ============================================================
# DESTINATION
# ============================================================

if st.session_state.search_address:

    st.divider()

    st.subheader(
        "📍 Destination"
    )

    st.write(
        st.session_state.search_address
    )

    if st.button(
        "⭐ Save Place",
    ):

        favorite = {
            "name":
                st.session_state.search_address,

            "lat":
                st.session_state.search_lat,

            "lon":
                st.session_state.search_lon,
        }

        already_saved = any(
            place["lat"]
            == favorite["lat"]
            and
            place["lon"]
            == favorite["lon"]
            for place
            in st.session_state.favorites
        )

        if not already_saved:

            st.session_state.favorites.append(
                favorite
            )

            save_persisted_data()

            st.success(
                "Place saved!"
            )

        else:

            st.info(
                "Already saved."
            )


# ============================================================
# FAVORITES
# ============================================================

if st.session_state.favorites:

    st.divider()

    st.subheader(
        "⭐ Saved Places"
    )

    if st.session_state.last_removed_favorite is not None:

        undo_fav_col1, undo_fav_col2 = st.columns([4, 1])

        with undo_fav_col1:

            st.caption(
                f"Removed \"{st.session_state.last_removed_favorite['name']}\""
            )

        with undo_fav_col2:

            if st.button("↩️ Undo", key="undo_favorite"):

                st.session_state.favorites.append(
                    st.session_state.last_removed_favorite
                )

                st.session_state.last_removed_favorite = None

                save_persisted_data()

                st.rerun()

    for index, favorite in enumerate(
        st.session_state.favorites
    ):

        col1, col2, col3 = st.columns(
            [5, 1.3, 1]
        )

        with col1:

            st.write(
                f"📍 {favorite['name']}"
            )

        with col2:

            if st.button(
                "🛣️ Route",
                key=f"route_to_fav_{index}",
            ):

                st.session_state.search_lat = favorite["lat"]
                st.session_state.search_lon = favorite["lon"]
                st.session_state.search_address = favorite["name"]

                st.session_state.routes = []

                if st.session_state.current_lat is not None:

                    with st.spinner("Finding the best route..."):

                        auto_routes = get_osrm_routes(
                            st.session_state.current_lat,
                            st.session_state.current_lon,
                            favorite["lat"],
                            favorite["lon"],
                            st.session_state.route_mode,
                        )

                    st.session_state.routes = auto_routes

                st.rerun()

        with col3:

            if st.button(
                "✕",
                key=f"remove_{index}",
            ):

                st.session_state.last_removed_favorite = (
                    st.session_state.favorites.pop(index)
                )

                save_persisted_data()

                st.rerun()


# ============================================================
# NEARBY PLACES
# ============================================================

if st.session_state.nearby_places:

    st.divider()

    st.subheader(
        "🏪 Nearby Places"
    )

    for place in (
        st.session_state.nearby_places[:20]
    ):

        st.markdown(
            f"""
            <div class="place-card">

                <b>📍 {place['name']}</b>

                <br>

                <span style="color:#687080;">
                    {place['type']}
                </span>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🗺️ Map Explorer V4 • "
    "Routing & search by Google Maps Platform • "
    "Nearby places by OpenStreetMap • "
    "Map data © OpenStreetMap contributors"
)
