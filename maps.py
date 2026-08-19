import streamlit as st
import requests
import folium

from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Map Explorer",
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
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .subtitle {
        color: #687080;
        font-size: 17px;
        margin-bottom: 20px;
    }

    .search-box {
        background: white;
        padding: 18px;
        border-radius: 16px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.08);
        margin-bottom: 15px;
    }

    .map-card {
        background: white;
        padding: 8px;
        border-radius: 16px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.08);
    }

    .place-card {
        background: white;
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }

    .small-text {
        color: #6b7280;
        font-size: 13px;
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
    "travel_mode": "driving",
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SERVICES
# ============================================================

geolocator = Nominatim(
    user_agent="map-explorer-v2"
)


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
# ROUTING
# ============================================================

def get_route(
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
        f"https://router.project-osrm.org/"
        f"route/v1/{profile}/"
        f"{start_lon},{start_lat};"
        f"{end_lon},{end_lat}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        data = response.json()

        if data.get("code") != "Ok":
            return None

        route = data["routes"][0]

        return {
            "distance_miles":
                route["distance"] / 1609.344,

            "distance_km":
                route["distance"] / 1000,

            "duration_minutes":
                route["duration"] / 60,

            "geometry":
                route["geometry"]["coordinates"],
        }

    except Exception:

        return None


# ============================================================
# NEARBY PLACES
# ============================================================

def get_nearby_places(lat, lon, category):

    queries = {

        "🍕 Restaurants": "amenity=restaurant",

        "☕ Cafes": "amenity=cafe",

        "⛽ Gas Stations": "amenity=fuel",

        "🏥 Hospitals": "amenity=hospital",

        "🏨 Hotels": "tourism=hotel",

        "🛒 Shops": "shop",

        "🏫 Schools": "amenity=school",

        "🏦 Banks": "amenity=bank",
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

        for element in data.get("elements", []):

            tags = element.get("tags", {})

            if element["type"] == "node":

                place_lat = element.get("lat")
                place_lon = element.get("lon")

            else:

                center = element.get("center", {})

                place_lat = center.get("lat")
                place_lon = center.get("lon")

            if place_lat is None or place_lon is None:
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
    "Search places, explore nearby locations, and get directions."
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

            with st.spinner("Searching..."):

                result = search_place(
                    search_query
                )

            if result:

                st.session_state.search_lat = result["lat"]
                st.session_state.search_lon = result["lon"]
                st.session_state.search_address = result["address"]

                st.session_state.route = None

                st.success("Location found!")

            else:

                st.error(
                    "Location not found."
                )

    st.divider()

    st.header("📍 Location")

    location = streamlit_geolocation()

    if location:

        lat = location.get("latitude")
        lon = location.get("longitude")

        if lat is not None and lon is not None:

            st.session_state.current_lat = lat
            st.session_state.current_lon = lon

            st.success(
                "Current location detected."
            )

    st.divider()

    st.header("🧭 Directions")

    travel_mode = st.radio(
        "Travel mode",
        [
            "🚗 Driving",
            "🚶 Walking",
            "🚴 Cycling",
        ],
    )

    if travel_mode.startswith("🚗"):
        st.session_state.travel_mode = "driving"

    elif travel_mode.startswith("🚶"):
        st.session_state.travel_mode = "walking"

    else:
        st.session_state.travel_mode = "cycling"

    if st.button(
        "🛣️ Get Directions",
        use_container_width=True,
    ):

        if (
            st.session_state.current_lat is not None
            and st.session_state.search_lat is not None
        ):

            with st.spinner(
                "Calculating route..."
            ):

                route = get_route(
                    st.session_state.current_lat,
                    st.session_state.current_lon,
                    st.session_state.search_lat,
                    st.session_state.search_lon,
                    st.session_state.travel_mode,
                )

            if route:

                st.session_state.route = route

            else:

                st.error(
                    "Could not calculate route."
                )

        else:

            st.warning(
                "You need your current location "
                "and a destination."
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

    st.session_state.map_style = map_style

    st.divider()

    st.header("🏪 Explore Nearby")

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
            or st.session_state.search_lat
        )

        target_lon = (
            st.session_state.current_lon
            or st.session_state.search_lon
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
# DETERMINE MAP CENTER
# ============================================================

if st.session_state.search_lat is not None:

    center_lat = st.session_state.search_lat
    center_lon = st.session_state.search_lon

elif st.session_state.current_lat is not None:

    center_lat = st.session_state.current_lat
    center_lon = st.session_state.current_lon

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
    st.session_state.map_style,
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
        popup="📍 Your current location",
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
# ROUTE
# ============================================================

if st.session_state.route:

    route = st.session_state.route

    route_points = [
        [
            coordinate[1],
            coordinate[0],
        ]
        for coordinate in route["geometry"]
    ]

    folium.PolyLine(
        route_points,
        color="#4285F4",
        weight=7,
        opacity=0.85,
        tooltip="Route",
    ).add_to(m)

    if route_points:

        m.fit_bounds(
            route_points
        )


# ============================================================
# MAP CONTROLS
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
# CLICKED LOCATION
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
        "📍 Get Address",
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
# ROUTE INFORMATION
# ============================================================

if st.session_state.route:

    route = st.session_state.route

    st.divider()

    st.subheader(
        "🧭 Route Information"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Distance",
            f"{route['distance_miles']:.1f} mi",
        )

    with col2:

        st.metric(
            "Distance",
            f"{route['distance_km']:.1f} km",
        )

    with col3:

        minutes = route[
            "duration_minutes"
        ]

        if minutes < 60:

            eta = f"{minutes:.0f} min"

        else:

            hours = int(minutes // 60)
            mins = int(minutes % 60)

            eta = f"{hours}h {mins}m"

        st.metric(
            "Estimated Time",
            eta,
        )


# ============================================================
# FAVORITES
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
            place["lat"] == favorite["lat"]
            and place["lon"] == favorite["lon"]
            for place in st.session_state.favorites
        )

        if not already_saved:

            st.session_state.favorites.append(
                favorite
            )

            st.success(
                "Saved to favorites!"
            )

        else:

            st.info(
                "Already saved."
            )


# ============================================================
# FAVORITES LIST
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
            [5, 1]
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
# NEARBY RESULTS
# ============================================================

if st.session_state.nearby_places:

    st.divider()

    st.subheader(
        f"🏪 Nearby {nearby_category}"
    )

    for place in st.session_state.nearby_places[:20]:

        st.markdown(
            f"""
            <div class="place-card">
                <b>📍 {place['name']}</b>
                <div class="small-text">
                    {place['type']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🗺️ Map Explorer V2 • "
    "Map data © OpenStreetMap contributors • "
    "Geocoding by Nominatim • "
    "Routing by OSRM"
)
