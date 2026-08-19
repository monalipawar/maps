import os
import re
import requests
import streamlit as st
import folium

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder


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
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background: #f5f7fb;
    }

    .title {
        font-size: 44px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .subtitle {
        color: #687080;
        font-size: 17px;
        margin-bottom: 20px;
    }

    .eta-card {
        background: white;
        padding: 24px;
        border-radius: 18px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.08);
        margin-top: 15px;
        text-align: center;
    }

    .eta-time {
        font-size: 40px;
        font-weight: 800;
    }

    .eta-label {
        color: #687080;
        font-size: 14px;
    }

    .traffic-card {
        background: white;
        padding: 18px;
        border-radius: 16px;
        box-shadow: 0 3px 14px rgba(0,0,0,0.07);
        margin-top: 12px;
    }

    .route-card {
        background: white;
        padding: 18px;
        border-radius: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }

    .place-card {
        background: white;
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }

    div[data-testid="stMetric"] {
        background: white;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

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

    "routes": [],

    "favorites": [],

    "map_click": None,

    "nearby_places": [],

    "map_style": "OpenStreetMap",

    "traffic_mode": True,
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SERVICES
# ============================================================

geolocator = Nominatim(
    user_agent="map-explorer-v4"
)

timezone_finder = TimezoneFinder()


# ============================================================
# GOOGLE ROUTES API KEY
# ============================================================

def get_google_api_key():

    # Streamlit Cloud / secrets.toml
    try:

        key = st.secrets.get(
            "GOOGLE_ROUTES_API_KEY"
        )

        if key:
            return key

    except Exception:
        pass

    # Environment variable
    key = os.environ.get(
        "GOOGLE_ROUTES_API_KEY"
    )

    if key:
        return key

    return None


# ============================================================
# SEARCH
# ============================================================

def search_place(query):

    try:

        location = geolocator.geocode(
            query,
            timeout=10,
            addressdetails=True,
            exactly_one=True,
        )

        if location:

            return {
                "lat": location.latitude,
                "lon": location.longitude,
                "address": location.address,
            }

    except Exception:
        pass

    return None


# ============================================================
# REVERSE GEOCODING
# ============================================================

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
        pass

    return None


# ============================================================
# TIMEZONE
# ============================================================

def get_timezone(lat, lon):

    try:

        return timezone_finder.timezone_at(
            lat=lat,
            lng=lon,
        )

    except Exception:

        return None


# ============================================================
# PARSE GOOGLE DURATION
# ============================================================

def parse_google_duration(value):

    if not value:
        return 0

    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)s",
        value,
    )

    if match:
        return float(
            match.group(1)
        )

    return 0


# ============================================================
# GOOGLE POLYLINE DECODER
# ============================================================

def decode_polyline(encoded):

    """
    Decode Google's encoded polyline.

    Returns:
        [[lat, lon], [lat, lon], ...]
    """

    coordinates = []

    index = 0
    lat = 0
    lon = 0

    while index < len(encoded):

        # Latitude
        result = 0
        shift = 0

        while True:

            byte = ord(
                encoded[index]
            ) - 63

            index += 1

            result |= (
                (byte & 0x1F)
                << shift
            )

            shift += 5

            if byte < 0x20:
                break

        if result & 1:

            lat_change = ~(
                result >> 1
            )

        else:

            lat_change = (
                result >> 1
            )

        lat += lat_change

        # Longitude
        result = 0
        shift = 0

        while True:

            byte = ord(
                encoded[index]
            ) - 63

            index += 1

            result |= (
                (byte & 0x1F)
                << shift
            )

            shift += 5

            if byte < 0x20:
                break

        if result & 1:

            lon_change = ~(
                result >> 1
            )

        else:

            lon_change = (
                result >> 1
            )

        lon += lon_change

        coordinates.append(
            [
                lat / 100000.0,
                lon / 100000.0,
            ]
        )

    return coordinates


# ============================================================
# GOOGLE ROUTES API
# ============================================================

