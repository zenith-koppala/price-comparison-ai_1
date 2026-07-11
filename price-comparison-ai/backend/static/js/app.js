const STORE_COLORS = {
  "Amazon": "#1F3A5F",
  "Flipkart": "#C8801A",
  "Croma": "#17915F",
  "Reliance Digital": "#8B5CF6",
  "Tata Cliq": "#D63384",
};

// Original, simple line-icon set (no external assets) + a tinted tile color per category.
const CATEGORY_STYLE = {
  "Electronics": {
    bg: "#E8EEF5", fg: "#1F3A5F",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 13v-1a8 8 0 0 1 16 0v1"/>
      <rect x="2.5" y="13" width="5" height="7" rx="2"/>
      <rect x="16.5" y="13" width="5" height="7" rx="2"/>
    </svg>`,
  },
  "Mobiles": {
    bg: "#E1F3F4", fg: "#0E7C86",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <rect x="6" y="2.5" width="12" height="19" rx="2.5"/>
      <line x1="10" y1="19" x2="14" y2="19"/>
    </svg>`,
  },
  "Laptops": {
    bg: "#ECE9F9", fg: "#4C3FA8",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <rect x="4" y="4" width="16" height="10.5" rx="1.5"/>
      <path d="M2 19.5h20l-2-4H4l-2 4Z"/>
    </svg>`,
  },
  "Home Appliances": {
    bg: "#FBEEE0", fg: "#B15C1E",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3.5" y="2.5" width="17" height="19" rx="2"/>
      <circle cx="12" cy="13.5" r="5"/>
      <circle cx="12" cy="13.5" r="2"/>
      <line x1="7" y1="5.5" x2="8.6" y2="5.5"/>
    </svg>`,
  },
  "Fashion": {
    bg: "#FBE7F0", fg: "#B0356B",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 3 L3 6.5 5.5 10 8 8.5 V21 H16 V8.5 L18.5 10 21 6.5 16 3 C16 4.5 14.2 5.5 12 5.5 C9.8 5.5 8 4.5 8 3Z"/>
    </svg>`,
  },
  "Gaming": {
    bg: "#EFE6FC", fg: "#6D28D9",
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6.5 8.5h11a4 4 0 0 1 4 4.4l-.5 3.6a2.3 2.3 0 0 1-4.2 1L15 15.5H9l-1.8 2a2.3 2.3 0 0 1-4.2-1L2.5 12.9a4 4 0 0 1 4-4.4Z"/>
      <line x1="7" y1="11" x2="7" y2="13.5"/>
      <line x1="5.7" y1="12.25" x2="8.3" y2="12.25"/>
      <circle cx="17" cy="11" r="0.8" fill="currentColor" stroke="none"/>
      <circle cx="15" cy="13" r="0.8" fill="currentColor" stroke="none"/>
    </svg>`,
  },
};

function ratingStars(rating) {
  const full = Math.round(rating);
  return "★".repeat(full) + "☆".repeat(5 - full);
}

const grid = document.getElementById("productGrid");
const cardTemplate = document.getElementById("cardTemplate");
const searchInput = document.getElementById("searchInput");
const categoryNav = document.getElementById("categoryNav");
const drawer = document.getElementById("drawer");
const drawerBackdrop = document.getElementById("drawerBackdrop");
const drawerContent = document.getElementById("drawerContent");
const drawerClose = document.getElementById("drawerClose");

let activeCategory = "All";
let activeSort = "";
let chartInstance = null;
let compareChart = null;
let currentDrawerProductId = null;
const compareSet = new Set();
const recCache = {}; // product_id -> recommendation result, fetched lazily for sparkline badges

const sortSelect = document.getElementById("sortSelect");
sortSelect.addEventListener("change", () => {
  activeSort = sortSelect.value;
  loadProducts();
});

