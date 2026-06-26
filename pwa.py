import streamlit.components.v1 as components


def inject_pwa() -> None:
    """Inject PWA manifest, meta tags, and service worker into the Streamlit app."""
    components.html(
        """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<script>
(function () {
  const doc = window.parent.document;

  if (doc.getElementById("sky-pwa-manifest")) return;

  const manifest = doc.createElement("link");
  manifest.id = "sky-pwa-manifest";
  manifest.rel = "manifest";
  manifest.href = "/app/static/manifest.json";
  doc.head.appendChild(manifest);

  const metas = [
    { name: "theme-color", content: "#818CF8" },
    { name: "mobile-web-app-capable", content: "yes" },
    { name: "apple-mobile-web-app-capable", content: "yes" },
    { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
    { name: "apple-mobile-web-app-title", content: "Sky Orders" },
    { name: "application-name", content: "Sky Orders" },
  ];

  metas.forEach(({ name, content }) => {
    if (doc.querySelector(`meta[name="${name}"]`)) return;
    const meta = doc.createElement("meta");
    meta.name = name;
    meta.content = content;
    doc.head.appendChild(meta);
  });

  if (!doc.querySelector('link[rel="apple-touch-icon"]')) {
    const appleIcon = doc.createElement("link");
    appleIcon.rel = "apple-touch-icon";
    appleIcon.href = "/app/static/icon-192.png";
    doc.head.appendChild(appleIcon);
  }

  const swCode = `
    const CACHE = "sky-order-converter-v1";
    const PRECACHE = [
      "/app/static/manifest.json",
      "/app/static/icon-192.png",
      "/app/static/icon-512.png",
      "/app/static/offline.html",
    ];

    self.addEventListener("install", (event) => {
      event.waitUntil(
        caches.open(CACHE).then((cache) => cache.addAll(PRECACHE))
      );
      self.skipWaiting();
    });

    self.addEventListener("activate", (event) => {
      event.waitUntil(
        caches.keys().then((keys) =>
          Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
      );
      self.clients.claim();
    });

    self.addEventListener("fetch", (event) => {
      if (event.request.method !== "GET") return;

      event.respondWith(
        fetch(event.request)
          .then((response) => {
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(CACHE).then((cache) => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() =>
            caches.match(event.request).then(
              (cached) => cached || caches.match("/app/static/offline.html")
            )
          )
      );
    });
  `;

  if ("serviceWorker" in window.parent.navigator) {
    const blob = new Blob([swCode], { type: "application/javascript" });
    const swUrl = URL.createObjectURL(blob);
    window.parent.navigator.serviceWorker
      .register(swUrl, { scope: "/" })
      .then(() => URL.revokeObjectURL(swUrl))
      .catch((err) => console.warn("Sky PWA service worker registration failed:", err));
  }
})();
</script>
</body>
</html>
        """,
        height=0,
        width=0,
    )
