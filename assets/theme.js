// Giao diện sáng/tối, nhớ lựa chọn giữa các trang (nếu trình duyệt cho phép)
(() => {
  const root = document.documentElement;
  try { const t = localStorage.getItem('uh-theme'); if (t) root.dataset.theme = t; } catch (e) {}
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('uh-theme', root.dataset.theme); } catch (e) {}
      document.dispatchEvent(new CustomEvent('themechange'));
    });
  });
})();