function currency(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

async function loadCategories() {
  const res = await fetch("/api/categories");
  const cats = await res.json();
  cats.forEach(cat => {
    const btn = document.createElement("button");
    btn.className = "cat-btn";
    btn.textContent = cat;
    btn.dataset.cat = cat;
    btn.addEventListener("click", () => {
      activeCategory = cat;
      document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      loadProducts();
    });
    categoryNav.appendChild(btn);
  });
  categoryNav.querySelector('[data-cat="All"]').addEventListener("click", () => {
    activeCategory = "All";
    document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
    categoryNav.querySelector('[data-cat="All"]').classList.add("active");
    loadProducts();
  });
}

function buildSparkline(svgEl, points) {
  if (!points || points.length < 2) return;
  const values = points.map(p => p.price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 100, h = 28, pad = 2;
  const step = (w - pad * 2) / (values.length - 1);
  const coords = values.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const trendUp = values[values.length - 1] > values[0];
  const color = trendUp ? "#C8801A" : "#17915F";
  svgEl.innerHTML = `<polyline points="${coords.join(" ")}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />`;
}

async function loadProducts() {
  const search = searchInput.value;
  const params = new URLSearchParams({ search, category: activeCategory, sort: activeSort });
  const res = await fetch(`/api/products?${params.toString()}`);
  const products = await res.json();

  grid.innerHTML = "";
  document.getElementById("statProducts").textContent = products.length;

  if (products.length === 0) {
    grid.innerHTML = `<div class="empty-state">No products match “${search}”. Try another search.</div>`;
    return;
  }

  for (const p of products) {
    const node = cardTemplate.content.cloneNode(true);
    const card = node.querySelector(".card");
    const style = CATEGORY_STYLE[p.category] || { bg: "#EEE", fg: "#555", svg: "" };

    const tile = node.querySelector(".card-icon-tile");
    tile.style.background = style.bg;
    const iconEl = node.querySelector(".card-icon");
    iconEl.style.color = style.fg;
    iconEl.innerHTML = style.svg;

    node.querySelector(".card-cat").textContent = p.category;
    node.querySelector(".card-title").textContent = p.name;
    node.querySelector(".card-rating-stars").textContent = ratingStars(p.rating);
    node.querySelector(".card-rating-num").textContent = `${p.rating.toFixed(1)} (${p.review_count.toLocaleString("en-IN")})`;
    node.querySelector(".card-price").textContent = currency(p.best_price);
    if (p.mrp && p.mrp > p.best_price) {
      node.querySelector(".card-mrp").textContent = currency(p.mrp);
      node.querySelector(".card-discount").textContent = `${Math.round(p.discount_pct)}% off`;
    }
    node.querySelector(".card-store").textContent = "at " + p.best_store;

    const checkbox = node.querySelector(".card-compare-checkbox");
    checkbox.checked = compareSet.has(p.product_id);
    checkbox.addEventListener("click", e => e.stopPropagation());
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        if (compareSet.size >= 3) {
          checkbox.checked = false;
          alert("You can compare up to 3 products at a time.");
          return;
        }
        compareSet.add(p.product_id);
      } else {
        compareSet.delete(p.product_id);
      }
      updateCompareBar();
    });
    node.querySelector(".card-compare").addEventListener("click", e => e.stopPropagation());

    card.addEventListener("click", () => openDrawer(p.product_id));
    card.addEventListener("keypress", e => { if (e.key === "Enter") openDrawer(p.product_id); });
    grid.appendChild(node);
  }

  // Second pass: attach sparklines + BUY/WAIT badges (batched to avoid layout thrash)
  const cardEls = grid.querySelectorAll(".card");
  products.forEach((p, i) => {
    fetch(`/api/products/${p.product_id}`).then(r => r.json()).then(detail => {
      const series = detail.history[p.best_store] || [];
      const svg = cardEls[i].querySelector(".sparkline");
      buildSparkline(svg, series);
    });
    fetch(`/api/products/${p.product_id}/recommendation?store=${encodeURIComponent(p.best_store)}`)
      .then(r => r.json())
      .then(rec => {
        const badge = cardEls[i].querySelector(".card-badge");
        const isBuy = rec.recommendation === "BUY_NOW";
        badge.textContent = isBuy ? "BUY NOW" : "WAIT — price may drop";
        badge.classList.add(isBuy ? "buy" : "wait");
      });
  });
}

