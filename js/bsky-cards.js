/* bsky-cards.js — Bluesky post-card overlay for the presentation.
 *
 * Reads the JSON embedded in the slide as <script id="bsky-posts"
 * type="application/json"> and builds <article class="bsky-card"> elements
 * inside the slide's <div class="bsky-field">. Cards pop in over ~0.45s and
 * fade out so each lives ~5s; the driver staggers them 3s apart and only
 * runs while the slide is `.present` (reveal.js events restart the cycle).
 *
 * Styling lives in css/theme-override.css (§ "Bluesky post cards").
 */

(() => {
  const dataEl = document.getElementById("bsky-posts");
  if (!dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  const field = document.querySelector(".bsky-field");
  if (!field) return;
  const section = field.closest("section");

  // [x%, y%, tilt°] — spread around the slide edges, deterministic
  const SPOTS = [
    [4, 6, -2], [56, 4, 2], [76, 22, -1.5], [30, 12, 1.5],
    [10, 34, 1], [68, 48, -2], [40, 68, 2], [6, 78, -1],
    [78, 74, 1.5], [26, 52, -1], [52, 30, -2], [18, 66, 2],
    [64, 84, -1.5], [44, 84, 1],
  ];
  const fmt = (n) =>
    n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n);

  const cards = data.posts.map((post, i) => {
    const card = document.createElement("article");
    card.className = "bsky-card";
    const [x, y, tilt] = SPOTS[i % SPOTS.length];
    card.style.left = x + "%";
    card.style.top = y + "%";
    card.style.setProperty("--tilt", tilt + "deg");

    const head = document.createElement("header");
    const av = document.createElement("img");
    av.className = "bsky-avatar";
    av.alt = "";
    if (post.author.avatar) av.src = post.author.avatar;
    av.onerror = () => {
      const f = document.createElement("span");
      f.className = "bsky-avatar bsky-fallback";
      f.textContent = post.author.displayName[0];
      av.replaceWith(f);
    };
    const who = document.createElement("div");
    who.className = "bsky-who";
    const name = document.createElement("strong");
    name.textContent = post.author.displayName;
    const meta = document.createElement("span");
    meta.className = "bsky-meta";
    meta.textContent = "@" + post.author.handle + " · " + post.date;
    who.append(name, meta);
    head.append(av, who);
    const body = document.createElement("p");
    body.textContent = post.text;
    const foot = document.createElement("footer");
    foot.textContent = "♥ " + fmt(post.likes) + "   ⇄ " + fmt(post.reposts);
    card.append(head, body, foot);
    return card;
  });
  cards.forEach((c) => field.appendChild(c));

  const STAGGER = 3000, LIFE = 5000, OUT = 1600;
  const pending = new Set();
  const later = (fn, ms) => {
    const t = setTimeout(() => { pending.delete(t); fn(); }, ms);
    pending.add(t);
  };
  const show = (card) => {
    card.style.transitionDuration = "450ms";
    card.classList.add("bsky-show");
    later(() => {
      card.style.transitionDuration = OUT + "ms";
      card.classList.remove("bsky-show");
    }, LIFE - OUT);
  };
  const reset = () => {
    pending.forEach(clearTimeout);
    pending.clear();
    for (const c of cards) {
      c.style.transitionDuration = "0ms";
      c.classList.remove("bsky-show");
    }
  };
  let idx = 0, timer = null;
  const tick = () => {
    if (idx >= cards.length) { reset(); idx = 0; }
    show(cards[idx++]);
  };
  const start = () => {
    if (timer) return;
    reset();
    idx = 0;
    tick();
    timer = setInterval(tick, STAGGER);
  };
  const stop = () => { clearInterval(timer); timer = null; };
  const active = () => section.classList.contains("present");
  const entered = (slide) => slide === section || slide.contains(section);
  document.addEventListener("slidechanged", (e) =>
    entered(e.target) ? start() : stop());
  document.addEventListener("ready", () => active() && start());
  setTimeout(() => active() && start(), 800);
})();
