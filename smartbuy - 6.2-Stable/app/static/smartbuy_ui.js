(() => {
  "use strict";

  // Highlights the current route without changing backend routes or permissions.
  const currentPath = window.location.pathname.replace(/\/$/, "") || "/";
  const links = [...document.querySelectorAll("aside nav a[href]")];
  const candidates = links
    .map(link => ({ link, path: new URL(link.href, window.location.origin).pathname.replace(/\/$/, "") || "/" }))
    .filter(item => currentPath === item.path || (item.path !== "/" && currentPath.startsWith(`${item.path}/`)))
    .sort((a, b) => b.path.length - a.path.length);

  if (candidates[0]) {
    candidates[0].link.classList.add("is-active");
    candidates[0].link.setAttribute("aria-current", "page");
  }

  // Optional dismiss buttons: <button data-sbu-dismiss>...</button>
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-sbu-dismiss]");
    if (!button) return;
    const target = button.closest(".sbu-alert, [data-sbu-dismissible]");
    if (target) target.remove();
  });
})();