def get_google_routes(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
):

    api_key = get_google_api_key()

    if not api_key:
        return {
            "error": (
                "Google Routes API key not found."
            )
        }

    url = (
        "https://routes.googleapis.com/"
        "directions/v2:computeRoutes"
    )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.staticDuration,"
            "routes.distanceMeters,"
            "routes.polyline.encodedPolyline,"
            "routes.routeLabels,"
            "routes.description"
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

        "travelMode": "DRIVE",

        "routingPreference":
            "TRAFFIC_AWARE_OPTIMAL",

        "computeAlternativeRoutes": True,

        "languageCode": "en-US",

        "units": "IMPERIAL",
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=45,
        )

        if response.status_code != 200:

            try:
                error_data = response.json()
            except Exception:
                error_data = response.text

            return {
                "error": (
                    f"Google Routes API error "
                    f"{response.status_code}: "
                    f"{error_data}"
                )
            }

        data = response.json()

        routes = []

        for route in data.get(
            "routes",
            []
        ):

            traffic_seconds = (
                parse_google_duration(
                    route.get(
                        "duration"
                    )
                )
            )

            normal_seconds = (
                parse_google_duration(
                    route.get(
                        "staticDuration"
                    )
                )
            )

            distance_meters = (
                route.get(
                    "distanceMeters",
                    0
                )
            )

            encoded_polyline = (
                route
                .get("polyline", {})
                .get(
                    "encodedPolyline"
                )
            )

            geometry = []

            if encoded_polyline:

                geometry = decode_polyline(
                    encoded_polyline
                )

            traffic_delay = max(
                0,
                traffic_seconds
                - normal_seconds,
            )

            routes.append(
                {
                    "traffic_seconds":
                        traffic_seconds,

                    "normal_seconds":
                        normal_seconds,

                    "traffic_minutes":
                        traffic_seconds / 60,

                    "normal_minutes":
                        normal_seconds / 60,

                    "traffic_delay_minutes":
                        traffic_delay / 60,

                    "distance_miles":
                        distance_meters / 1609.344,

                    "distance_km":
                        distance_meters / 1000,

                    "geometry":
                        geometry,

                    "labels":
                        route.get(
                            "routeLabels",
                            []
                        ),

                    "description":
                        route.get(
                            "description",
                            ""
                        ),
                }
            )

        return {
            "routes": routes
        }

    except requests.RequestException as exc:

        return {
            "error": (
                f"Network error: {exc}"
            )
        }

    except Exception as exc:

        return {
            "error": (
                f"Unexpected error: {exc}"
            )
        }


# ============================================================
# TRAFFIC LABEL
# ============================================================

def traffic_label(delay_minutes):

    if delay_minutes <= 2:

        return (
            "🟢 Normal traffic",
            "Normal"
        )

    if delay_minutes <= 8:

        return (
            "🟠 Moderate traffic",
            "Moderate"
        )

    return (
        "🔴 Heavy traffic",
        "Heavy"
    )


# ============================================================
# NEARBY PLACES
# ============================================================

