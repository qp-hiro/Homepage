/* Hirosuke Asahi — site chatbot (client-side retrieval, no external API)
   ─────────────────────────────────────────────────────────────────────
   • Fully static: matches visitor questions against a built-in knowledge
     base (Japanese + English) and answers in the language of the question.
   • Publications / awards / latest-news answers are parsed live from
     index.html's #publications section, so the weekly auto-update routine
     keeps this bot current with zero extra work.
   • Include with:  <script src="chatbot.js" defer></script>
     (from works/ subpages: <script src="../chatbot.js" defer></script>)
*/
(() => {
    'use strict';

    /* ---------- Paths (resolve relative to this script file) ---------- */
    const SCRIPT_URL = document.currentScript ? document.currentScript.src : 'chatbot.js';
    const INDEX_URL = new URL('index.html', SCRIPT_URL).href;
    const ROOT = (p) => new URL(p, SCRIPT_URL).href;

    /* ---------- Utilities ---------- */
    const escapeHTML = (s) => String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const isJapanese = (s) => /[぀-ヿ㐀-鿿]/.test(s);

    const normalize = (s) => s
        .toLowerCase()
        .replace(/[？?！!。、．，,.\s]+/g, ' ')
        .trim();

    /* ---------- Live publication data (parsed from index.html) ---------- */
    let pubCache = null;

    async function loadPublications() {
        if (pubCache) return pubCache;
        try {
            const res = await fetch(INDEX_URL);
            const html = await res.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const groups = [];
            doc.querySelectorAll('#publications .ach-group').forEach(g => {
                const title = (g.querySelector('.ach-group__title > span')?.textContent || '').trim();
                const items = Array.from(g.querySelectorAll('.ach-list > li')).map(li => {
                    const venue = (li.querySelector('.ach__venue')?.textContent || '').replace(/\s+/g, ' ').trim();
                    const yearMatch = venue.match(/(20\d{2})/);
                    return {
                        title: (li.querySelector('.ach__title')?.textContent || '').replace(/\s+/g, ' ').trim(),
                        venue: venue.replace(/[·\s]*(DOI|Video|Link)(\s*(DOI|Video|Link))*\s*$/, '').trim(),
                        year: yearMatch ? parseInt(yearMatch[1], 10) : 0
                    };
                });
                groups.push({ title, items });
            });
            if (groups.length) pubCache = groups;
            return pubCache;
        } catch (e) {
            return null;
        }
    }

    const findGroup = (groups, re) => groups.find(g => re.test(g.title));

    const fmtItems = (items, max) => '<ul class="hcb-list">' + items.slice(0, max).map(it =>
        `<li>${escapeHTML(it.title)}<span class="hcb-venue">${escapeHTML(it.venue)}</span></li>`
    ).join('') + '</ul>';

    async function answerPublications(jp) {
        const groups = await loadPublications();
        if (!groups) {
            return jp
                ? `研究業績は<a href="${ROOT('index.html')}#publications">Publicationsセクション</a>と<a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a>をご覧ください。`
                : `Please see the <a href="${ROOT('index.html')}#publications">Publications section</a> or <a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a>.`;
        }
        const intl = findGroup(groups, /international/i);
        const dome = findGroup(groups, /domestic/i);
        let out = jp ? '主な研究業績です:' : 'Selected publications:';
        if (intl) {
            out += `<p class="hcb-sub">${jp ? '国際会議(査読あり)' : 'International (peer-reviewed)'} · ${intl.items.length}${jp ? '件' : ''}</p>` + fmtItems(intl.items, 5);
        }
        if (dome) {
            out += `<p class="hcb-sub">${jp ? '国内学会' : 'Domestic conferences'} · ${dome.items.length}${jp ? '件' : ''}</p>` + fmtItems(dome.items, 3);
        }
        out += jp
            ? `<p>一覧は<a href="${ROOT('index.html')}#publications">Publications</a>と<a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a>へ。</p>`
            : `<p>Full list: <a href="${ROOT('index.html')}#publications">Publications</a> · <a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a>.</p>`;
        return out;
    }

    async function answerAwards(jp) {
        const groups = await loadPublications();
        const awards = groups && findGroup(groups, /award/i);
        if (!awards) {
            return jp
                ? `受賞歴は<a href="${ROOT('index.html')}#publications">Publicationsセクション</a>のAwardsをご覧ください。`
                : `Please see the Awards group in the <a href="${ROOT('index.html')}#publications">Publications section</a>.`;
        }
        return (jp ? `受賞歴 (${awards.items.length}件):` : `Awards (${awards.items.length}):`) + fmtItems(awards.items, 8);
    }

    async function answerNews(jp) {
        const groups = await loadPublications();
        if (!groups) {
            return jp
                ? `最新情報はトップページの Latest News をご覧ください。`
                : `Please see the Latest News panel on the top page.`;
        }
        const all = groups.flatMap(g => g.items).sort((a, b) => b.year - a.year);
        return (jp ? '最近の活動です:' : 'Recent activity:') + fmtItems(all, 4);
    }

    /* ---------- Knowledge base ---------- */
    /* Each entry: keys (substrings, JP) / words (whole-word English), jp / en answers.
       Answers may be a string or an async function (jp) => html. */
    const KB = [
        {
            id: 'greeting',
            keys: ['こんにちは', 'こんばんは', 'はじめまして', 'やあ', 'おはよう'],
            words: ['hello', 'hi', 'hey', 'good morning', 'good evening'],
            jp: 'こんにちは!旭博佑(あさひ ひろすけ)についての質問にお答えします。研究内容・経歴・業績・作品・連絡先など、気軽に聞いてください。',
            en: "Hello! I can answer questions about Hirosuke Asahi — his research, career, publications, works, and how to contact him. Feel free to ask."
        },
        {
            id: 'thanks',
            keys: ['ありがとう', '助かった', 'どうも'],
            words: ['thanks', 'thank you', 'thx'],
            jp: 'どういたしまして!他にも知りたいことがあれば聞いてください。',
            en: "You're welcome! Ask me anything else about him."
        },
        {
            id: 'who',
            keys: ['誰', 'だれ', '何者', 'どんな人', '自己紹介', 'について教えて', 'プロフィール', '紹介して'],
            words: ['who', 'about him', 'profile', 'introduce', 'introduction', 'bio'],
            jp: '旭博佑(あさひ ひろすけ)は、東京大学 先端科学技術研究センター(RCAST)に在籍する博士課程の研究者です。2000年福岡生まれ。人の身体感覚や運動に介入し、それらを再設計することで新しい体験を生み出す研究(情報身体学・HCI・VR・ロボティクス)に取り組んでいます。',
            en: 'Hirosuke Asahi is a doctoral researcher at RCAST, The University of Tokyo. Born in Fukuoka in 2000, he works on Information Somatics, HCI, VR, and Robotics — intervening in human bodily sensation and movement, and redesigning them to create new kinds of experience.'
        },
        {
            id: 'research',
            keys: ['研究', 'テーマ', '専門', '分野', '何をして', 'なにをして'],
            words: ['research', 'study', 'studies', 'field', 'topic', 'work on', 'somatics', 'hci', 'haptics'],
            jp: '研究分野は情報身体学・HCI・VR・ロボティクスです。人の身体感覚や運動に介入・再設計することで新しい体験を生み出すことを目指しており、VR/AR、ハプティクス、バイオメカニクス、運動学習、AIなど幅広い領域にまたがります。「拡張された身体は知覚や行為をいかに変えるのか」という問いに、実装と展示を通じて取り組んでいます。',
            en: 'His fields are Information Somatics, HCI, VR, and Robotics. His work spans VR/AR, haptics, biomechanics, motor learning, and AI, asking how a computationally extended body reshapes perception and action — explored through working systems and exhibitions.'
        },
        {
            id: 'affiliation',
            keys: ['所属', '大学', '研究室', 'ラボ', 'どこの', '職位'],
            words: ['affiliation', 'university', 'lab', 'position', 'rcast', 'tokyo'],
            jp: '所属は東京大学 先端科学技術研究センター(RCAST)、先端学際工学専攻の博士課程1年です(2025年4月〜)。稲見昌彦教授らとの共著研究を多く発表しています。',
            en: 'He is a 1st-year doctoral student in Advanced Interdisciplinary Studies at RCAST, The University of Tokyo (since April 2025), frequently co-authoring with Prof. Masahiko Inami and colleagues.'
        },
        {
            id: 'career',
            keys: ['経歴', '学歴', '出身校', '高校', '学部', '修士', '博士'],
            words: ['career', 'education', 'background', 'degree', 'history', 'school'],
            jp: '経歴:<ul class="hcb-list"><li>2016–2019 久留米附設高等学校</li><li>2019–2023 東京大学 工学部 精密工学科(学士)</li><li>2023–2025 東京大学大学院 情報理工学系研究科(修士)</li><li>2025– 東京大学大学院 先端学際工学専攻 博士課程(在籍中)</li></ul>',
            en: 'Career:<ul class="hcb-list"><li>2016–2019 Kurume Fusetsu High School</li><li>2019–2023 B.S. Precision Engineering, The University of Tokyo</li><li>2023–2025 M.S. Information Physics &amp; Computing, The University of Tokyo</li><li>2025– Doctoral course, Advanced Interdisciplinary Studies, UTokyo RCAST (current)</li></ul>'
        },
        {
            id: 'publications',
            keys: ['業績', '論文', '発表', '出版', '学会'],
            words: ['publication', 'publications', 'paper', 'papers', 'conference'],
            fn: answerPublications
        },
        {
            id: 'awards',
            keys: ['受賞', '賞', 'アワード'],
            words: ['award', 'awards', 'prize', 'honor'],
            fn: answerAwards
        },
        {
            id: 'news',
            keys: ['ニュース', '最新', '最近', '近況', 'アップデート'],
            words: ['news', 'latest', 'recent', 'update', 'updates', 'new'],
            fn: answerNews
        },
        {
            id: 'works',
            keys: ['作品', 'プロジェクト', 'デモ', '展示', '聖剣', 'ゴーグル'],
            words: ['works', 'project', 'projects', 'demo', 'exhibition', 'goggles', 'forcefield', 'sword'],
            jp: `代表的な作品:<ul class="hcb-list"><li><a href="${ROOT('works/work1-details.html')}">The Legend of Holy Sword(聖剣を継ぐ者)</a> — 集中を証明するマルチモーダルVR体験 (2023)</li><li><a href="${ROOT('works/work2-details.html')}">ForceField</a> — 床と深度センシングによる物体間相互作用の可視化 (2023)</li><li><a href="${ROOT('works/work3-details.html')}">Semantic See-through Goggles</a> — 視界を一度言語に変換し再画像化するゴーグル (2024)</li></ul><a href="${ROOT('works.html')}">作品一覧はこちら</a>。`,
            en: `Selected works:<ul class="hcb-list"><li><a href="${ROOT('works/work1-details.html')}">The Legend of Holy Sword</a> — a multimodal VR proof of concentration (2023)</li><li><a href="${ROOT('works/work2-details.html')}">ForceField</a> — visualising intermaterial force via floor &amp; depth sensing (2023)</li><li><a href="${ROOT('works/work3-details.html')}">Semantic See-through Goggles</a> — glasses that turn the view into text and re-scenify it (2024)</li></ul>See the <a href="${ROOT('works.html')}">Works page</a>.`
        },
        {
            id: 'skills',
            keys: ['スキル', '技能', 'プログラミング', '技術', '得意'],
            words: ['skill', 'skills', 'programming', 'tech stack', 'unity', 'python'],
            jp: '技術スキル:<ul class="hcb-list"><li>熟練 — Python / C / C# / C++ / HTML・CSS / Arduino / 3D CAD / Unity</li><li>中級 — JavaScript / MySQL / ROS / 機械学習</li><li>初級 — Blender / Houdini</li></ul>',
            en: 'Technical skills:<ul class="hcb-list"><li>Advanced — Python, C, C#, C++, HTML/CSS, Arduino, 3D CAD, Unity</li><li>Intermediate — JavaScript, MySQL, ROS, Machine Learning</li><li>Beginner — Blender, Houdini</li></ul>'
        },
        {
            id: 'languages',
            keys: ['言語', '何語', '英語', '中国語', 'スペイン語', '話せ'],
            words: ['language', 'languages', 'speak', 'english', 'chinese', 'spanish'],
            jp: '日本語(母語)・英語・中国語・スペイン語を話します。幼少期を日本と中国の両国で過ごしました。',
            en: 'He speaks Japanese (native), English, Chinese, and Spanish. He spent his childhood in both Japan and China.'
        },
        {
            id: 'contact',
            keys: ['連絡', 'メール', 'コンタクト', '問い合わせ', '共同研究', '依頼', '取材'],
            words: ['contact', 'email', 'mail', 'reach', 'collaboration', 'collaborate', 'inquiry'],
            jp: `連絡はメールでどうぞ: <a href="mailto:hirosuke.asahi@star.rcast.u-tokyo.ac.jp">hirosuke.asahi@star.rcast.u-tokyo.ac.jp</a><br>共同研究・取材などのご相談も歓迎です。SNSは<a href="${ROOT('index.html')}#contact">Contactセクション</a>にまとまっています。`,
            en: `The best way is email: <a href="mailto:hirosuke.asahi@star.rcast.u-tokyo.ac.jp">hirosuke.asahi@star.rcast.u-tokyo.ac.jp</a><br>Collaboration and media inquiries are welcome. Social links are in the <a href="${ROOT('index.html')}#contact">Contact section</a>.`
        },
        {
            id: 'sns',
            keys: ['github', 'ギットハブ', 'インスタ', 'youtube', 'ユーチューブ', 'note', 'facebook', 'sns', 'スカラー'],
            words: ['github', 'instagram', 'youtube', 'facebook', 'note', 'scholar', 'social'],
            jp: 'リンク:<ul class="hcb-list"><li><a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a></li><li><a href="https://github.com/qp-hiro" target="_blank" rel="noopener">GitHub (qp-hiro)</a></li><li><a href="https://www.instagram.com/hiro.asahi.00/" target="_blank" rel="noopener">Instagram</a></li><li><a href="https://www.youtube.com/channel/UCP0LKD8eFH5t-28rO6rThuA" target="_blank" rel="noopener">YouTube</a></li><li><a href="https://note.com/qp_blueberry" target="_blank" rel="noopener">note</a></li></ul>',
            en: 'Links:<ul class="hcb-list"><li><a href="https://scholar.google.com/citations?hl=ja&user=YPA6TZ4AAAAJ" target="_blank" rel="noopener">Google Scholar</a></li><li><a href="https://github.com/qp-hiro" target="_blank" rel="noopener">GitHub (qp-hiro)</a></li><li><a href="https://www.instagram.com/hiro.asahi.00/" target="_blank" rel="noopener">Instagram</a></li><li><a href="https://www.youtube.com/channel/UCP0LKD8eFH5t-28rO6rThuA" target="_blank" rel="noopener">YouTube</a></li><li><a href="https://note.com/qp_blueberry" target="_blank" rel="noopener">note</a></li></ul>'
        },
        {
            id: 'origin',
            keys: ['出身', '生まれ', '福岡', '年齢', '何歳', 'いつ生まれ'],
            words: ['born', 'from', 'age', 'old', 'hometown', 'fukuoka'],
            jp: '2000年、福岡県福岡市生まれです。幼少期は日本と中国の両国で過ごしました。現在の拠点は東京です。',
            en: 'He was born in Fukuoka, Japan in 2000, spent his childhood across Japan and China, and is now based in Tokyo.'
        },
        {
            id: 'fellowship',
            keys: ['フェロー', '奨学', '資金', 'gx'],
            words: ['fellowship', 'funding', 'grant', 'gx'],
            jp: '東京大学「グリーントランスフォーメーション (GX) を先導する高度人材育成プログラム」のフェローです(2025.04–2028.03)。',
            en: 'He is a fellow of the UTokyo GX (Green Transformation) Advanced Human Resource Development Program (2025.04–2028.03).'
        },
        {
            id: 'cv',
            keys: ['履歴書', '職務経歴'],
            words: ['cv', 'resume', 'curriculum vitae'],
            jp: `CV(履歴書)は<a href="${ROOT('CV_template.pdf')}" target="_blank" rel="noopener">こちらのPDF</a>からご覧いただけます。`,
            en: `You can view his CV <a href="${ROOT('CV_template.pdf')}" target="_blank" rel="noopener">here (PDF)</a>.`
        },
        {
            id: 'bot',
            keys: ['あなたは', 'このボット', 'チャットボット', 'ai なの', 'aiです'],
            words: ['are you', 'this bot', 'chatbot', 'what are you'],
            jp: '私はこのサイトに組み込まれた案内ボットです。サイト内の情報(プロフィール・経歴・業績・作品など)をもとに、旭博佑についての質問に自動で答えます。外部への通信は行いません。',
            en: "I'm a small assistant built into this site. I answer questions about Hirosuke Asahi using the information published here (profile, career, publications, works). Nothing you type is sent to any external service."
        }
    ];

    /* ---------- Matching ---------- */
    function match(query) {
        const nq = normalize(query);
        if (!nq) return null;
        let best = null, bestScore = 0;
        for (const entry of KB) {
            let score = 0;
            for (const k of (entry.keys || [])) {
                if (nq.includes(k.toLowerCase())) score += k.length + 2;
            }
            for (const w of (entry.words || [])) {
                const re = new RegExp('(?:^|[^a-z])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:[^a-z]|$)', 'i');
                if (re.test(nq)) score += w.length + 2;
            }
            if (score > bestScore) { bestScore = score; best = entry; }
        }
        return bestScore >= 4 ? best : null;
    }

    async function respond(query) {
        const jp = isJapanese(query);
        const entry = match(query);
        if (!entry) {
            return jp
                ? `すみません、その質問にはうまく答えられませんでした。下の候補から選ぶか、「研究」「経歴」「業績」「作品」「連絡先」などのキーワードで聞いてみてください。直接の質問は<a href="mailto:hirosuke.asahi@star.rcast.u-tokyo.ac.jp">メール</a>でも歓迎です。`
                : `Sorry, I couldn't find a good answer for that. Try keywords like "research", "career", "publications", "works", or "contact" — or <a href="mailto:hirosuke.asahi@star.rcast.u-tokyo.ac.jp">email him directly</a>.`;
        }
        if (entry.fn) return entry.fn(jp);
        return jp ? entry.jp : entry.en;
    }

    /* ---------- Styles ---------- */
    const CSS = `
    .hcb-launcher{position:fixed;right:22px;bottom:22px;z-index:900;width:56px;height:56px;border-radius:50%;
        background:var(--bg-deep,#1c1a17);color:var(--hi-text,#faf6ec);border:1px solid var(--border-dark,rgba(0,0,0,.35));
        display:flex;align-items:center;justify-content:center;cursor:pointer;
        box-shadow:0 8px 24px rgba(0,0,0,.28);transition:transform .25s var(--ease,ease);}
    .hcb-launcher:hover{transform:translateY(-3px);}
    .hcb-launcher svg{width:24px;height:24px;}
    .hcb-panel{position:fixed;right:22px;bottom:90px;z-index:901;width:min(380px,calc(100vw - 32px));
        max-height:min(560px,calc(100vh - 120px));display:none;flex-direction:column;overflow:hidden;
        background:var(--bg-pale,#f7f3ea);border:1px solid var(--border,rgba(28,26,23,.22));
        box-shadow:0 18px 48px rgba(0,0,0,.30);font-family:var(--sans,sans-serif);}
    .hcb-panel.is-open{display:flex;}
    .hcb-head{display:flex;align-items:center;justify-content:space-between;gap:12px;
        padding:14px 18px;background:var(--bg-deep,#1c1a17);color:var(--hi-text,#faf6ec);}
    .hcb-head__title{font-size:14px;letter-spacing:.04em;font-weight:600;}
    .hcb-head__sub{display:block;font-size:10.5px;font-weight:400;opacity:.65;margin-top:2px;}
    .hcb-close{background:none;border:none;color:inherit;font-size:20px;line-height:1;cursor:pointer;opacity:.8;padding:4px;}
    .hcb-close:hover{opacity:1;}
    .hcb-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;}
    .hcb-msg{max-width:86%;padding:10px 13px;font-size:13px;line-height:1.65;word-break:break-word;}
    .hcb-msg--bot{align-self:flex-start;background:var(--bg-elev,#f2eee5);border:1px solid var(--border-soft,rgba(28,26,23,.12));color:var(--text,#1c1a17);}
    .hcb-msg--user{align-self:flex-end;background:var(--bg-deep,#1c1a17);color:var(--hi-text,#faf6ec);}
    .hcb-msg a{color:inherit;text-decoration:underline;text-underline-offset:2px;}
    .hcb-msg--bot a{color:var(--text,#1c1a17);}
    .hcb-list{margin:6px 0 2px;padding-left:18px;}
    .hcb-list li{margin:4px 0;}
    .hcb-venue{display:block;font-size:11px;color:var(--text-muted,#7a7468);}
    .hcb-sub{margin:10px 0 2px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted,#7a7468);}
    .hcb-chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 12px;}
    .hcb-chip{font-size:11.5px;padding:6px 11px;background:var(--bg-soft,#ddd7c7);border:1px solid var(--border-soft,rgba(28,26,23,.12));
        color:var(--text-soft,#4a463f);cursor:pointer;border-radius:999px;transition:background .2s;}
    .hcb-chip:hover{background:var(--surface-hi,rgba(0,0,0,.08));}
    .hcb-inputrow{display:flex;gap:8px;padding:12px 14px;border-top:1px solid var(--border-soft,rgba(28,26,23,.12));background:var(--bg-elev,#f2eee5);}
    .hcb-input{flex:1;border:1px solid var(--border,rgba(28,26,23,.22));background:var(--bg-pale,#f7f3ea);
        color:var(--text,#1c1a17);font-size:13px;padding:9px 12px;outline:none;font-family:inherit;}
    .hcb-input:focus{border-color:var(--accent-line,rgba(28,26,23,.4));}
    .hcb-send{border:none;background:var(--bg-deep,#1c1a17);color:var(--hi-text,#faf6ec);
        font-size:13px;padding:0 16px;cursor:pointer;letter-spacing:.04em;}
    .hcb-send:hover{opacity:.85;}
    .hcb-typing{align-self:flex-start;font-size:12px;color:var(--text-muted,#7a7468);padding:2px 4px;}
    @media (max-width:520px){
        .hcb-panel{right:12px;left:12px;width:auto;bottom:84px;}
        .hcb-launcher{right:16px;bottom:16px;}
    }`;

    /* ---------- UI ---------- */
    function buildUI() {
        const style = document.createElement('style');
        style.textContent = CSS;
        document.head.appendChild(style);

        const launcher = document.createElement('button');
        launcher.className = 'hcb-launcher';
        launcher.setAttribute('aria-label', 'Ask about Hirosuke Asahi / 旭博佑について質問する');
        launcher.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-3.2-.6L3 21l1.7-4.6A8.4 8.4 0 1 1 21 11.5z"/><path d="M8 10h8M8 13.5h5"/></svg>';

        const panel = document.createElement('div');
        panel.className = 'hcb-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Chatbot');
        panel.innerHTML = `
            <div class="hcb-head">
                <div>
                    <span class="hcb-head__title">Ask about Hirosuke <span style="font-weight:400;">/ 旭博佑</span></span>
                    <span class="hcb-head__sub">サイト内情報から自動回答 · answers from this site · EN/日本語 OK</span>
                </div>
                <button class="hcb-close" aria-label="Close">×</button>
            </div>
            <div class="hcb-body"></div>
            <div class="hcb-chips"></div>
            <form class="hcb-inputrow">
                <input class="hcb-input" type="text" maxlength="200"
                    placeholder="質問をどうぞ / Ask a question…" aria-label="Your question">
                <button class="hcb-send" type="submit">送信</button>
            </form>`;

        document.body.appendChild(launcher);
        document.body.appendChild(panel);

        const body = panel.querySelector('.hcb-body');
        const chipsEl = panel.querySelector('.hcb-chips');
        const form = panel.querySelector('.hcb-inputrow');
        const input = panel.querySelector('.hcb-input');

        const addMsg = (html, who) => {
            const div = document.createElement('div');
            div.className = 'hcb-msg hcb-msg--' + who;
            if (who === 'user') div.textContent = html;
            else div.innerHTML = html;
            body.appendChild(div);
            body.scrollTop = body.scrollHeight;
            return div;
        };

        const CHIPS = [
            'どんな研究をしていますか?',
            '経歴を教えて',
            '最近のニュースは?',
            '代表的な業績は?',
            '連絡先は?',
            'What does he research?'
        ];
        CHIPS.forEach(q => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'hcb-chip';
            b.textContent = q;
            b.addEventListener('click', () => ask(q));
            chipsEl.appendChild(b);
        });

        let greeted = false;
        const open = () => {
            panel.classList.add('is-open');
            if (!greeted) {
                greeted = true;
                addMsg('こんにちは!旭博佑についての質問に、このサイトの情報をもとにお答えします。<br>Hi! Ask me anything about Hirosuke Asahi — in Japanese or English.', 'bot');
            }
            input.focus();
        };
        const close = () => panel.classList.remove('is-open');

        launcher.addEventListener('click', () =>
            panel.classList.contains('is-open') ? close() : open());
        panel.querySelector('.hcb-close').addEventListener('click', close);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });

        let busy = false;
        async function ask(q) {
            if (busy || !q.trim()) return;
            busy = true;
            addMsg(q, 'user');
            input.value = '';
            const typing = document.createElement('div');
            typing.className = 'hcb-typing';
            typing.textContent = '…';
            body.appendChild(typing);
            body.scrollTop = body.scrollHeight;
            try {
                const ans = await respond(q);
                typing.remove();
                addMsg(ans, 'bot');
            } catch (e) {
                typing.remove();
                addMsg('Sorry, something went wrong. / エラーが発生しました。', 'bot');
            }
            busy = false;
        }

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            ask(input.value);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', buildUI);
    } else {
        buildUI();
    }
})();
