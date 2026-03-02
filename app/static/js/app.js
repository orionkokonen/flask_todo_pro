// アプリ全体で使う共通 JS をまとめたモジュール。
// IIFE（即時実行関数）でスコープを閉じて、グローバル変数の汚染を防ぐ。
(function(){
  const any = (sel) => document.querySelector(sel);
  const all = (sel) => Array.from(document.querySelectorAll(sel));

  // セレクトボックスの値が変わったらフィルターフォームを自動送信する。
  const filterForm = any('#filterForm');
  if (filterForm) {
    all('#filterForm select').forEach(el => {
      el.addEventListener('change', () => filterForm.submit());
    });
  }

  // data-confirm 属性を持つフォームの送信前に確認ダイアログを表示する。
  // 以前はテンプレートに onsubmit="return confirm(...)" を直書きしていたが、
  // CSP の 'unsafe-inline' を script-src から外すためにこちらへ集約した。
  // フォームに data-confirm="メッセージ" を付けるだけで確認ダイアログを有効化できる。
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  }, true);

  // Bootstrap のツールチップ（ホバー時の補足説明）を初期化・有効化する。
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  });

  // PWA: Service Worker を登録してオフライン対応とキャッシュ戦略を有効にする。
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function (err) {
        console.warn('ServiceWorker registration failed:', err);
      });
    });
  }
})();
