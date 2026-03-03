/* Service Worker（PWA のオフライン対応）
   - 静的ファイル: キャッシュ優先（cache-first）で高速表示
   - 画面遷移（HTML）: ネットワーク優先（network-first）で常に最新を返す
*/

const CACHE_NAME = "todo-pro-v2";

// “アプリの骨格”だけをプリキャッシュ。
// Bootstrap をローカル配信に切り替えたため、UI に必要な vendor 資産も含める。
const CORE_ASSETS = [
  "/",
  "/offline.html",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/vendor/bootstrap/bootstrap.min.css",
  "/static/vendor/bootstrap/bootstrap.bundle.min.js",
  "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
  "/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
  "/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/maskable-192.png",
  "/static/icons/maskable-512.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isNavigationRequest(request) {
  return request.mode === "navigate";
}

function isStaticRequest(url) {
  return url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest";
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1) HTML（画面遷移）は network-first
  if (isNavigationRequest(request)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches
            .match(request)
            .then((cached) => cached || caches.match("/offline.html"))
        )
    );
    return;
  }

  // 2) 静的ファイルは cache-first
  if (isStaticRequest(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        });
      })
    );
    return;
  }

  // 3) それ以外は基本 network（失敗したらキャッシュがあれば返す）
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
