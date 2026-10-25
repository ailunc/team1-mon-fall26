// Find caregivers page: address suggestions from NYC GeoSearch and the map.
(function () {
  "use strict";

  // ---------- Address suggestions ----------
  var AUTOCOMPLETE_URL = "https://geosearch.planninglabs.nyc/v2/autocomplete";
  var form = document.getElementById("caregiver-search");
  var input = document.getElementById("search-address");
  var list = document.getElementById("address-suggestions");
  var lat = document.getElementById("search-lat");
  var lng = document.getElementById("search-lng");
  var area = document.getElementById("search-area");
  var timer = null;
  var latest = 0;

  function hideSuggestions() {
    list.hidden = true;
    list.replaceChildren();
    input.setAttribute("aria-expanded", "false");
  }

  // "70 WASHINGTON SQUARE SOUTH" -> "70 Washington Square South"
  function titleCase(text) {
    return text.toLowerCase().replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); });
  }

  function choose(feature) {
    var coords = feature.geometry.coordinates;
    input.value = titleCase(feature.properties.label.split(",")[0]);
    lng.value = coords[0];
    lat.value = coords[1];
    area.value = "";
    hideSuggestions();
    form.submit();
  }

  function showSuggestions(features) {
    list.replaceChildren();
    features.slice(0, 6).forEach(function (feature, i) {
      var item = document.createElement("li");
      item.setAttribute("role", "option");
      item.id = "suggestion-" + i;
      item.textContent = feature.properties.label.replace(/, USA$/, "");
      item.addEventListener("mousedown", function (event) {
        event.preventDefault();
        choose(feature);
      });
      list.appendChild(item);
    });
    list.hidden = features.length === 0;
    input.setAttribute("aria-expanded", String(features.length > 0));
  }

  if (input) {
    input.addEventListener("input", function () {
      // Typing a new address forgets the coordinates of the last one.
      lat.value = "";
      lng.value = "";
      clearTimeout(timer);
      var text = input.value.trim();
      if (text.length < 3) { hideSuggestions(); return; }
      timer = setTimeout(function () {
        var request = ++latest;
        fetch(AUTOCOMPLETE_URL + "?text=" + encodeURIComponent(text))
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (request === latest) showSuggestions(data.features || []);
          })
          .catch(hideSuggestions); // the server still looks the address up on submit
      }, 250);
    });
    input.addEventListener("blur", hideSuggestions);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") hideSuggestions();
    });
    area.addEventListener("change", function () {
      if (area.value) { input.value = ""; lat.value = ""; lng.value = ""; }
    });
  }

  // ---------- Filters ----------
  // Changing a filter runs the search again right away.
  document.querySelectorAll("[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () { form.submit(); });
  });

  // ---------- Map ----------
  var mapElement = document.getElementById("caregiver-map");
  var data = JSON.parse(document.getElementById("caregiver-map-data").textContent);
  if (!mapElement || typeof L === "undefined") return;

  var map = L.map(mapElement, { scrollWheelZoom: false }).setView([40.7128, -74.006], 11);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    // OpenStreetMap blocks tile requests without a Referer, and Django's
    // default Referrer-Policy (same-origin) sends none to other sites.
    // Send just our origin (e.g. http://127.0.0.1:8000), never the page URL.
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  var bounds = [];
  if (data.origin) {
    var here = [data.origin.latitude, data.origin.longitude];
    L.circleMarker(here, { radius: 8, color: "#1c1a1a", fillColor: "#f4a27a", fillOpacity: 1, weight: 2 })
      .addTo(map).bindTooltip("You searched here");
    bounds.push(here);
  }

  data.points.forEach(function (point) {
    var spot = [point.latitude, point.longitude];
    var marker = L.marker(spot).addTo(map);
    var link = document.createElement("a");
    link.href = point.url;
    link.textContent = point.name;
    marker.bindPopup(link);
    var card = document.getElementById("caregiver-" + point.id);
    marker.on("click", function () {
      if (!card) return;
      document.querySelectorAll(".caregiver-result.is-highlighted").forEach(function (c) {
        c.classList.remove("is-highlighted");
      });
      card.classList.add("is-highlighted");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    if (card) {
      card.addEventListener("mouseenter", function () { marker.openPopup(); });
    }
    bounds.push(spot);
  });

  if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
  else if (bounds.length === 1) map.setView(bounds[0], 13);
})();
