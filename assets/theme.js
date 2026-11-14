// Giao diện sáng/tối, nhớ lựa chọn giữa các trang (nếu trình duyệt cho phép)
(() => {
  const root = document.documentElement;
  try { const t = localStorage.getItem('uh-theme'); if (t) root.dataset.theme = t; } catch (e) {}
  document.addEventListener('DOMContentLoaded', () => {
    // Thanh điều hướng cuộn ngang trên điện thoại: đưa mục đang mở vào giữa khung
    const nav = document.querySelector('nav.parts'), curA = nav && nav.querySelector('[aria-current="page"]');
    if (nav && curA && nav.scrollWidth > nav.clientWidth){
      const a = curA.getBoundingClientRect(), n = nav.getBoundingClientRect();
      nav.scrollLeft += (a.left + a.width / 2) - (n.left + n.width / 2);
    }
    const btn = document.getElementById('themeBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('uh-theme', root.dataset.theme); } catch (e) {}
      document.dispatchEvent(new CustomEvent('themechange'));
    });
  });
})();
