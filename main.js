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

// ---------- Works cascade: per-card image slideshow ----------
(() => {
    const groups = document.querySelectorAll('.cascade__slides[data-slides]');
    if (!groups.length) return;
    groups.forEach((group, cardIdx) => {
        const imgs = group.querySelectorAll('img');
        if (imgs.length < 2) return;
        let i = 0;
        setTimeout(() => {
            setInterval(() => {
                imgs[i].classList.remove('is-active');
                i = (i + 1) % imgs.length;
                imgs[i].classList.add('is-active');
            }, 4000);
        }, cardIdx * 900);
    });
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

// ---------- Detail page: lightbox with arrow navigation ----------
// Used on works/workN-details.html. Every image with [data-lightbox]
// becomes a thumbnail; clicking one opens the lightbox at that image
// and ArrowLeft / ArrowRight (or the on-screen chevrons) walk through
// the full set with wrap-around.
(() => {
    const lb = document.querySelector('.lightbox');
    if (!lb) return;
    const lbImg = lb.querySelector('img');
    const thumbs = Array.from(document.querySelectorAll('[data-lightbox]'));
    if (!thumbs.length) return;

    // Lazily add the prev / next / counter chrome if the page's lightbox
    // markup predates the arrow version
    let lbPrev = lb.querySelector('.lightbox__nav--prev');
    let lbNext = lb.querySelector('.lightbox__nav--next');
    let lbCount = lb.querySelector('.lightbox__counter');
    if (!lbPrev) {
        lbPrev = document.createElement('button');
        lbPrev.type = 'button';
        lbPrev.className = 'lightbox__nav lightbox__nav--prev';
        lbPrev.setAttribute('aria-label', 'Previous photo');
        lbPrev.textContent = '‹';
        lb.appendChild(lbPrev);
    }
    if (!lbNext) {
        lbNext = document.createElement('button');
        lbNext.type = 'button';
        lbNext.className = 'lightbox__nav lightbox__nav--next';
        lbNext.setAttribute('aria-label', 'Next photo');
        lbNext.textContent = '›';
        lb.appendChild(lbNext);
    }
    if (!lbCount) {
        lbCount = document.createElement('span');
        lbCount.className = 'lightbox__counter';
        lbCount.setAttribute('aria-hidden', 'true');
        lb.appendChild(lbCount);
    }

    const photos = thumbs.map(t => ({
        src: t.getAttribute('src'),
        alt: t.getAttribute('alt') || '',
    }));
    let idx = 0;

    const show = () => {
        const p = photos[idx];
        lbImg.src = p.src;
        lbImg.alt = p.alt;
        lbCount.textContent = `${idx + 1} / ${photos.length}`;
        const multi = photos.length > 1;
        lbPrev.hidden = !multi;
        lbNext.hidden = !multi;
        lbCount.hidden = !multi;
    };
    const nav = (delta) => {
        idx = (idx + delta + photos.length) % photos.length;
        show();
    };

    thumbs.forEach((t, i) => {
        t.addEventListener('click', () => { idx = i; show(); lb.classList.add('is-open'); });
    });
    lbPrev.addEventListener('click', (e) => { e.stopPropagation(); nav(-1); });
    lbNext.addEventListener('click', (e) => { e.stopPropagation(); nav( 1); });
    lbImg.addEventListener('click', (e) => e.stopPropagation());
    lb.addEventListener('click', () => lb.classList.remove('is-open'));
    document.addEventListener('keydown', (e) => {
        if (!lb.classList.contains('is-open')) return;
        if (e.key === 'Escape')          lb.classList.remove('is-open');
        else if (e.key === 'ArrowRight') nav( 1);
        else if (e.key === 'ArrowLeft')  nav(-1);
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

// ---------- Abstract language switch (EN ↔ JP) ----------
// On a Works detail page: the abstract has both languages in the DOM and a
// small `EN / JP` toggle. Choice persists in localStorage so visitors who
// prefer Japanese don't have to switch on every page.
(() => {
    const containers = document.querySelectorAll('[data-lang-container]');
    if (!containers.length) return;

    const STORAGE_KEY = 'abstract-lang';
    const defaultLang = (navigator.language || 'en').toLowerCase().startsWith('ja') ? 'jp' : 'en';
    let lang = localStorage.getItem(STORAGE_KEY) || defaultLang;

    const applyLang = () => {
        containers.forEach(container => {
            // If this container has no JP block, force EN
            const hasJp = container.querySelector('[data-lang="jp"].detail-abstract__text');
            const effective = hasJp ? lang : 'en';
            container.querySelectorAll('[data-lang]').forEach(el => {
                if (el.classList.contains('lang-switch')) return;      // the button itself
                if (el.parentElement && el.parentElement.classList.contains('lang-switch')) {
                    el.classList.toggle('is-active', el.dataset.lang === effective);
                    return;
                }
                el.hidden = el.dataset.lang !== effective;
            });
            container.querySelectorAll('.lang-switch').forEach(btn => {
                btn.hidden = !hasJp;
            });
        });
    };

    document.querySelectorAll('.lang-switch').forEach(btn => {
        btn.addEventListener('click', () => {
            lang = (lang === 'en') ? 'jp' : 'en';
            localStorage.setItem(STORAGE_KEY, lang);
            applyLang();
        });
    });

    applyLang();
})();

// ---------- Lite YouTube embed (click to play) ----------
// The iframe is injected only on click. On file:// previews YouTube refuses to
// embed entirely, so there we open the video on YouTube instead of erroring.
(() => {
    document.querySelectorAll('.video-frame[data-youtube]').forEach(frame => {
        const id = frame.dataset.youtube;
        const play = () => {
            if (location.protocol === 'file:') {
                window.open('https://www.youtube.com/watch?v=' + id, '_blank', 'noopener');
                return;
            }
            if (frame.querySelector('iframe')) return;
            const iframe = document.createElement('iframe');
            iframe.src = 'https://www.youtube.com/embed/' + id + '?autoplay=1';
            iframe.title = frame.getAttribute('aria-label') || 'Video';
            iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
            iframe.allowFullscreen = true;
            frame.innerHTML = '';
            frame.appendChild(iframe);
        };
        frame.addEventListener('click', play);
        frame.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play(); }
        });
    });
})();
