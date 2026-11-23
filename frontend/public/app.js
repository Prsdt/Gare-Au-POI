const API_BASE =
  window.location.port === "3000" ? "http://localhost:8000/api" : "/api";

const map = L.map("map", { zoomControl: true }).setView([46.6, 2.2], 6);

// Clean, bright CartoDB Positron map tiles matching the light indigo/white aesthetic
L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
  attribution: "Tiles &copy; Esri &mdash; OpenStreetMap contributors",
  maxZoom: 16,
}).addTo(map);

let routeLayer = null;
let originPin = null;
let catalogPOIs = [];
let selectedPOIs = [];
let customOrigin = null;
let pickingOriginOnMap = false;

const stationSearch = document.getElementById("station-search");
const stationSelect = document.getElementById("station-select");
const customOriginBadge = document.getElementById("custom-origin-badge");
const pickOriginMapBtn = document.getElementById("pick-origin-map-btn");
const poiCatalogSelect = document.getElementById("poi-catalog");
const selectedPoisList = document.getElementById("selected-pois");
const statusMsg = document.getElementById("status-msg");
const resultsSection = document.getElementById("results");
const criterionInput = document.getElementById("criterion");

// Top Navigation Pill Switcher for Optimization Criterion
document.querySelectorAll(".nav-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    criterionInput.value = tab.dataset.val;
  });
});

function setCustomOrigin(lat, lon, label) {
  customOrigin = { lat, lon, label };
  customOriginBadge.classList.remove("hidden");
  customOriginBadge.innerHTML = `<span>📍 <b>${label}</b> (${lat.toFixed(3)}, ${lon.toFixed(3)})</span><button type="button" id="clear-origin">✕</button>`;
  document.getElementById("clear-origin").onclick = () => {
    customOrigin = null;
    customOriginBadge.classList.add("hidden");
    if (originPin) map.removeLayer(originPin);
  };
  if (originPin) map.removeLayer(originPin);
  originPin = L.marker([lat, lon], {
    icon: L.divIcon({
      className: "",
      html: `<div class="map-callout origin"><span class="dot"></span>${label}</div>`,
      iconAnchor: [20, 14],
    }),
  }).addTo(map);
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
    () => (statusMsg.textContent = "GPS indisponible. Cliquez sur la carte ou choisissez une gare.")
  );
});

pickOriginMapBtn.addEventListener("click", () => {
  pickingOriginOnMap = !pickingOriginOnMap;
  pickOriginMapBtn.classList.toggle("active", pickingOriginOnMap);
  pickOriginMapBtn.textContent = pickingOriginOnMap ? "🎯 Cliquez sur la carte..." : "🗺️ Sur la carte";
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
    statusMsg.textContent = "⚠️ Backend API hors ligne sur le port 8000.";
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
    statusMsg.textContent = "⚠️ Impossible de charger les POIs.";
  }
}

function renderSelectedPOIs() {
  selectedPoisList.innerHTML = "";
  selectedPOIs.forEach((poi, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<span><span class="poi-tag">POI #${idx + 1}</span>${poi.name}</span><button type="button">✕</button>`;
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
    setCustomOrigin(lat, lng, `Départ (${lat.toFixed(3)}, ${lng.toFixed(3)})`);
    pickingOriginOnMap = false;
    pickOriginMapBtn.classList.remove("active");
    pickOriginMapBtn.textContent = "🗺️ Sur la carte";
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
    statusMsg.textContent = "Sélectionnez un point de départ et au moins une destination.";
    return;
  }

  const rawDate = document.getElementById("travel-date").value.replaceAll("-", "");
  const depTime = document.getElementById("dep-time").value;
  const criterion = criterionInput.value;

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
  submitBtn.textContent = "Optimisation en cours...";

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
    <div class="kpi-grid">
      <div class="kpi-card purple">
        <div class="kpi-val">${s.total_duration_min} min</div>
        <div class="kpi-lbl">${s.departure_time} → ${s.final_arrival_time}</div>
      </div>
      <div class="kpi-card cyan">
        <div class="kpi-val">${s.total_distance_km} km</div>
        <div class="kpi-lbl">${s.total_transfers} corresp.</div>
      </div>
      <div class="kpi-card coral">
        <div class="kpi-val">${s.total_co2_kg} kg</div>
        <div class="kpi-lbl">Empreinte CO₂</div>
      </div>
    </div>

    <div class="eco-card">
      <div>
        <div class="eco-main">🌱 ${s.co2_saved_kg} kg de CO₂ évités</div>
        <div class="eco-sub">Contre ${s.car_co2_kg} kg en voiture thermique</div>
      </div>
      <span class="eco-pill">-${Math.round((s.co2_saved_kg / Math.max(s.car_co2_kg, 0.1)) * 100)}% CO₂</span>
    </div>
  `;

  if (data.initial_walk) {
    html += `<div class="stage-card"><div class="walk-pill">🚶 Marche initiale : ${data.initial_walk.walk_km} km (~${data.initial_walk.walk_min} min) → ${data.initial_walk.to_station}</div></div>`;
  }

  data.stages.forEach((st) => {
    html += `<div class="stage-card"><div class="stage-title"><span class="step-pill coral">${st.stage}</span>${st.poi_name}</div>`;
    st.rail_legs.forEach((leg) => {
      html += `
        <div class="leg-row">
          <div><b>${leg.departure}</b> ${leg.from_station} &rarr; <b>${leg.arrival}</b> ${leg.to_station}</div>
          <div class="leg-meta">${leg.mode} · ${leg.distance_km} km · ${leg.co2_g} g CO₂</div>
        </div>
      `;
    });
    html += `<div class="walk-pill">🚶 Marche finale : ${st.walk_km} km (~${st.walk_min} min) depuis ${st.arrival_station} · Arrivée ${st.poi_arrival_time}</div></div>`;
  });

  resultsSection.innerHTML = html;
}

function renderGeoJSON(geojson) {
  if (routeLayer) map.removeLayer(routeLayer);
  if (originPin) map.removeLayer(originPin);

  routeLayer = L.geoJSON(geojson, {
    style: (f) =>
      f.properties.mode === "walk"
        ? { color: "#fb7185", weight: 4, dashArray: "6, 8" }
        : { color: "#6c5dd3", weight: 5 },
    pointToLayer: (f, latlng) => {
      const role = f.properties.role;
      if (role === "origin" || role === "poi") {
        return L.marker(latlng, {
          icon: L.divIcon({
            className: "",
            html: `<div class="map-callout ${role}"><span class="dot"></span>${f.properties.name}</div>`,
            iconAnchor: [20, 14],
          }),
        });
      }
      return L.circleMarker(latlng, {
        radius: role === "transfer" ? 7 : 5,
        fillColor: role === "transfer" ? "#f43f5e" : "#6c5dd3",
        color: "#ffffff",
        weight: 2,
        fillOpacity: 1,
      });
    },
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      if (f.geometry.type === "Point") lyr.bindPopup(`<b>${p.name}</b><br/>${p.detail}`);
      else if (p.mode === "rail") lyr.bindPopup(`<b>${p.from} &rarr; ${p.to}</b><br/>${p.departure} - ${p.arrival} (${p.train_type})`);
      else lyr.bindPopup(`<b>Marche</b>: ${p.distance_km} km (~${p.duration_min} min)`);
    },
  }).addTo(map);

  map.fitBounds(routeLayer.getBounds(), { padding: [90, 420] });
}

loadStations("Bordeaux");
loadPOICatalog();