import json
from pathlib import Path
from app.engine.poi_planner import MultimodalPlan, PointOfInterest, plan_trip_to_poi
from app.engine.timetable_router import TimeDependentRailway, format_seconds_to_hhmm


def plan_to_geojson(network: TimeDependentRailway, plan: MultimodalPlan) -> dict:
    """Convert a MultimodalPlan into an RFC 7946 GeoJSON FeatureCollection."""
    features: list[dict] = []

    # 1. Rail segments (LineString per leg) & Station markers (Point)
    visited_stations: list[tuple[str, str, str]] = []  # (station_id, role, detail)

    for idx, (from_id, edge) in enumerate(plan.legs):
        s_from = network.stations[from_id]
        s_to = network.stations[edge.to_station_id]

        if idx == 0:
            visited_stations.append(
                (from_id, "origin", f"Depart {format_seconds_to_hhmm(edge.dep_sec)}")
            )

        is_last_leg = idx == len(plan.legs) - 1
        next_trip = plan.legs[idx + 1][1].trip_id if not is_last_leg else None
        is_transfer = (not is_last_leg) and (next_trip != edge.trip_id)

        role = "arrival_station" if is_last_leg else ("transfer" if is_transfer else "stop")
        detail = f"Arrive {format_seconds_to_hhmm(edge.arr_sec)}"
        if not is_last_leg:
            detail += f" | Next dep {format_seconds_to_hhmm(plan.legs[idx + 1][1].dep_sec)}"
        visited_stations.append((edge.to_station_id, role, detail))

        # GeoJSON uses [longitude, latitude] order
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[s_from.lon, s_from.lat], [s_to.lon, s_to.lat]],
                },
                "properties": {
                    "mode": "rail",
                    "from": s_from.name,
                    "to": s_to.name,
                    "departure": format_seconds_to_hhmm(edge.dep_sec),
                    "arrival": format_seconds_to_hhmm(edge.arr_sec),
                    "route": edge.route_name,
                },
            }
        )

    # 2. Last-mile walking segment (LineString from arrival station to POI)
    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [plan.dest_station.lon, plan.dest_station.lat],
                    [plan.poi.lon, plan.poi.lat],
                ],
            },
            "properties": {
                "mode": "walk",
                "from": plan.dest_station.name,
                "to": plan.poi.name,
                "distance_km": round(plan.walk_km, 2),
                "duration_min": plan.walk_sec // 60,
            },
        }
    )

    # 3. Point features for stations + destination POI
    for st_id, role, detail in visited_stations:
        st = network.stations[st_id]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [st.lon, st.lat]},
                "properties": {"name": st.name, "role": role, "detail": detail},
            }
        )

    features.append(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [plan.poi.lon, plan.poi.lat]},
            "properties": {
                "name": plan.poi.name,
                "role": "poi",
                "detail": f"Reach POI at {format_seconds_to_hhmm(plan.poi_arrival_sec)}",
            },
        }
    )

    return {"type": "FeatureCollection", "features": features}


def export_interactive_map(
    geojson_data: dict,
    title: str,
    geojson_path: str | Path = "outputs/itinerary.geojson",
    html_path: str | Path = "outputs/itinerary_map.html",
) -> None:
    """Save GeoJSON file and render a standalone Leaflet.js interactive HTML map."""
    g_path = Path(geojson_path)
    h_path = Path(html_path)
    g_path.parent.mkdir(parents=True, exist_ok=True)

    g_path.write_text(json.dumps(geojson_data, indent=2, ensure_ascii=False), encoding="utf-8")

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, sans-serif; }}
    #map {{ height: 100vh; width: 100vw; }}
    .legend {{
      background: white; padding: 12px 16px; border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2); line-height: 1.6; font-size: 13px;
    }}
    .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const geojsonData = {json.dumps(geojson_data, ensure_ascii=False)};
    const map = L.map('map').setView([46.6, 2.2], 6);

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, USGS, Intermap, INCREMENT P, NRCan, Esri Japan, METI, Esri China (Hong Kong), Esri Korea, Esri (Thailand), NGCC, (c) OpenStreetMap contributors, and the GIS User Community',
      maxZoom: 19
    }}).addTo(map);

    const roleColors = {{
      origin: '#16a34a',
      transfer: '#ea580c',
      stop: '#2563eb',
      arrival_station: '#7c3aed',
      poi: '#dc2626'
    }};

    const layer = L.geoJSON(geojsonData, {{
      style: function(feature) {{
        if (feature.properties.mode === 'walk') {{
          return {{ color: '#dc2626', weight: 4, dashArray: '6, 8' }};
        }}
        return {{ color: '#2563eb', weight: 4, opacity: 0.85 }};
      }},
      pointToLayer: function(feature, latlng) {{
        const role = feature.properties.role;
        const radius = (role === 'origin' || role === 'poi' || role === 'transfer') ? 8 : 5;
        return L.circleMarker(latlng, {{
          radius: radius,
          fillColor: roleColors[role] || '#2563eb',
          color: '#ffffff',
          weight: 2,
          fillOpacity: 0.95
        }});
      }},
      onEachFeature: function(feature, lyr) {{
        const p = feature.properties;
        if (feature.geometry.type === 'Point') {{
          lyr.bindPopup(`<b>${{p.name}}</b><br/>Role: ${{p.role}}<br/>${{p.detail}}`);
        }} else if (p.mode === 'rail') {{
          lyr.bindPopup(`<b>${{p.from}} &rarr; ${{p.to}}</b><br/>${{p.departure}} - ${{p.arrival}}<br/>Line: ${{p.route}}`);
        }} else if (p.mode === 'walk') {{
          lyr.bindPopup(`<b>Last-Mile Walk</b><br/>${{p.from}} &rarr; ${{p.to}}<br/>${{p.distance_km}} km (~${{p.duration_min}} min)`);
        }}
      }}
    }}).addTo(map);

    map.fitBounds(layer.getBounds(), {{ padding: [40, 40] }});

    const legend = L.control({{ position: 'bottomright' }});
    legend.onAdd = function() {{
      const div = L.DomUtil.create('div', 'legend');
      div.innerHTML = `
        <b>{title}</b><br/>
        <span class="dot" style="background:#16a34a"></span>Origin Station<br/>
        <span class="dot" style="background:#ea580c"></span>Transfer Station<br/>
        <span class="dot" style="background:#2563eb"></span>Intermediate Stop / Rail<br/>
        <span class="dot" style="background:#7c3aed"></span>Arrival Station<br/>
        <span class="dot" style="background:#dc2626"></span>Destination POI &amp; Walk
      `;
      return div;
    }};
    legend.addTo(map);
  </script>
</body>
</html>
"""
    h_path.write_text(html_template, encoding="utf-8")
    print(f"Saved GeoJSON to: {g_path.resolve()}")
    print(f"Saved Interactive Map to: {h_path.resolve()}")


if __name__ == "__main__":
    DATE = "20261221"
    td_network = TimeDependentRailway.for_date(DATE, "DATA")

    vieux_port = PointOfInterest("Vieux-Port de Marseille", lat=43.2951, lon=5.3744)
    plan = plan_trip_to_poi(td_network, "Bègles", vieux_port, "07:30:00")

    if plan:
        geojson = plan_to_geojson(td_network, plan)
        export_interactive_map(
            geojson,
            title="Bègles → Vieux-Port de Marseille (2026-12-21)",
            geojson_path="outputs/begles_to_vieux_port.geojson",
            html_path="outputs/begles_to_vieux_port.html",
        )