```python
import streamlit as st
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
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background: #f5f7fb;
    }

    .main-title {
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
        text-align: center;
        margin-top: 18px;
    }

    .eta-label {
        color: #687080;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    .eta-time {
        font-size: 42px;
        font-weight: 800;
        margin-top: 5px;
    }

    .eta-date {
        color: #687080;
        font-size: 14px;
    }

    .route-card {
        background: white;
        padding: 18px;
        border-radius: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }

    .traffic-normal {
        background: #e9f7ef;
        padding: 12px;
        border-radius: 12px;
        margin-top: 12px;
    }

    .info-card {
        background: white;
        padding: 18px;
        border-radius: 15px;
        margin-top: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }

    .place-card {
        background: white;
        padding: 14px;
        border-radius: 12px;
        margin-bottom: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
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

    "route_mode": "driving",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SERVICES
# ============================================================

geolocator = Nominatim(
    user_agent="MapExplorerV4/1.0"
)

timezone_finder = TimezoneFinder()


# ============================================================
# AUTOMATIC ETA REFRESH
# ============================================================

# Refresh every 60 seconds once a route exists.
# This keeps the ETA current as the clock advances.

if st.session_state.routes:

    st_autorefresh(
        interval=60 * 1000,
        key="eta_refresh",
    )


# ============================================================
# SEARCH
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
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

        return None

    return None


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
# OSRM ROUTING
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_osrm_routes(
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

    profile = profile_map.get(
        mode,
        "driving",
    )

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
        "steps": "true",
    }

    headers = {
        "User-Agent": (
            "MapExplorerV4/1.0"
        )
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":

            return []

        routes = []

        for route in data.get(
            "routes",
            []
        ):

            routes.append(
                {
                    "distance_meters":
                        route.get(
                            "distance",
                            0
                        ),

                    "distance_miles":
                        route.get(
                            "distance",
                            0
                        ) / 1609.344,

                    "distance_km":
                        route.get(
                            "distance",
                            0
                        ) / 1000,

                    "duration_seconds":
                        route.get(
                            "duration",
                            0
                        ),

                    "duration_minutes":
                        route.get(
                            "duration",
                            0
                        ) / 60,

                    "geometry":
                        [
                            [
                                point[1],
                                point[0]
                            ]
                            for point
                            in route[
                                "geometry"
                            ][
                                "coordinates"
                            ]
                        ],

                    "legs":
                        route.get(
                            "legs",
                            []
                        ),
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

    st.header("🔎 Search")

    search_query = st.text_input(
        "Where do you want to go?",
        placeholder=(
            "New York City, Times Square..."
        ),
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
                    "Location not found. "
                    "Try a city, street address, "
                    "or landmark."
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

            st.session_state.current_lat = lat
            st.session_state.current_lon = lon

            st.success(
                "Location detected!"
            )

            st.caption(
                f"{lat:.5f}, {lon:.5f}"
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

        if index == 0:

            route_color = "#4285F4"
            route_weight = 8
            route_opacity = 0.90

        else:

            route_color = "#7b8794"
            route_weight = 5
            route_opacity = 0.50

        if route["geometry"]:

            folium.PolyLine(
                route["geometry"],
                color=route_color,
                weight=route_weight,
                opacity=route_opacity,
                tooltip=(
                    "⭐ Recommended route"
                    if index == 0
                    else
                    f"Alternative route {index + 1}"
                ),
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

    # --------------------------------------------------------
    # Destination local time
    # --------------------------------------------------------

    destination_now = (
        get_destination_time(
            st.session_state.search_lat,
            st.session_state.search_lon,
        )
    )

    # --------------------------------------------------------
    # Automatic ETA
    # --------------------------------------------------------

    eta = (
        destination_now
        + timedelta(
            seconds=main_route[
                "duration_seconds"
            ]
        )
    )

    # --------------------------------------------------------
    # Format
    # --------------------------------------------------------

    duration_text = format_duration(
        duration_minutes
    )

    distance_text = format_distance(
        distance_miles
    )

    # --------------------------------------------------------
    # ETA CARD
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="eta-card">

            <div class="eta-label">
                🕐 ESTIMATED ARRIVAL
            </div>

            <div class="eta-time">
                {eta.strftime("%I:%M %p")}
            </div>

            <div class="eta-date">
                {eta.strftime("%A, %B %d, %Y")}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ETA INFO
    # --------------------------------------------------------

    timezone_name = get_timezone(
        st.session_state.search_lat,
        st.session_state.search_lon,
    )

    st.markdown(
        f"""
        <div class="traffic-normal">

        🟢 <b>Road-network ETA</b>

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
        "ETA automatically refreshes every 60 seconds."
    )

    # --------------------------------------------------------
    # ROUTE OPTIONS
    # --------------------------------------------------------

    if len(
        st.session_state.routes
    ) > 1:

        st.divider()

        st.subheader(
            "🛣️ Route Options"
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
    "Routing by OSRM • "
    "Geocoding by OpenStreetMap Nominatim • "
    "Map data © OpenStreetMap contributors"
)
```
