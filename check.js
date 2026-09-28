const puppeteer = require('puppeteer-core');
(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    defaultViewport: { width: 1280, height: 720 }
  });
  const page = await browser.newPage();
  await page.goto('file:///Users/joey/Workspace/github.com/jdc-pub/monktoberfest-2026/dist/presentation.html', { waitUntil: 'networkidle0' });
  const n = await page.evaluate(() => Reveal.getTotalSlides());
  for (let i = 0; i < n; i++) {
    await page.evaluate(idx => Reveal.slide(idx), i);
    await new Promise(r => setTimeout(r, 150));
    const out = await page.evaluate(() => {
      const s = Reveal.getCurrentSlide();
      const r = s.getBoundingClientRect();
      const res = { id: s.id || s.className, cls: s.className,
        top: Math.round(r.top), h: Math.round(r.height),
        inlineTop: s.style.top, styleH: s.style.height,
        disp: getComputedStyle(s).display, scrollH: s.scrollHeight };
      const h2 = s.querySelector(':scope > h2');
      if (h2) { const hr = h2.getBoundingClientRect(); res.h2Top = Math.round(hr.top); res.h2RelTop = Math.round(hr.top - r.top); }
      return res;
    });
    console.log(JSON.stringify(out));
  }
  await browser.close();
})();
