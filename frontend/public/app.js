const API_BASE =
  window.location.port === "3000" ? "http://localhost:8000/api" : "/api";

const map = L.map("map").setView([46.6, 2.2], 6);
L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
  attribution: "Tiles &copy; Esri &mdash; OpenStreetMap contributors",
  maxZoom: 19,
}).addTo(map);

let routeLayer = null;
let originPin = null;
let catalogPOIs = [];
let selectedPOIs = [];
let customOrigin = null; // { lat, lon, label }
let pickingOriginOnMap = false;

const stationSearch = document.getElementById("station-search");
const stationSelect = document.getElementById("station-select");
const customOriginBadge = document.getElementById("custom-origin-badge");
const pickOriginMapBtn = document.getElementById("pick-origin-map-btn");
const poiCatalogSelect = document.getElementById("poi-catalog");
const selectedPoisList = document.getElementById("selected-pois");
const statusMsg = document.getElementById("status-msg");
const resultsSection = document.getElementById("results");

function setCustomOrigin(lat, lon, label) {
  customOrigin = { lat, lon, label };
  customOriginBadge.classList.remove("hidden");
  customOriginBadge.innerHTML = `📍 Départ : <b>${label}</b> (${lat.toFixed(4)}, ${lon.toFixed(4)}) <button type="button" id="clear-origin">✕</button>`;
  document.getElementById("clear-origin").onclick = () => {
    customOrigin = null;
    customOriginBadge.classList.add("hidden");
    if (originPin) map.removeLayer(originPin);
  };
  if (originPin) map.removeLayer(originPin);
  originPin = L.marker([lat, lon]).addTo(map).bindPopup(`<b>Départ :</b> ${label}`).openPopup();
  map.setView([lat, lon], 12);
}

document.getElementById("gps-btn").addEventListener("click", () => {
  statusMsg.textContent = "";
  if (!navigator.geolocation) {
    statusMsg.textContent = "La géolocalisation n'est pas supportée par votre navigateur.";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => setCustomOrigin(pos.coords.latitude, pos.coords.longitude, "Ma position GPS"),
    () => (statusMsg.textContent = "Impossible d'accéder à votre position GPS. Cliquez sur la carte ou choisissez une gare.")
  );
});

pickOriginMapBtn.addEventListener("click", () => {
  pickingOriginOnMap = !pickingOriginOnMap;
  pickOriginMapBtn.style.background = pickingOriginOnMap ? "#bfdbfe" : "#e2e8f0";
  pickOriginMapBtn.textContent = pickingOriginOnMap ? "🎯 Cliquez sur la carte..." : "🗺️ Cliquer sur carte";
});

async function loadStations(query = "") {
  try {
    const res = await fetch(`${API_BASE}/stations?q=${encodeURIComponent(query)}`);
    const stations = await res.json();
    stationSelect.innerHTML = "";
    stations.forEach((st) => {
      const opt = document.createElement("option");
      opt.value = st.station_id;
      opt.textContent = st.name;
      stationSelect.appendChild(opt);
    });
    if (stations.length > 0) stationSelect.selectedIndex = 0;
  } catch {
    statusMsg.textContent = "⚠️ Backend API hors ligne (vérifiez que uvicorn tourne sur le port 8000).";
  }
}

async function loadPOICatalog() {
  try {
    const res = await fetch(`${API_BASE}/pois`);
    catalogPOIs = await res.json();
    poiCatalogSelect.innerHTML = "";
    catalogPOIs.forEach((poi, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `${poi.name} (${poi.city})`;
      poiCatalogSelect.appendChild(opt);
    });
    if (catalogPOIs.length > 0 && selectedPOIs.length === 0) {
      selectedPOIs.push({ ...catalogPOIs[0], visit_duration_min: 90 });
      renderSelectedPOIs();
    }
  } catch {
    statusMsg.textContent = "⚠️ Impossible de charger les POIs depuis l'API.";
  }
}

function renderSelectedPOIs() {
  selectedPoisList.innerHTML = "";
  selectedPOIs.forEach((poi, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<span><b>#${idx + 1}</b> ${poi.name}</span><button type="button" data-idx="${idx}">✕</button>`;
    li.querySelector("button").addEventListener("click", () => {
      selectedPOIs.splice(idx, 1);
      renderSelectedPOIs();
    });
    selectedPoisList.appendChild(li);
  });
}

document.getElementById("add-poi-btn").addEventListener("click", () => {
  const poi = catalogPOIs[poiCatalogSelect.value];
  if (poi) {
    selectedPOIs.push({ ...poi, visit_duration_min: 90 });
    renderSelectedPOIs();
  }
});