async function openDrawer(productId) {
  currentDrawerProductId = productId;
  const res = await fetch(`/api/products/${productId}`);
  const data = await res.json();
  const recRes = await fetch(`/api/products/${productId}/recommendation?store=${encodeURIComponent(data.cheapest_store)}`);
  const rec = await recRes.json();

  const isBuy = rec.recommendation === "BUY_NOW";

  const storeRows = Object.entries(data.prices)
    .sort((a, b) => a[1] - b[1])
    .map(([store, price]) => `
      <div class="store-row ${store === data.cheapest_store ? "cheapest" : ""}">
        <span>${store}${store === data.cheapest_store ? " · cheapest" : ""}</span>
        <span class="price">${currency(price)}</span>
      </div>
    `).join("");

  drawerContent.innerHTML = `
    <div class="drawer-cat">${data.product.category}</div>
    <h2>${data.product.name}</h2>

    <div class="rec-panel ${isBuy ? "buy" : "wait"}">
      <span class="rec-dot"></span>
      <div>
        <div class="rec-text-title">${isBuy ? "Buy now" : "Wait — a better deal is likely"}</div>
        <div class="rec-text-sub">${rec.reason} (model confidence ${(rec.confidence * 100).toFixed(0)}%)</div>
      </div>
    </div>

    <div class="store-list">${storeRows}</div>

    <button class="btn-watch" id="watchToggleBtn">☆ Track this price</button>
    <div class="watch-form" id="watchForm">
      <label>Alert me when the price drops to or below</label>
      <input type="number" id="watchTargetPrice" placeholder="e.g. ${Math.round(data.prices[data.cheapest_store] * 0.9)}" />
      <label>Email (optional — leave blank to just track it here)</label>
      <input type="email" id="watchEmail" placeholder="you@example.com" />
      <button id="watchSubmitBtn">Start tracking</button>
    </div>

    <div class="chart-wrap">
      <h4>60-day price history by store</h4>
      <canvas id="priceChart" height="220"></canvas>
    </div>
  `;

  drawer.classList.add("open");
  drawerBackdrop.classList.add("open");

  const ctx = document.getElementById("priceChart");
  const labels = Object.values(data.history)[0]?.map(pt => pt.date) || [];
  const datasets = Object.entries(data.history).map(([store, series]) => ({
    label: store,
    data: series.map(pt => pt.price),
    borderColor: STORE_COLORS[store] || "#999",
    backgroundColor: "transparent",
    tension: 0.25,
    pointRadius: 0,
    borderWidth: 2,
  }));

  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
      scales: {
        x: { ticks: { maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { font: { size: 10 } } },
      },
    },
  });

  document.getElementById("watchToggleBtn").addEventListener("click", () => {
    document.getElementById("watchForm").classList.toggle("open");
  });
  document.getElementById("watchSubmitBtn").addEventListener("click", async () => {
    const target = parseFloat(document.getElementById("watchTargetPrice").value);
    const email = document.getElementById("watchEmail").value.trim();
    if (!target || target <= 0) {
      alert("Enter a valid target price.");
      return;
    }
    await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: currentDrawerProductId, target_price: target, email: email || null }),
    });
    const btn = document.getElementById("watchToggleBtn");
    btn.textContent = "★ Tracking this price";
    document.getElementById("watchForm").classList.remove("open");
    refreshWatchlistCount();
  });
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerBackdrop.classList.remove("open");
  watchlistDrawer.classList.remove("open");
}
drawerClose.addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);

const watchlistDrawer = document.getElementById("watchlistDrawer");
const watchlistNavBtn = document.getElementById("watchlistNavBtn");
const watchlistClose = document.getElementById("watchlistClose");
const watchlistItemsEl = document.getElementById("watchlistItems");
const checkAlertsBtn = document.getElementById("checkAlertsBtn");

async function refreshWatchlistCount() {
  const res = await fetch("/api/watchlist");
  const items = await res.json();
  document.getElementById("watchlistCount").textContent = items.length ? `(${items.length})` : "";
  return items;
}

