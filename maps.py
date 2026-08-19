import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Auto Location Clock",
    page_icon="🕐",
    layout="centered"
)

components.html(
    """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                margin: 0;
                background: linear-gradient(135deg, #0f172a, #1e293b);
                font-family: Arial, sans-serif;
            }

            .clock-container {
                background: #111827;
                border-radius: 30px;
                padding: 40px 20px;
                text-align: center;
                margin: 20px auto;
                max-width: 650px;
                box-shadow: 0 15px 50px rgba(0,0,0,0.45);
            }

            .location {
                font-size: 22px;
                color: #cbd5e1;
                margin-bottom: 25px;
            }

            .time {
                font-family: monospace;
                font-size: 70px;
                font-weight: bold;
                color: white;
                letter-spacing: 4px;
            }

            .ampm {
                font-size: 24px;
                color: #94a3b8;
                margin-top: 5px;
            }

            .day {
                font-size: 30px;
                font-weight: bold;
                color: white;
                margin-top: 25px;
            }

            .date {
                font-size: 20px;
                color: #cbd5e1;
                margin-top: 8px;
            }

            .timezone {
                font-size: 15px;
                color: #64748b;
                margin-top: 25px;
            }

            .detecting {
                color: #94a3b8;
                font-size: 16px;
            }
        </style>
    </head>

    <body>

        <div class="clock-container">

            <div class="location" id="location">
                📍 Detecting location...
            </div>

            <div class="time" id="time">
                00:00:00
            </div>

            <div class="ampm" id="ampm">
                AM
            </div>

            <div class="day" id="day">
                Monday
            </div>

            <div class="date" id="date">
                January 1, 2026
            </div>

            <div class="timezone" id="timezone">
                Detecting time zone...
            </div>

        </div>

        <script>

            // Get the user's time zone automatically
            const timeZone =
                Intl.DateTimeFormat().resolvedOptions().timeZone;


            // Convert time zone into a friendly location name
            function getLocationName(zone) {

                const locations = {

                    "America/New_York":
                        "📍 Eastern United States",

                    "America/Chicago":
                        "📍 Central United States",

                    "America/Denver":
                        "📍 Mountain United States",

                    "America/Los_Angeles":
                        "📍 Pacific United States",

                    "America/Anchorage":
                        "📍 Alaska",

                    "Pacific/Honolulu":
                        "📍 Hawaii",

                    "Asia/Kolkata":
                        "📍 India",

                    "Asia/Calcutta":
                        "📍 India",

                    "Europe/London":
                        "📍 United Kingdom",

                    "Europe/Paris":
                        "📍 France / Central Europe",

                    "Europe/Berlin":
                        "📍 Germany / Central Europe",

                    "Asia/Tokyo":
                        "📍 Japan",

                    "Asia/Shanghai":
                        "📍 China",

                    "Asia/Singapore":
                        "📍 Singapore",

                    "Australia/Sydney":
                        "📍 Sydney, Australia",

                    "America/Toronto":
                        "📍 Toronto, Canada",

                    "America/Vancouver":
                        "📍 Vancouver, Canada"

                };

                return locations[zone] || "📍 " + zone;
            }


            function updateClock() {

                const now = new Date();


                // Time
                const timeOptions = {
                    timeZone: timeZone,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: true
                };

                const timeParts =
                    new Intl.DateTimeFormat(
                        "en-US",
                        timeOptions
                    ).formatToParts(now);


                let hour = "";
                let minute = "";
                let second = "";
                let dayPeriod = "";


                timeParts.forEach(part => {

                    if (part.type === "hour")
                        hour = part.value;

                    if (part.type === "minute")
                        minute = part.value;

                    if (part.type === "second")
                        second = part.value;

                    if (part.type === "dayPeriod")
                        dayPeriod = part.value;

                });


                document.getElementById("time").textContent =
                    `${hour}:${minute}:${second}`;

                document.getElementById("ampm").textContent =
                    dayPeriod;


                // Day
                const dayOptions = {
                    timeZone: timeZone,
                    weekday: "long"
                };

                document.getElementById("day").textContent =
                    new Intl.DateTimeFormat(
                        "en-US",
                        dayOptions
                    ).format(now);


                // Date
                const dateOptions = {
                    timeZone: timeZone,
                    month: "long",
                    day: "numeric",
                    year: "numeric"
                };

                document.getElementById("date").textContent =
                    new Intl.DateTimeFormat(
                        "en-US",
                        dateOptions
                    ).format(now);


                // Time zone
                const zoneOptions = {
                    timeZone: timeZone,
                    timeZoneName: "long"
                };

                const zoneParts =
                    new Intl.DateTimeFormat(
                        "en-US",
                        zoneOptions
                    ).formatToParts(now);

                const zoneName =
                    zoneParts.find(
                        part => part.type === "timeZoneName"
                    );


                document.getElementById("timezone").textContent =
                    (zoneName
                        ? zoneName.value
                        : timeZone)
                    + " • " + timeZone;


                // Location
                document.getElementById("location").textContent =
                    getLocationName(timeZone);

            }


            // Run immediately
            updateClock();


            // Update every second
            setInterval(updateClock, 1000);

        </script>

    </body>
    </html>
    """,
    height=500
)
