(() => {
  if (!window.InstantClick) return;

  const progress = () => document.querySelector('.navigation-progress');
  const setLoading = (loading) => {
    document.body.classList.toggle('is-navigating', loading);
    const bar = progress();
    if (bar) bar.setAttribute('aria-hidden', 'true');
  };

  const initialisePage = (initialLoad) => {
    setLoading(false);
    if (window.BorghiCatalogue) window.BorghiCatalogue.init();
    if (initialLoad) return;

    const heading = document.querySelector('h1');
    const status = document.querySelector('#navigazione-stato');
    if (status && heading) status.textContent = `Pagina caricata: ${heading.textContent.trim()}`;

    const hashTarget = location.hash ? document.getElementById(location.hash.slice(1)) : null;
    const focusTarget = hashTarget || document.querySelector('#contenuto');
    if (focusTarget) {
      if (!focusTarget.hasAttribute('tabindex')) focusTarget.setAttribute('tabindex', '-1');
      focusTarget.focus({ preventScroll: true });
    }
  };

  InstantClick.on('wait', () => setLoading(true));
  InstantClick.on('exit', () => setLoading(false));
  InstantClick.on('restore', () => initialisePage(true));
  InstantClick.on('change', (initialLoad) => initialisePage(initialLoad));
  InstantClick.init('mousedown');
})();
