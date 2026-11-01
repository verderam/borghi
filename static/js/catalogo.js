(() => {
  const normalize = (value) => (value || '').toLocaleLowerCase('it').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();

  function initCatalogue() {
    const form = document.querySelector('#filtri');
    const grid = document.querySelector('#griglia-idee');
    if (!form || !grid || form.dataset.catalogueReady === 'true') return;
    form.dataset.catalogueReady = 'true';

    const cards = [...grid.querySelectorAll('.idea-card')];
    const search = document.querySelector('#cerca');
    const category = document.querySelector('#categoria');
    const investment = document.querySelector('#investimento');
    const effort = document.querySelector('#impegno');
    const order = document.querySelector('#ordine');
    const results = document.querySelector('#risultati');
    const empty = document.querySelector('#nessun-risultato');
    const emptyReset = document.querySelector('#azzera-vuoto');
    const fields = [search, category, investment, effort, order];

    function applyFilters() {
      const q = normalize(search.value);
      const selectedCategory = category.value;
      const selectedInvestment = normalize(investment.value);
      const selectedEffort = normalize(effort.value);
      const ordered = [...cards].sort((a, b) => {
        if (order.value === 'titolo') return a.dataset.title.localeCompare(b.dataset.title, 'it');
        return Number(a.dataset.number) - Number(b.dataset.number);
      });

      let visible = 0;
      ordered.forEach((card) => {
        const matches = (!q || normalize(card.dataset.search).includes(q)) &&
          (!selectedCategory || card.dataset.category === selectedCategory) &&
          (!selectedInvestment || normalize(card.dataset.investment).includes(selectedInvestment)) &&
          (!selectedEffort || normalize(card.dataset.impegno).includes(selectedEffort));
        card.hidden = !matches;
        if (matches) visible += 1;
        grid.appendChild(card);
      });

      results.innerHTML = `<strong>${visible}</strong> ${visible === 1 ? 'idea trovata' : 'idee trovate'}`;
      empty.hidden = visible !== 0;
      grid.hidden = visible === 0;
    }

    function resetFilters() {
      search.value = '';
      category.value = '';
      investment.value = '';
      effort.value = '';
      order.value = 'documento';
      applyFilters();
      search.focus();
    }

    const params = new URLSearchParams(location.search);
    search.value = params.get('q') || '';
    category.value = params.get('categoria') || '';
    investment.value = params.get('investimento') || '';
    effort.value = params.get('impegno') || '';
    order.value = params.get('ordine') === 'titolo' ? 'titolo' : 'documento';
    applyFilters();

    form.addEventListener('submit', (event) => event.preventDefault());
    form.addEventListener('reset', (event) => {
      event.preventDefault();
      resetFilters();
    });
    fields.forEach((field) => field.addEventListener(field === search ? 'input' : 'change', () => applyFilters()));
    emptyReset.addEventListener('click', resetFilters);
  }

  window.BorghiCatalogue = { init: initCatalogue };

  if (!window.BorghiCatalogueKeyboard) {
    window.BorghiCatalogueKeyboard = true;
    document.addEventListener('keydown', (event) => {
      const search = document.querySelector('#cerca');
      if (!search) return;
      const target = event.target;
      const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target.isContentEditable;
      if (event.key === '/' && !typing) {
        event.preventDefault();
        search.focus();
      }
      if (event.key === 'Escape' && document.activeElement === search && search.value) {
        search.value = '';
        search.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
  }

  initCatalogue();
})();
