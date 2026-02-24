(function(){
  const any = (sel) => document.querySelector(sel);
  const all = (sel) => Array.from(document.querySelectorAll(sel));

  // Auto-submit filter form on select change
  const filterForm = any('#filterForm');
  if (filterForm) {
    all('#filterForm select').forEach(el => {
      el.addEventListener('change', () => filterForm.submit());
    });
  }

  // Enable tooltip
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  });
})();