async function renderWatchlist() {
  const items = await refreshWatchlistCount();
  if (items.length === 0) {
    watchlistItemsEl.innerHTML = `<div class="empty-state">Nothing tracked yet. Open a product and click “Track this price.”</div>`;
    return;
  }
  watchlistItemsEl.innerHTML = items.map(item => `
    <div class="watch-item ${item.target_hit ? "hit" : ""}">
      <div class="watch-item-top">
        <div>
          <div class="watch-item-name">${item.name}</div>
          <div class="watch-item-prices">Current: ${currency(item.current_price)} at ${item.current_store} &nbsp;·&nbsp; Target: ${currency(item.target_price)}</div>
          ${item.target_hit ? `<span class="watch-item-hit-badge">Target hit \u2713</span>` : ""}
        </div>
        <button class="watch-item-remove" data-id="${item.id}" title="Remove">&times;</button>
      </div>
    </div>
  `).join("");

  watchlistItemsEl.querySelectorAll(".watch-item-remove").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/watchlist/${btn.dataset.id}`, { method: "DELETE" });
      renderWatchlist();
    });
  });
}

watchlistNavBtn.addEventListener("click", () => {
  closeDrawer();
  watchlistDrawer.classList.add("open");
  drawerBackdrop.classList.add("open");
  renderWatchlist();
});
watchlistClose.addEventListener("click", closeDrawer);

checkAlertsBtn.addEventListener("click", async () => {
  checkAlertsBtn.textContent = "Checking...";
  const res = await fetch("/api/watchlist/check-alerts", { method: "POST" });
  const data = await res.json();
  checkAlertsBtn.textContent = "Check for price drops now";
  if (data.triggered.length === 0) {
    alert("No target prices hit yet — still tracking.");
  } else {
    alert(`${data.triggered.length} price drop(s) found! Check the list below.`);
  }
  renderWatchlist();
});

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadProducts, 250);
});

loadCategories().then(loadProducts);
refreshWatchlistCount();

// ---------- Compare feature ----------
const compareBar = document.getElementById("compareBar");
const compareBarText = document.getElementById("compareBarText");
const compareBarBtn = document.getElementById("compareBarBtn");
const compareBarClear = document.getElementById("compareBarClear");
const compareDrawer = document.getElementById("compareDrawer");
const compareBackdrop = document.getElementById("compareBackdrop");
const compareClose = document.getElementById("compareClose");
const compareContent = document.getElementById("compareContent");

function updateCompareBar() {
  const n = compareSet.size;
  compareBarText.textContent = n === 0 ? "0 selected" : `${n} selected — pick up to 3 to compare`;
  compareBarBtn.disabled = n < 2;
  compareBar.classList.toggle("visible", n > 0);
  // keep checkboxes in sync when navigating back to the grid
  document.querySelectorAll(".card-compare-checkbox").forEach(cb => {
    // no-op placeholder; sync happens per-render in loadProducts
  });
}

compareBarClear.addEventListener("click", () => {
  compareSet.clear();
  updateCompareBar();
  loadProducts();
});

compareBarBtn.addEventListener("click", async () => {
  const ids = Array.from(compareSet).join(",");
  const res = await fetch(`/api/products/compare?ids=${ids}`);
  const items = await res.json();
  renderCompare(items);
  closeDrawer();
  compareDrawer.classList.add("open");
  compareBackdrop.classList.add("open");
});

function renderCompare(items) {
  const allStores = [...new Set(items.flatMap(i => Object.keys(i.prices)))];

  const rows = allStores.map(store => {
    const cells = items.map(item => {
      const price = item.prices[store];
      const isCheapest = store === item.cheapest_store;
      return `<td class="${isCheapest ? "compare-cheapest" : ""}">${price ? currency(price) : "—"}${isCheapest ? " ✓" : ""}</td>`;
    }).join("");
    return `<tr><th>${store}</th>${cells}</tr>`;
  }).join("");

  const header = items.map(item => `
    <th>
      <div class="compare-col-name">${item.name}</div>
      <div style="font-size:12px;color:var(--ink-muted)">${ratingStars(item.rating)} ${item.rating.toFixed(1)}</div>
      <div style="margin-top:4px;font-size:11px;font-weight:700;color:${item.recommendation === "BUY_NOW" ? "var(--buy)" : "var(--wait)"}">
        ${item.recommendation === "BUY_NOW" ? "BUY NOW" : "WAIT"} (${(item.confidence * 100).toFixed(0)}%)
      </div>
    </th>
  `).join("");

  compareContent.innerHTML = `
    <table class="compare-table">
      <thead><tr><th></th>${header}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function closeCompareDrawer() {
  compareDrawer.classList.remove("open");
  compareBackdrop.classList.remove("open");
}
compareClose.addEventListener("click", closeCompareDrawer);
compareBackdrop.addEventListener("click", closeCompareDrawer);
