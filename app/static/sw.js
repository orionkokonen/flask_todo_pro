// このファイルは、オフラインでも一部の画面を使えるようにする仕組みです。
/* Service Worker（PWA のオフライン対応）
   - 静的ファイル: キャッシュ優先（cache-first）で高速表示
   - 画面遷移（HTML）: ネットワーク優先（network-first）で常に最新を返す
*/

// キャッシュ仕様を変えたら、キャッシュ名も上げて古い資産を入れ替える。
const CACHE_NAME = "todo-pro-v4";

// “アプリの骨格”だけをプリキャッシュ。
// Bootstrap をローカル配信に切り替えたため、UI に必要な vendor 資産も含める。
const CORE_ASSETS = [
  "/",
  "/offline.html",
  "/static/css/app.css",
  "/static/js/app.js?v=20260304-2",
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

// install: 初回登録時に CORE_ASSETS をまとめてキャッシュに保存する。
// skipWaiting() で旧バージョンの待機を飛ばし、新 SW をすぐ有効にする。
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// activate: バージョンが上がったとき、古いキャッシュを削除して新しいものに切り替える。
// clients.claim() で既に開いているタブにも新 SW を即座に適用する。
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

// --- ヘルパー関数群: リクエスト種別の判定とキャッシュ戦略 ---

function isNavigationRequest(request) {
  return request.mode === "navigate";
}

function isStaticRequest(url) {
  return url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest";
}

// 自作 JS/CSS/manifest は更新頻度が高いため、vendor と区別する。
function isMutableStaticRequest(url) {
  return (
    url.pathname.startsWith("/static/js/") ||
    url.pathname.startsWith("/static/css/") ||
    url.pathname === "/manifest.webmanifest"
  );
}

// レスポンスが正常ならキャッシュに保存し、次回以降オフラインでも使えるようにする。
function cacheResponse(request, response) {
  if (!response || !response.ok) {
    return response;
  }

  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
  return response;
}

// ネットワーク優先戦略: まずサーバーに問い合わせ、失敗したらキャッシュを使う。
function networkFirst(request, options = {}) {
  const { ignoreSearch = false, offlineFallback = null } = options;

  return fetch(request)
    .then((response) => cacheResponse(request, response))
    .catch(() =>
      // ignoreSearch=true にすると `?v=...` の違いを無視して同じ資産として探せる。
      // CSS/JS の版番号付きURLでもキャッシュを再利用しやすくするための設定。
      caches.match(request, { ignoreSearch }).then(
        (cached) => cached || (offlineFallback ? caches.match(offlineFallback) : undefined)
      )
    );
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // POST などの変更系リクエストはキャッシュ戦略の対象外にする。
  if (request.method !== "GET") {
    return;
  }

  // 1) HTML（画面遷移）は network-first
  if (isNavigationRequest(request)) {
    event.respondWith(networkFirst(request, { offlineFallback: "/offline.html" }));
    return;
  }

  // 2) 自作の JS/CSS/manifest は network-first で更新を優先する。
  if (isStaticRequest(url)) {
    if (isMutableStaticRequest(url)) {
      event.respondWith(networkFirst(request, { ignoreSearch: true }));
      return;
    }

    // 3) vendor やアイコンなど、更新頻度の低い静的ファイルは cache-first。
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => cacheResponse(request, response));
      })
    );
    return;
  }

  // 4) それ以外は基本 network（失敗したらキャッシュがあれば返す）
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
