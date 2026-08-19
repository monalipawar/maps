import streamlit as st
import requests
import folium

from datetime import datetime
from zoneinfo import ZoneInfo

from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Map Explorer V3",
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
        font-size: 38px;
        font-weight: 800;
    }

    .eta-label {
        color: #687080;
        font-size: 14px;
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

    "route": None,

    "favorites": [],

    "map_click": None,

    "nearby_places": [],

    "map_style": "OpenStreetMap",

    "route_requested": False,
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SERVICES
# ============================================================

geolocator = Nominatim(
    user_agent="map-explorer-v3"
)

timezone_finder = TimezoneFinder()


# ============================================================
# SEARCH PLACE
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
# FIND TIMEZONE
# ============================================================

def get_timezone(lat, lon):

    try:

        timezone_name = timezone_finder.timezone_at(
            lat=lat,
            lng=lon,
        )

        return timezone_name

    except Exception:

        return None


# ============================================================
# CURRENT LOCAL TIME
# ============================================================

def get_local_time(lat, lon):

    timezone_name = get_timezone(
        lat,
        lon,
    )

    if timezone_name:

        try:

            local_time = datetime.now(
                ZoneInfo(timezone_name)
            )

            return local_time, timezone_name

        except Exception:
            pass

    return datetime.now(), "Local time"


# ============================================================
# ROUTING
# ============================================================

def get_route(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
):

    url = (
        "https://router.project-osrm.org/"
        "route/v1/driving/"
        f"{start_lon},{start_lat};"
        f"{end_lon},{end_lat}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": "true",
        "steps": "false",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            return None

        routes = data.get(
            "routes",
            [],
        )

        if not routes:
            return None

        processed_routes = []

        for route in routes:

            processed_routes.append(
                {
                    "distance_miles":
                        route["distance"] / 1609.344,

                    "distance_km":
                        route["distance"] / 1000,

                    "duration_minutes":
                        route["duration"] / 60,

                    "geometry":
                        route["geometry"]["coordinates"],
                }
            )

        return processed_routes

    except Exception:

        return None


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
            [],
        ):

            tags = element.get(
                "tags",
                {},
            )

            if element["type"] == "node":

                place_lat = element.get("lat")
                place_lon = element.get("lon")

            else:

                center = element.get(
                    "center",
                    {},
                )

                place_lat = center.get("lat")
                place_lon = center.get("lon")

            if (
                place_lat is None
                or place_lon is None
            ):
                continue

            name = tags.get(
                "name",
                "Unnamed place",
            )

            places.append(
                {
                    "name": name,
                    "lat": place_lat,
                    "lon": place_lon,
                    "type": category,
                }
            )

        return places[:40]

    except Exception:

        return []


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">🗺️ Map Explorer</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Search places, get directions, and see your arrival time."
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

                st.session_state.route = None

                st.session_state.route_requested = False

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

            st.session_state.current_lat = lat
            st.session_state.current_lon = lon

            st.success(
                "Current location detected."
            )

            st.caption(
                f"{lat:.5f}, {lon:.5f}"
            )

    st.divider()

    st.header("🚗 Directions")

    if st.button(
        "🛣️ Calculate Route",
        use_container_width=True,
    ):

        if (
            st.session_state.current_lat is not None
            and st.session_state.search_lat is not None
        ):

            st.session_state.route_requested = True

            with st.spinner(
                "Calculating route..."
            ):

                routes = get_route(
                    st.session_state.current_lat,
                    st.session_state.current_lon,
                    st.session_state.search_lat,
                    st.session_state.search_lon,
                )

            if routes:

                st.session_state.route = routes

                st.success(
                    f"{len(routes)} route(s) found."
                )

            else:

                st.error(
                    "Could not calculate route."
                )

        else:

            st.warning(
                "Allow location access and search "
                "for a destination first."
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

    st.session_state.map_style = map_style

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

    center_lat = st.session_state.search_lat
    center_lon = st.session_state.search_lon

elif st.session_state.current_lat is not None:

    center_lat = st.session_state.current_lat
    center_lon = st.session_state.current_lon

else:

    # Princeton Junction
    center_lat = 40.3173
    center_lon = -74.6199


# ============================================================
# MAP
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
# TILE LAYER
# ============================================================

folium.TileLayer(
    tiles=st.session_state.map_style,
    name="Map",
).add_to(m)


# ============================================================
# CURRENT LOCATION MARKER
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
        popup="📍 Your current location",
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
        popup=st.session_state.search_address,
        icon=folium.Icon(
            color="red",
            icon="flag",
            prefix="fa",
        ),
    ).add_to(m)


# ============================================================
# NEARBY MARKERS
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
# ROUTES
# ============================================================

if st.session_state.route:

    routes = st.session_state.route

    # Draw all available routes
    for index, route in enumerate(routes):

        route_points = [
            [
                coordinate[1],
                coordinate[0],
            ]
            for coordinate in route["geometry"]
        ]

        # Main route is thicker
        weight = 7 if index == 0 else 4

        opacity = 0.9 if index == 0 else 0.45

        folium.PolyLine(
            route_points,
            color="#4285F4",
            weight=weight,
            opacity=opacity,
            tooltip=(
                "Recommended route"
                if index == 0
                else f"Alternative route {index + 1}"
            ),
        ).add_to(m)

    # Fit map to main route

    main_route = routes[0]

    main_points = [
        [
            coordinate[1],
            coordinate[0],
        ]
        for coordinate in main_route["geometry"]
    ]

    if main_points:

        m.fit_bounds(
            main_points
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
# ROUTE / ETA SECTION
# ============================================================

if st.session_state.route:

    routes = st.session_state.route

    main_route = routes[0]

    duration = main_route[
        "duration_minutes"
    ]

    distance_miles = main_route[
        "distance_miles"
    ]

    distance_km = main_route[
        "distance_km"
    ]

    # --------------------------------------------------------
    # Destination timezone
    # --------------------------------------------------------

    destination_lat = (
        st.session_state.search_lat
    )

    destination_lon = (
        st.session_state.search_lon
    )

    timezone_name = get_timezone(
        destination_lat,
        destination_lon,
    )

    if timezone_name:

        try:

            destination_now = datetime.now(
                ZoneInfo(timezone_name)
            )

        except Exception:

            destination_now = datetime.now()

    else:

        destination_now = datetime.now()

    # --------------------------------------------------------
    # Calculate ETA
    # --------------------------------------------------------

    from datetime import timedelta

    eta = destination_now + timedelta(
        minutes=duration
    )

    # --------------------------------------------------------
    # Format duration
    # --------------------------------------------------------

    if duration < 60:

        duration_text = (
            f"{duration:.0f} min"
        )

    else:

        hours = int(
            duration // 60
        )

        minutes = int(
            duration % 60
        )

        duration_text = (
            f"{hours}h {minutes}m"
        )

    # --------------------------------------------------------
    # ETA card
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="eta-card">

            <div class="eta-label">
                🚗 ESTIMATED ARRIVAL
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
    # Route metrics
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "📏 Distance",
            f"{distance_miles:.1f} mi",
        )

    with col2:

        st.metric(
            "🌎 Distance",
            f"{distance_km:.1f} km",
        )

    with col3:

        st.metric(
            "⏱️ Travel Time",
            duration_text,
        )

    with col4:

        st.metric(
            "🕐 ETA",
            eta.strftime("%I:%M %p"),
        )

    if timezone_name:

        st.caption(
            f"🕐 Destination timezone: "
            f"{timezone_name}"
        )

    # --------------------------------------------------------
    # Route comparison
    # --------------------------------------------------------

    if len(routes) > 1:

        st.divider()

        st.subheader(
            "🛣️ Alternative Routes"
        )

        for index, route in enumerate(
            routes
        ):

            route_duration = route[
                "duration_minutes"
            ]

            if route_duration < 60:

                route_time = (
                    f"{route_duration:.0f} min"
                )

            else:

                h = int(
                    route_duration // 60
                )

                mins = int(
                    route_duration % 60
                )

                route_time = (
                    f"{h}h {mins}m"
                )

            st.write(
                f"**Route {index + 1}:** "
                f"{route_time} • "
                f"{route['distance_miles']:.1f} mi"
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

            st.success(address)

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
            p["lat"] == favorite["lat"]
            and p["lon"] == favorite["lon"]
            for p in st.session_state.favorites
        )

        if not already_saved:

            st.session_state.favorites.append(
                favorite
            )

            st.success(
                "Saved!"
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

    for place in st.session_state.nearby_places[:20]:

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
    "🗺️ Map Explorer V3 • "
    "Map data © OpenStreetMap contributors • "
    "Geocoding by Nominatim • "
    "Routing by OSRM"
)
