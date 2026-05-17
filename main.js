/* Hirosuke Asahi — shared front-end */

// ---------- Nav: mobile toggle + scroll state ----------
(() => {
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.querySelector('.primary-nav');
    const topbar = document.querySelector('.topbar');

    if (toggle && nav) {
        toggle.addEventListener('click', () => {
            nav.classList.toggle('is-open');
            toggle.classList.toggle('is-open');
        });

        nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
            nav.classList.remove('is-open');
            toggle.classList.remove('is-open');
        }));
    }

    if (topbar) {
        const onScroll = () => {
            if (window.scrollY > 24) topbar.classList.add('is-solid');
            else topbar.classList.remove('is-solid');
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }
})();

// ---------- Landing: hero background carousel ----------
(() => {
    const imgs = document.querySelectorAll('.hero-bg__img');
    if (imgs.length < 2) return;
    let i = 0;
    setInterval(() => {
        imgs[i].classList.remove('is-active');
        i = (i + 1) % imgs.length;
        imgs[i].classList.add('is-active');
    }, 7000);
})();

// ---------- News card: expand/collapse ----------
(() => {
    const card = document.querySelector('.news-card');
    const btn = document.querySelector('[data-toggle="news"]');
    if (!card || !btn) return;
    const labelEl = btn.querySelector('.label');
    btn.addEventListener('click', () => {
        const open = card.classList.toggle('is-open');
        if (labelEl) labelEl.textContent = open ? 'Show less' : 'Show more';
    });
})();

// ---------- Profile: collapsible publications ----------
(() => {
    document.querySelectorAll('[data-collapsible-trigger]').forEach(btn => {
        const targetId = btn.getAttribute('data-collapsible-trigger');
        const target = document.getElementById(targetId);
        if (!target) return;
        const labelEl = btn.querySelector('.label');
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const open = target.classList.toggle('is-open');
            btn.classList.toggle('is-open');
            if (labelEl) labelEl.textContent = open ? 'Show less' : 'Show more';
        });
    });
})();

// ---------- Detail page: lightbox ----------
(() => {
    const lb = document.querySelector('.lightbox');
    if (!lb) return;
    const lbImg = lb.querySelector('img');
    document.querySelectorAll('[data-lightbox]').forEach(img => {
        img.addEventListener('click', () => {
            lbImg.src = img.src;
            lb.classList.add('is-open');
        });
    });
    lb.addEventListener('click', () => lb.classList.remove('is-open'));
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') lb.classList.remove('is-open');
    });
})();

// ---------- Hero news: auto-populate from publications ----------
// Reads <li> items inside #publications .ach-list, sorts by year
// (then original DOM order), and renders the top N into
// <ul class="hero-news__list" data-auto-news>.
// To change how many items appear, edit HERO_NEWS_COUNT.
(() => {
    const HERO_NEWS_COUNT = 3;

    const list = document.querySelector('.hero-news__list[data-auto-news]');
    const updatedEl = document.querySelector('.hero-news__updated');
    const pubs = document.querySelectorAll('#publications .ach-list > li');
    if (!list || !pubs.length) return;

    const escapeHTML = (s) => String(s).replace(/[&<>"]/g, c =>
        ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c])
    );

    const items = Array.from(pubs).map((li, idx) => {
        const venue = (li.querySelector('.ach__venue')?.textContent || '')
            .replace(/\s+/g, ' ').trim();
        const titleEl = li.querySelector('.ach__title');
        const title = (titleEl?.textContent || '').trim();
        const titleHTML = titleEl ? titleEl.innerHTML : escapeHTML(title);
        const typeText = (li.querySelector('.ach__type')?.textContent || '')
            .replace(/\s+/g, ' ').trim();

        const yearMatch = venue.match(/(20\d{2})/);
        const monthMatch = venue.match(/(20\d{2})[\.\s·\-\/]+(\d{1,2})\b/);
        const year = yearMatch ? parseInt(yearMatch[1], 10) : 0;
        const month = monthMatch ? parseInt(monthMatch[2], 10) : 0;

        // venue without trailing year for sub-line
        const venueClean = venue.replace(/[·\s]*\d{4}.*$/, '').replace(/[·\s]+$/, '').trim();

        return { idx, year, month, title, titleHTML, venue, venueClean, typeText };
    });

    items.sort((a, b) => {
        if (b.year !== a.year) return b.year - a.year;
        if (b.month !== a.month) return b.month - a.month;
        return a.idx - b.idx;  // stable: keep author's ordering inside a year
    });

    const top = items.slice(0, HERO_NEWS_COUNT);

    list.innerHTML = top.map(item => {
        const dateLabel = item.month
            ? `${item.year}.${String(item.month).padStart(2, '0')}`
            : `${item.year}`;
        return `<li>
            <time>${escapeHTML(dateLabel)}</time>
            <a href="#publications">
                ${item.titleHTML}
                <span class="jp">${escapeHTML(item.venueClean)}</span>
            </a>
        </li>`;
    }).join('');

    if (updatedEl && top[0]) {
        const dl = top[0].month
            ? `${top[0].year}.${String(top[0].month).padStart(2, '0')}`
            : `${top[0].year}`;
        updatedEl.textContent = `Updated ${dl}`;
    }
})();

// ---------- Reveal on scroll ----------
(() => {
    if (!('IntersectionObserver' in window)) return;
    const els = document.querySelectorAll('[data-reveal]');
    if (!els.length) return;
    const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-revealed');
                io.unobserve(entry.target);
            }
        });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.05 });
    els.forEach(el => io.observe(el));
})();
