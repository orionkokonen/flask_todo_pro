// アプリ全体で使う共通 JS をまとめたモジュール。
// IIFE（即時実行関数）でスコープを閉じて、グローバル変数の汚染を防ぐ。
(function(){
  // よく使う DOM 取得を短く書くための小さなヘルパー。
  // 処理本体の意図を読みやすくし、毎回同じ長い式を書かないために置いている。
  const any = (sel) => document.querySelector(sel);
  const all = (sel) => Array.from(document.querySelectorAll(sel));
  // js-task-card-link クラスを持つカード要素をクリック可能領域として扱うためのセレクター。
  const cardLinkSelector = '.js-task-card-link';
  // カード内にある操作系の子要素（リンク・ボタン・フォーム等）を列挙するセレクター。
  // これらをクリックしたときはカード遷移を起こさず、元の動作（フォーム送信など）を優先する。
  const interactiveSelector = [
    'a',
    'button',
    'form',
    'input',
    'select',
    'textarea',
    'label',
    '[data-bs-toggle="dropdown"]',
    '.dropdown-menu',
  ].join(',');

  const getElementTarget = (target) => target instanceof Element ? target : null;
  // クリックされた要素が js-task-card-link の内側かを判定する。
  const getClickableCard = (target) => {
    const elementTarget = getElementTarget(target);
    if (!elementTarget) return null;
    return elementTarget.closest(cardLinkSelector);
  };
  // クリックされた要素がリンク・ボタン・フォームなど操作系の要素か判定する。
  const isInteractiveTarget = (target) => {
    const elementTarget = getElementTarget(target);
    if (!elementTarget) return false;
    return Boolean(elementTarget.closest(interactiveSelector));
  };
  // カードの data-detail-url に保持した URL へブラウザ遷移する。
  const navigateToCard = (card) => {
    if (!(card instanceof HTMLElement)) return;

    const detailUrl = card.dataset.detailUrl;
    if (detailUrl) {
      window.location.assign(detailUrl);
    }
  };

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

  // カードの余白をクリックしても詳細へ移動できるようにする。
  // ボタン・リンクなどの操作要素は除外し、修飾キー（Ctrl/Cmd など）付きクリックも除外することで
  // 「新しいタブで開く」操作などブラウザ標準の挙動を妨げない。
  document.addEventListener('click', (event) => {
    const card = getClickableCard(event.target);
    if (!card || isInteractiveTarget(event.target)) return;
    if (event.defaultPrevented) return;
    if (event instanceof MouseEvent && (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)) {
      return;
    }

    navigateToCard(card);
  });

  // キーボード操作でもカード自体を詳細リンクとして扱えるようにする。
  document.addEventListener('keydown', (event) => {
    const card = getClickableCard(event.target);
    if (!card || event.target !== card) return;
    if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return;

    event.preventDefault();
    navigateToCard(card);
  });

  // Bootstrap のツールチップ（ホバー時の補足説明）を初期化・有効化する。
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  });

  // PWA: Service Worker を登録してオフライン対応とキャッシュ戦略を有効にする。
  // updateViaCache: 'none' でブラウザの HTTP キャッシュに引っ張られにくくし、
  // sw.js の更新チェック時に古い内容を掴み続けるリスクを下げる。
  // registration.update() は登録後の更新確認だけを担当させ、失敗ログも登録失敗とは分けて出す。
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
        .then(function (registration) {
          registration.update().catch(function (err) {
            console.warn('ServiceWorker update check failed:', err);
          });
        })
        .catch(function (err) {
          console.warn('ServiceWorker registration failed:', err);
        });
    });
  }
})();
