# Scraping bot-gated SPAs with Playwright attached to the real Chrome over CDP

The problem: automating a site behind **Cloudflare** ("Verify you are human" / managed challenge) or **reCAPTCHA**
(v2 checkbox or v3 score). A normal automated browser trips these:
- Playwright's own bundled Chromium launched via `chromium.launch()` sets `navigator.webdriver = true` and other
  automation fingerprints — Cloudflare/reCAPTCHA flag it and show a challenge.
- Injection-based extensions (e.g. a DOM-injection MCP browser) time out entirely on heavy SPAs that never reach
  `document_idle` — they wait for an idle that never comes.

## The technique: launch real Chrome yourself, then only *connect* over CDP

Do **not** let Playwright launch the browser. Instead:

1. Launch the **system Google Chrome** yourself with a debug port and a dedicated profile:
   ```
   chrome.exe --remote-debugging-port=9222 --user-data-dir=<throwaway-profile> --no-first-run --no-default-browser-check <url>
   ```
   (macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; Linux: `google-chrome`.)
2. Attach Playwright with `playwright-core` (not `playwright` — avoids the browser download):
   ```js
   import { chromium } from "playwright-core";
   const browser = await chromium.connectOverCDP("http://localhost:9222");
   const page = browser.contexts()[0].pages().find(p => p.url().includes("…")) ?? await browser.contexts()[0].newPage();
   // browser.close() detaches CDP; it does NOT close the user's Chrome.
   ```

Because Chrome was launched **without** Playwright's automation switches (no `--enable-automation`) and Playwright
only *connects*, `navigator.webdriver` stays **false**. Cloudflare's managed challenge and reCAPTCHA v3 then treat
it as a genuine browser and pass **with no manual solve** on a warmed profile. Verify with
`await page.evaluate(() => navigator.webdriver)` → should be `false`. `channel: "chrome"` on a `launch()` still
sets the automation flag — only *connect-to-a-manually-launched-Chrome* clears it.

Install just the library, no browser download:
```
npm i playwright-core        # (PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 not even needed; playwright-core has no postinstall)
```
The debug endpoint is browseable: `curl http://localhost:9222/json/version` (up?), `…/json` (tabs).

## The anti-bot boundary (do not cross)

Programmatically bypassing / auto-solving a CAPTCHA or bot check, or adding stealth hacks
(`--disable-blink-features=AutomationControlled`, UA spoofing, `navigator.webdriver` masking) specifically to slip
past detection **unattended**, is prohibited detection-evasion. The allowed pattern is: the browser is **visible**
(headful, on the user's desktop), and if a challenge ever appears a **human solves it in that window**, then the
script resumes. CDP-attach isn't evasion — it's driving the user's genuine browser, which is why the challenge
passes honestly. The persistent `--user-data-dir` remembers any Cloudflare `cf_clearance` cookie for next time.

## Reusable Playwright patterns these SPAs need

- **Native file dialog → `filechooser` event.** Upload widgets (custom `<div>` buttons, drop-zones) open an OS
  dialog you can't drive. Intercept it:
  ```js
  const [chooser] = await Promise.all([ page.waitForEvent("filechooser"), page.locator(".upload-btn").click() ]);
  await chooser.setFiles(absPath);
  ```
  A hidden `<input type=file>` is even simpler: `page.locator('input[type=file]').setInputFiles(path)` works even
  when the input is `display:none` — no need to click the visible button.
- **Flaky / async-navigating clicks → click-then-waitURL-then-reclick.** SPA buttons often register the click but
  navigate a beat later, or no-op during hydration. A single `click()` + `waitForURL()` flakes. Retry:
  ```js
  async function navStep(page, getBtn, urlRe, tries=4) {
    for (let t=0;t<tries;t++){ await clickVisible(getBtn()); try { await page.waitForURL(urlRe,{timeout:12000}); return; } catch { await page.waitForTimeout(800); } }
    throw new Error(`navStep failed ${urlRe}`);
  }
  ```
- **`clickVisible` for responsive duplicates.** SPAs render mobile+desktop copies of a control; a role/text locator
  then hits "strict mode violation" or clicks the hidden one. Iterate `.nth(i)`, pick the first `isVisible() &&
  isEnabled()`, and give `click({timeout})` a bounded timeout + `.catch(()=>false)` so a stuck element doesn't hang
  30 s (the default action timeout) — return false and let `navStep` retry.
- **Count-driven clears, not button-presence.** A "Delete/Clear" button often stays in the DOM **disabled** at zero
  items; looping `while button exists: click` then hangs 30 s waiting for the disabled button to become enabled.
  Loop on the real state (`N items` text → count) instead.
- **Incremental-load lists → wait for the row count to stabilize.** Result lists that stream in (big query, many
  suppliers) will read short if you extract immediately after the first row appears. Poll until the count is
  unchanged across two consecutive polls before extracting, and again after each "Show more".
- **Discovery loop for unknown selectors.** Navigate, `page.screenshot({path})` (Read it back), and dump candidate
  targets (`querySelectorAll` of inputs/buttons/links with tag+class+text) to a JSON file. Iterate. Anchor a card's
  action button by filtering the card container to an exact child text
  (`page.locator('.Card').filter({ has: page.getByText('PLA', {exact:true}) })`) rather than nth-by-order.

## Gotcha: a process-kill filter that matches its own command line

When killing the debug Chrome by a distinguishing marker (e.g. its profile-dir path), a
`Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*my-profile*' }` (or `pgrep`/`grep`) will
**match the very query process running it**, because the pattern string is literally in that command's command
line. You then chase a phantom "N processes still alive" with ever-changing PIDs (each check spawns a new
bash/powershell). Filter on the **process name too** (`$_.Name -eq 'chrome.exe'`) so shell/query processes are
excluded. (This is the classic `ps | grep foo` self-match, one level removed.)
