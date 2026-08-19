import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from streamlit_geolocation import streamlit_geolocation

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="Map Explorer",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------

st.markdown(
    """
    <style>
        .stApp {
            background: #f5f7fa;
        }

        .main-title {
            font-size: 42px;
            font-weight: 800;
            margin-bottom: 0;
        }

        .subtitle {
            color: #666;
            font-size: 17px;
            margin-bottom: 25px;
        }

        .info-card {
            background: white;
            padding: 18px;
            border-radius: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            margin-bottom: 12px;
        }

        .big-number {
            font-size: 28px;
            font-weight: 700;
        }

        .small-label {
            color: #777;
            font-size: 13px;
        }

        div[data-testid="stMetric"] {
            background: white;
            padding: 12px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "search_location" not in st.session_state:
    st.session_state.search_location = None

if "search_lat" not in st.session_state:
    st.session_state.search_lat = None

if "search_lon" not in st.session_state:
    st.session_state.search_lon = None

if "search_address" not in st.session_state:
    st.session_state.search_address = None

if "current_lat" not in st.session_state:
    st.session_state.current_lat = None

if "current_lon" not in st.session_state:
    st.session_state.current_lon = None

if "route_data" not in st.session_state:
    st.session_state.route_data = None

if "map_click" not in st.session_state:
    st.session_state.map_click = None


# ---------------------------------------------------------
# GEOCODER
# ---------------------------------------------------------

geolocator = Nominatim(
    user_agent="map-explorer-streamlit-app"
)


def search_place(query):
    """Search an address/place using OpenStreetMap Nominatim."""

    if not query or not query.strip():
        return None

    try:
        location = geolocator.geocode(
            query,
            timeout=10,
            addressdetails=True
        )

        if location:
            return {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "address": location.address
            }

    except (GeocoderTimedOut, GeocoderServiceError):
        return None
    except Exception:
        return None

    return None


def reverse_geocode(lat, lon):
    """Convert coordinates into an address."""

    try:
        location = geolocator.reverse(
            (lat, lon),
            timeout=10,
            addressdetails=True
        )

        if location:
            return location.address

    except Exception:
        return None

    return None


# ---------------------------------------------------------
# ROUTING
# ---------------------------------------------------------

def get_route(start_lat, start_lon, end_lat, end_lon):
    """
    Get a driving route from OSRM.

    OSRM coordinates use:
    longitude,latitude
    """

    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            return None

        route = data["routes"][0]

        return {
            "distance_miles": route["distance"] / 1609.344,
            "distance_km": route["distance"] / 1000,
            "duration_minutes": route["duration"] / 60,
            "geometry": route["geometry"]["coordinates"]
        }

    except Exception:
        return None


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.markdown(
    '<div class="main-title">🗺️ Map Explorer</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    "Explore places, search locations, find your position, and get directions."
    "</div>",
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:

    st.header("🔎 Search")

    search_query = st.text_input(
        "Search for a place",
        placeholder="Princeton Junction, NJ..."
    )

    search_button = st.button(
        "🔍 Search",
        use_container_width=True
    )

    st.divider()

    st.header("📍 Your Location")

    location_data = streamlit_geolocation()

    if location_data:

        latitude = location_data.get("latitude")
        longitude = location_data.get("longitude")

        if latitude is not None and longitude is not None:

            st.session_state.current_lat = latitude
            st.session_state.current_lon = longitude

            st.success("Location found!")

            st.caption(
                f"Latitude: {latitude:.6f}"
            )

            st.caption(
                f"Longitude: {longitude:.6f}"
            )

    else:
        st.info(
            "Click the location button above to allow "
            "your browser to share your location."
        )

    st.divider()

    st.header("🧭 Directions")

    start_option = st.radio(
        "Starting point",
        [
            "My Location",
            "Search Result"
        ]
    )

    if st.session_state.search_address:
        st.caption(
            f"Destination: {st.session_state.search_address}"
        )
    else:
        st.caption(
            "Search for a destination first."
        )


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

if search_button:

    if not search_query.strip():

        st.warning(
            "Please enter a place to search."
        )

    else:

        with st.spinner("Searching..."):

            result = search_place(search_query)

        if result:

            st.session_state.search_location = result
            st.session_state.search_lat = result["latitude"]
            st.session_state.search_lon = result["longitude"]
            st.session_state.search_address = result["address"]
            st.session_state.route_data = None

            st.success(
                f"Found: {result['address']}"
            )

        else:

            st.error(
                "I couldn't find that location. "
                "Try a more specific address or city."
            )


# ---------------------------------------------------------
# DEFAULT MAP LOCATION
# ---------------------------------------------------------

if st.session_state.current_lat is not None:

    default_lat = st.session_state.current_lat
    default_lon = st.session_state.current_lon

elif st.session_state.search_lat is not None:

    default_lat = st.session_state.search_lat
    default_lon = st.session_state.search_lon

else:

    # Default location: Princeton Junction, NJ
    default_lat = 40.3173
    default_lon = -74.6199


# ---------------------------------------------------------
# MAP
# ---------------------------------------------------------

map_object = folium.Map(
    location=[
        default_lat,
        default_lon
    ],
    zoom_start=13,
    control_scale=True,
    tiles="OpenStreetMap"
)


# ---------------------------------------------------------
# MAP LAYERS
# ---------------------------------------------------------

folium.TileLayer(
    "OpenStreetMap",
    name="Street Map"
).add_to(map_object)

folium.TileLayer(
    "CartoDB positron",
    name="Light Map"
).add_to(map_object)

folium.TileLayer(
    "CartoDB dark_matter",
    name="Dark Map"
).add_to(map_object)


# ---------------------------------------------------------
# CURRENT LOCATION MARKER
# ---------------------------------------------------------

if (
    st.session_state.current_lat is not None
    and st.session_state.current_lon is not None
):

    current_popup = folium.Popup(
        "<b>📍 Your Location</b>",
        max_width=250
    )

    folium.Marker(
        location=[
            st.session_state.current_lat,
            st.session_state.current_lon
        ],
        popup=current_popup,
        tooltip="Your Location",
        icon=folium.Icon(
            color="blue",
            icon="user",
            prefix="fa"
        )
    ).add_to(map_object)


# ---------------------------------------------------------
# SEARCH RESULT MARKER
# ---------------------------------------------------------

if st.session_state.search_lat is not None:

    folium.Marker(
        location=[
            st.session_state.search_lat,
            st.session_state.search_lon
        ],
        popup=folium.Popup(
            f"<b>📍 Destination</b><br>"
            f"{st.session_state.search_address}",
            max_width=350
        ),
        tooltip="Destination",
        icon=folium.Icon(
            color="red",
            icon="flag",
            prefix="fa"
        )
    ).add_to(map_object)


# ---------------------------------------------------------
# ROUTE
# ---------------------------------------------------------

if (
    st.session_state.search_lat is not None
    and st.session_state.search_lon is not None
):

    if start_option == "My Location":

        route_start_lat = st.session_state.current_lat
        route_start_lon = st.session_state.current_lon

    else:

        route_start_lat = default_lat
        route_start_lon = default_lon

    if route_start_lat is not None and route_start_lon is not None:

        route_button = st.button(
            "🚗 Get Directions",
            use_container_width=True
        )

        if route_button:

            with st.spinner("Calculating route..."):

                route = get_route(
                    route_start_lat,
                    route_start_lon,
                    st.session_state.search_lat,
                    st.session_state.search_lon
                )

            if route:

                st.session_state.route_data = route

            else:

                st.error(
                    "Could not calculate a route."
                )


# ---------------------------------------------------------
# DRAW ROUTE
# ---------------------------------------------------------

if st.session_state.route_data:

    route = st.session_state.route_data

    route_points = [
        [coordinate[1], coordinate[0]]
        for coordinate in route["geometry"]
    ]

    folium.PolyLine(
        route_points,
        color="#4285F4",
        weight=7,
        opacity=0.85,
        tooltip="Driving Route"
    ).add_to(map_object)

    # Fit map to route

    map_object.fit_bounds(
        [
            [
                route_points[0][0],
                route_points[0][1]
            ],
            [
                route_points[-1][0],
                route_points[-1][1]
            ]
        ]
    )


# ---------------------------------------------------------
# CLICK MAP
# ---------------------------------------------------------

folium.LayerControl().add_to(map_object)


map_result = st_folium(
    map_object,
    width=None,
    height=650,
    returned_objects=[
        "last_clicked"
    ]
)


# ---------------------------------------------------------
# MAP CLICK INFORMATION
# ---------------------------------------------------------

if map_result and map_result.get("last_clicked"):

    clicked = map_result["last_clicked"]

    clicked_lat = clicked["lat"]
    clicked_lon = clicked["lng"]

    st.session_state.map_click = (
        clicked_lat,
        clicked_lon
    )


# ---------------------------------------------------------
# CLICKED LOCATION
# ---------------------------------------------------------

if st.session_state.map_click:

    clicked_lat, clicked_lon = st.session_state.map_click

    st.divider()

    st.subheader("📌 Selected Location")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Latitude",
            f"{clicked_lat:.6f}"
        )

    with col2:

        st.metric(
            "Longitude",
            f"{clicked_lon:.6f}"
        )

    if st.button("📍 Find Address"):

        with st.spinner("Finding address..."):

            address = reverse_geocode(
                clicked_lat,
                clicked_lon
            )

        if address:

            st.success(address)

        else:

            st.warning(
                "No address was found for this location."
            )


# ---------------------------------------------------------
# SEARCH RESULT INFORMATION
# ---------------------------------------------------------

if st.session_state.search_address:

    st.divider()

    st.subheader("📍 Destination")

    st.write(
        st.session_state.search_address
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Latitude",
            f"{st.session_state.search_lat:.6f}"
        )

    with col2:

        st.metric(
            "Longitude",
            f"{st.session_state.search_lon:.6f}"
        )


# ---------------------------------------------------------
# ROUTE INFORMATION
# ---------------------------------------------------------

if st.session_state.route_data:

    route = st.session_state.route_data

    st.divider()

    st.subheader("🚗 Route Information")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Distance",
            f"{route['distance_miles']:.1f} mi"
        )

    with col2:

        st.metric(
            "Distance",
            f"{route['distance_km']:.1f} km"
        )

    with col3:

        minutes = route["duration_minutes"]

        if minutes < 60:

            time_text = f"{minutes:.0f} min"

        else:

            hours = int(minutes // 60)
            remaining = int(minutes % 60)

            time_text = f"{hours}h {remaining}m"

        st.metric(
            "Estimated Drive",
            time_text
        )


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    "🗺️ Map Explorer • Maps © OpenStreetMap contributors "
    "• Geocoding by Nominatim • Routing by OSRM"
)
