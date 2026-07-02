const STORE_COLORS = {
  "Amazon": "#1F3A5F",
  "Flipkart": "#C8801A",
  "Croma": "#17915F",
  "Reliance Digital": "#8B5CF6",
};

const grid = document.getElementById("productGrid");
const cardTemplate = document.getElementById("cardTemplate");
const searchInput = document.getElementById("searchInput");
const categoryNav = document.getElementById("categoryNav");
const drawer = document.getElementById("drawer");
const drawerBackdrop = document.getElementById("drawerBackdrop");
const drawerContent = document.getElementById("drawerContent");
const drawerClose = document.getElementById("drawerClose");

let activeCategory = "All";
let chartInstance = null;
const recCache = {}; // product_id -> recommendation result, fetched lazily for sparkline badges

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
  const params = new URLSearchParams({ search, category: activeCategory });
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
    node.querySelector(".card-cat").textContent = p.category;
    node.querySelector(".card-title").textContent = p.name;
    node.querySelector(".card-price").textContent = currency(p.best_price);
    node.querySelector(".card-store").textContent = "at " + p.best_store;
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
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerBackdrop.classList.remove("open");
}
drawerClose.addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadProducts, 250);
});

loadCategories().then(loadProducts);