def get_nearby_places(
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
        node[{query}](around:5000,{lat},{lon});

        way[{query}](around:5000,{lat},{lon});
    );

    out center;
    """

    try:

        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            timeout=30,
        )

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
# HEADER
# ============================================================

st.markdown(
    '<div class="title">'
    "🗺️ Map Explorer V4"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Traffic-aware directions and real-time ETA"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("🔎 Search")

    search_query = st.text_input(
        "Where do you want to go?",
        placeholder="New York City...",
    )

    if st.button(
        "🔍 Search",
        use_container_width=True,
    ):

        if search_query.strip():

            with st.spinner(
                "Searching..."
            ):

                result = search_place(
                    search_query
                )

            if result:

                st.session_state.search_lat = (
                    result["lat"]
                )

                st.session_state.search_lon = (
                    result["lon"]
                )

                st.session_state.search_address = (
                    result["address"]
                )

                st.session_state.routes = []

                st.success(
                    "Destination found!"
                )

            else:

                st.error(
                    "Location not found."
                )

    st.divider()

    st.header("📍 Your Location")

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

            st.session_state.current_lat = (
                lat
            )

            st.session_state.current_lon = (
                lon
            )

            st.success(
                "Location detected!"
            )

            st.caption(
                f"{lat:.5f}, {lon:.5f}"
            )

    st.divider()

    st.header("🚦 Traffic Routing")

    traffic_enabled = st.checkbox(
        "Use live traffic",
        value=True,
    )

    st.session_state.traffic_mode = (
        traffic_enabled
    )

    if traffic_enabled:

        st.caption(
            "Using Google's "
            "TRAFFIC_AWARE_OPTIMAL routing."
        )

    else:

        st.caption(
            "Traffic-aware routing is disabled."
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
                "Allow location access and "
                "search for a destination."
            )

        else:

            api_key = get_google_api_key()

            if not api_key:

                st.error(
                    "Google Routes API key "
                    "is not configured."
                )

            else:

                with st.spinner(
                    "Calculating traffic-aware route..."
                ):

                    result = get_google_routes(
                        st.session_state.current_lat,
                        st.session_state.current_lon,
                        st.session_state.search_lat,
                        st.session_state.search_lon,
                    )

                if result.get("error"):

                    st.error(
                        result["error"]
                    )

                else:

                    st.session_state.routes = (
                        result["routes"]
                    )

                    if st.session_state.routes:

                        st.success(
                            f"{len(st.session_state.routes)} "
                            "route(s) found."
                        )

                    else:

                        st.warning(
                            "No route found."
                        )

    st.divider()

    st.header("🗺️ Map Style")

    map_style = st.selectbox(
        "Map",
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
            if st.session_state.current_lat is not None
            else st.session_state.search_lat
        )

        target_lon = (
            st.session_state.current_lon
            if st.session_state.current_lon is not None
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
        popup="Your current location",
        icon=folium.Icon(
            color="blue",
            icon="user",
            prefix="fa",
        ),
    ).add_to(m)


# ============================================================
# DESTINATION
# ============================================================

if st.session_state.search_lat is not None:

    folium.Marker(
        [
            st.session_state.search_lat,
            st.session_state.search_lon,
        ],
        tooltip="📍 Destination",
        popup=st.session_state.search_address,
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
# DRAW GOOGLE ROUTES
# ============================================================

if st.session_state.routes:

    for index, route in enumerate(
        st.session_state.routes
    ):

        geometry = route["geometry"]

        if not geometry:
            continue

        # Main route
        if index == 0:

            route_color = "#4285F4"
            route_weight = 8
            route_opacity = 0.90

        else:

            route_color = "#7b8794"
            route_weight = 5
            route_opacity = 0.55

        folium.PolyLine(
            geometry,
            color=route_color,
            weight=route_weight,
            opacity=route_opacity,
            tooltip=(
                "Recommended route"
                if index == 0
                else f"Alternative route {index + 1}"
            ),
        ).add_to(m)

    # Fit to recommended route

    main_geometry = (
        st.session_state.routes[0]["geometry"]
    )

    if main_geometry:

        m.fit_bounds(
            main_geometry
        )


# ============================================================
# LAYER CONTROL
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
        "last_clicked",
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
# TRAFFIC ETA
# ============================================================

if st.session_state.routes:

    main_route = (
        st.session_state.routes[0]
    )

    traffic_minutes = (
        main_route[
            "traffic_minutes"
        ]
    )

    normal_minutes = (
        main_route[
            "normal_minutes"
        ]
    )

    delay_minutes = (
        main_route[
            "traffic_delay_minutes"
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

    # --------------------------------------------------------
    # Destination timezone
    # --------------------------------------------------------

    destination_timezone = (
        get_timezone(
            st.session_state.search_lat,
            st.session_state.search_lon,
        )
    )

    if destination_timezone:

        try:

            now_destination = datetime.now(
                ZoneInfo(
                    destination_timezone
                )
            )

        except Exception:

            now_destination = datetime.now()

    else:

        now_destination = datetime.now()

    # --------------------------------------------------------
    # ETA
    # --------------------------------------------------------

    eta = (
        now_destination
        + timedelta(
            minutes=traffic_minutes
        )
    )

    # --------------------------------------------------------
    # Duration text
    # --------------------------------------------------------

    if traffic_minutes < 60:

        traffic_text = (
            f"{traffic_minutes:.0f} min"
        )

    else:

        hours = int(
            traffic_minutes // 60
        )

        minutes = int(
            traffic_minutes % 60
        )

        traffic_text = (
            f"{hours}h {minutes}m"
        )

    if normal_minutes < 60:

        normal_text = (
            f"{normal_minutes:.0f} min"
        )

    else:

        hours = int(
            normal_minutes // 60
        )

        minutes = int(
            normal_minutes % 60
        )

        normal_text = (
            f"{hours}h {minutes}m"
        )

    traffic_text_label, _ = (
        traffic_label(
            delay_minutes
        )
    )

    # --------------------------------------------------------
    # ETA CARD
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="eta-card">

            <div class="eta-label">
                🚗 TRAFFIC-AWARE ETA
            </div>

            <div class="eta-time">
                {eta.strftime("%I:%M %p")}
            </div>

            <div class="eta-label">
                {eta.strftime("%A, %B %d, %Y")}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "📏 Distance",
            f"{distance_miles:.1f} mi",
        )

    with col2:

        st.metric(
            "🚗 Traffic ETA",
            traffic_text,
        )

    with col3:

        st.metric(
            "🕐 Arrival",
            eta.strftime(
                "%I:%M %p"
            ),
        )

    with col4:

        st.metric(
            "🚦 Traffic Delay",
            f"+{delay_minutes:.0f} min",
        )

    # --------------------------------------------------------
    # TRAFFIC CARD
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="traffic-card">

        <h3>{traffic_text_label}</h3>

        <b>Traffic-aware travel time:</b>
        {traffic_text}

        <br>

        <b>Normal estimated time:</b>
        {normal_text}

        <br>

        <b>Estimated traffic delay:</b>
        +{delay_minutes:.0f} minutes

        </div>
        """,
        unsafe_allow_html=True,
    )

    if destination_timezone:

        st.caption(
            "🕐 Destination timezone: "
            f"{destination_timezone}"
        )

    # --------------------------------------------------------
    # ALTERNATIVE ROUTES
    # --------------------------------------------------------

    if len(
        st.session_state.routes
    ) > 1:

        st.divider()

        st.subheader(
            "🛣️ Alternative Routes"
        )

        for index, route in enumerate(
            st.session_state.routes
        ):

            route_minutes = (
                route[
                    "traffic_minutes"
                ]
            )

            route_delay = (
                route[
                    "traffic_delay_minutes"
                ]
            )

            if route_minutes < 60:

                route_time = (
                    f"{route_minutes:.0f} min"
                )

            else:

                hours = int(
                    route_minutes // 60
                )

                mins = int(
                    route_minutes % 60
                )

                route_time = (
                    f"{hours}h {mins}m"
                )

            label = (
                "⭐ Recommended"
                if index == 0
                else f"Route {index + 1}"
            )

            traffic_label_text, _ = (
                traffic_label(
                    route_delay
                )
            )

            st.markdown(
                f"""
                <div class="route-card">

                <b>{label}</b>

                <br><br>

                🚗 {route_time}

                &nbsp;&nbsp;•&nbsp;&nbsp;

                📏 {route['distance_miles']:.1f} mi

                <br>

                {traffic_label_text}

                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# SELECTED MAP LOCATION
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

            st.success(address)

        else:

            st.warning(
                "Address not found."
            )


# ============================================================
# SAVE DESTINATION
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

            st.success(
                "Place saved!"
            )

        else:

            st.info(
                "This place is already saved."
            )


# ============================================================
# FAVORITES
# ============================================================

if st.session_state.favorites:

    st.divider()

    st.subheader(
        "⭐ Saved Places"
    )

    for index, favorite in enumerate(
        st.session_state.favorites
    ):

        col1, col2 = st.columns(
            [6, 1]
        )

        with col1:

            st.write(
                f"📍 {favorite['name']}"
            )

        with col2:

            if st.button(
                "✕",
                key=f"remove_{index}",
            ):

                st.session_state.favorites.pop(
                    index
                )

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
    "Traffic routing by Google Routes API • "
    "Map data © OpenStreetMap contributors • "
    "Geocoding by Nominatim"
)