map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  if (pickingOriginOnMap) {
    setCustomOrigin(lat, lng, `Point de départ (${lat.toFixed(3)}, ${lng.toFixed(3)})`);
    pickingOriginOnMap = false;
    pickOriginMapBtn.style.background = "#e2e8f0";
    pickOriginMapBtn.textContent = "🗺️ Cliquer sur carte";
    return;
  }
  selectedPOIs.push({
    name: `Destination (${lat.toFixed(3)}, ${lng.toFixed(3)})`,
    lat,
    lon: lng,
    visit_duration_min: 60,
  });
  renderSelectedPOIs();
});

let debounceTimer;
stationSearch.addEventListener("input", () => {
  customOrigin = null;
  customOriginBadge.classList.add("hidden");
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => loadStations(stationSearch.value.trim()), 250);
});

document.getElementById("route-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  statusMsg.textContent = "";

  if ((!customOrigin && !stationSelect.value) || selectedPOIs.length === 0) {
    statusMsg.textContent = "Veuillez choisir un point de départ et au moins une destination (POI).";
    return;
  }

  const rawDate = document.getElementById("travel-date").value.replaceAll("-", "");
  const depTime = document.getElementById("dep-time").value;
  const criterion = document.getElementById("criterion").value;

  const payload = {
    pois: selectedPOIs.map((p) => ({
      name: p.name,
      lat: p.lat,
      lon: p.lon,
      visit_duration_min: p.visit_duration_min || 60,
    })),
    date: rawDate,
    departure_time: depTime,
    criterion,
  };

  if (customOrigin) {
    payload.origin_lat = customOrigin.lat;
    payload.origin_lon = customOrigin.lon;
    payload.origin_label = customOrigin.label;
  } else {
    payload.origin_station_id = stationSelect.value;
  }

  const submitBtn = document.getElementById("submit-btn");
  submitBtn.disabled = true;
  submitBtn.textContent = "Calcul en cours...";

  try {
    const res = await fetch(`${API_BASE}/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur lors du calcul");

    renderResults(data);
    renderGeoJSON(data.geojson);
  } catch (err) {
    statusMsg.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Calculer l'itinéraire";
  }
});

function renderResults(data) {
  const s = data.summary;
  resultsSection.classList.remove("hidden");
  let html = `
    <div class="summary-card">
      <div><b>Départ :</b> ${s.departure_time} &rarr; <b>Arrivée finale :</b> ${s.final_arrival_time}</div>
      <div><b>Durée totale :</b> ${s.total_duration_min} min | <b>Correspondances :</b> ${s.total_transfers}</div>
      <div><b>Distance :</b> ${s.total_distance_km} km</div>
      <div class="co2-badge">🌱 ${s.total_co2_kg} kg CO₂ (vs ${s.car_co2_kg} kg en voiture — ${s.co2_saved_kg} kg économisés)</div>
    </div>
  `;

  if (data.initial_walk) {
    html += `<div class="stage-card"><div class="walk-item">🚶 Marche initiale : ${data.initial_walk.walk_km} km (~${data.initial_walk.walk_min} min) vers <b>${data.initial_walk.to_station}</b></div></div>`;
  }

  data.stages.forEach((st) => {
    html += `<div class="stage-card"><strong>Étape ${st.stage} : ${st.poi_name}</strong>`;
    st.rail_legs.forEach((leg) => {
      html += `<div class="leg-item">${leg.departure} <b>${leg.from_station}</b> &rarr; ${leg.arrival} <b>${leg.to_station}</b> (${leg.mode} · ${leg.co2_g}g CO₂)</div>`;
    });
    html += `<div class="walk-item">🚶 Marche : ${st.walk_km} km (~${st.walk_min} min) depuis ${st.arrival_station} &rarr; Arrivée ${st.poi_arrival_time}</div></div>`;
  });

  resultsSection.innerHTML = html;
}

function renderGeoJSON(geojson) {
  if (routeLayer) map.removeLayer(routeLayer);
  const colors = { origin: "#16a34a", transfer: "#ea580c", stop: "#2563eb", poi: "#dc2626" };

  routeLayer = L.geoJSON(geojson, {
    style: (f) =>
      f.properties.mode === "walk"
        ? { color: "#dc2626", weight: 4, dashArray: "6, 8" }
        : { color: "#2563eb", weight: 4 },
    pointToLayer: (f, latlng) =>
      L.circleMarker(latlng, {
        radius: f.properties.role === "stop" ? 5 : 8,
        fillColor: colors[f.properties.role] || "#2563eb",
        color: "#fff",
        weight: 2,
        fillOpacity: 0.95,
      }),
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      if (f.geometry.type === "Point") lyr.bindPopup(`<b>${p.name}</b><br/>${p.detail}`);
      else if (p.mode === "rail") lyr.bindPopup(`<b>${p.from} &rarr; ${p.to}</b><br/>${p.departure} - ${p.arrival} (${p.train_type})`);
      else lyr.bindPopup(`<b>Marche</b>: ${p.distance_km} km (~${p.duration_min} min)`);
    },
  }).addTo(map);

  map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
}

loadStations("Bordeaux");
loadPOICatalog();