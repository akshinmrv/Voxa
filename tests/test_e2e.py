"""The console end to end, in a real browser, against the real `voxa serve` (tests/e2e/serve.py)
with only its dubbing pipeline faked (tests/e2e/fake_voxa.py): a preview made from the
Studio's form, its lines checked, changed, saved and voiced; a dub that fails, and Try again;
the Settings search; and axe-core's accessibility rules on every page.

They need the console built (cd web && npm run build:console) and Playwright with a browser
(pip install playwright && python -m playwright install chromium), so they run only when asked:
VOXA_E2E=1 pytest tests/test_e2e.py. VOXA_E2E_CHANNEL=msedge uses the installed Edge instead.
CI runs them in the e2e job."""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HERE = Path(__file__).with_name("e2e")
AXE = REPO / "web" / "node_modules" / "axe-core" / "axe.min.js"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
WAIT = 30_000                                       # ms; a CI runner can be slow

pytestmark = pytest.mark.skipif(os.environ.get("VOXA_E2E") != "1",
                                reason="the console in a browser: set VOXA_E2E=1")


def _api(url, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _upload(url, clip):
    boundary = "voxa-e2e"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{clip.name}\"\r\nContent-Type: video/mp4\r\n\r\n").encode() \
        + clip.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url + "/api/upload", data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["fileId"]


def _until(check, timeout=30.0, what="it"):
    end = time.time() + timeout
    while time.time() < end:
        got = check()
        if got:
            return got
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    if not (REPO / "voxa_ui" / "static" / "en" / "app" / "index.html").exists():
        pytest.fail("the console isn't built: cd web && npm run build:console")
    pytest.importorskip("uvicorn")
    work = tmp_path_factory.mktemp("e2e")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k not in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN", "VOXA_TOKEN")}
    env.update(VOXA_NO_UPDATE_CHECK="1", VOXA_ENGINES_DIR=str(work / "engines"),
               PYTHONUTF8="1")
    log = (work / "server.log").open("w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(HERE / "serve.py"), "--port", str(port)],
                            cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    try:
        _until(lambda: _health(url), timeout=120, what="the server")
        yield url, work
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        log.close()
        if os.environ.get("CI"):
            print((work / "server.log").read_text(encoding="utf-8")[-4000:])


def _health(url):
    try:
        return _api(url, "/api/health")
    except OSError:
        return None


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("VOXA_E2E_CHANNEL") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    ctx =browser.new_context(viewport={"width": 1280, "height": 840}, reduced_motion="reduce")
    ctx.add_init_script("localStorage.setItem('voxa.welcomed', '1')")
    ctx.set_default_timeout(WAIT)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    ctx.close()
    assert not pg.errors, f"errors on the page: {pg.errors}"


def _only_turkish(page):
    """The Studio's languages: Turkish alone, so the form makes one dub."""
    group = page.get_by_role("group", name="Languages")
    turkish = group.get_by_role("button", name=re.compile(r"^Turkish"))
    if turkish.get_attribute("aria-pressed") != "true":
        turkish.click()
    # One at a time: a list taken first goes stale as each is let go.
    others = group.locator("button[aria-pressed=true]").filter(
        has_not_text=re.compile(r"^Turkish"))
    while others.count():
        others.first.click()
    assert group.locator("button[aria-pressed=true]").count() == 1


def test_the_welcome_on_a_first_visit(browser, server):
    url, _ = server
    ctx = browser.new_context(viewport={"width": 1280, "height": 840}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(f"{url}/en/app/")
    dialog = page.get_by_role("dialog")
    dialog.wait_for(timeout=WAIT)
    dialog.get_by_role("button", name="Skip").click()
    page.wait_for_selector("#studio-target", timeout=WAIT)
    assert page.evaluate("localStorage.getItem('voxa.welcomed')") == "1"
    page.reload()
    page.wait_for_selector("#studio-target", timeout=WAIT)
    assert page.get_by_role("dialog").count() == 0          # once is enough
    ctx.close()


def test_a_preview_from_the_studio_checked_saved_and_voiced(page, server):
    url, _ = server
    page.goto(f"{url}/en/app/")
    page.wait_for_selector("#studio-target")
    page.locator("input[type=file]").set_input_files(str(HERE / "clip.mp4"))
    _only_turkish(page)
    page.get_by_role("button", name=re.compile(r"^More")).click()          # its summary follows
    review = page.get_by_role("switch", name="Check the translation before it's voiced")
    if review.get_attribute("aria-checked") != "true":
        review.click()
    page.get_by_role("button", name="Preview the first 20 s").click()

    # Its page, stopped for review once the lines are translated.
    page.wait_for_url(re.compile(r"/app/jobs/view/\?id="))
    job_id = page.url.split("id=")[1].split("&")[0]
    job = _until(lambda: (j := _api(url, f"/api/jobs/{job_id}"))["status"] in (
        "review", "done", "failed") and j, what="the translation")
    assert job["status"] == "review", job
    assert job["config"]["preview"] == 20
    page.get_by_text("Waiting for you to check the translation.").wait_for()
    assert job["config"]["targetLang"] == "tr"

    # Every line, with the source it came from; one changed, saved with Ctrl+S.
    boxes = page.locator("main textarea")
    assert boxes.count() == 3
    assert boxes.nth(1).input_value() == "[tr] This line is spoken second."
    assert page.get_by_text("This line is spoken second.", exact=True).count() >= 1
    boxes.nth(1).fill("Bu satır ikinci söyleniyor.")
    page.get_by_text("1 line changed, not saved yet").wait_for()
    page.keyboard.press("Control+s")
    page.get_by_text("Saved", exact=True).wait_for()
    kept = _api(url, f"/api/jobs/{job_id}/translation")["lines"]
    assert kept[1]["text"] == "Bu satır ikinci söyleniyor."

    # Voiced: the run goes on from the lines as they are, and the preview is done.
    page.get_by_role("button", name="Voice it", exact=True).click()
    _until(lambda: _api(url, f"/api/jobs/{job_id}")["status"] == "done", what="the dub")
    page.get_by_text("Preview · 20 s").first.wait_for()
    whole = page.get_by_role("button", name="Dub the whole video")
    whole.wait_for()
    page.get_by_role("tab", name="Result").click()
    video = page.locator("main video").first
    assert video.get_attribute("src").endswith(f"/api/jobs/{job_id}/result/video")
    assert _api(url, f"/api/jobs/{job_id}/translation")["lines"][1]["text"] == \
        "Bu satır ikinci söyleniyor."

    # The whole video, with the same settings, on a page of its own.
    whole.click()
    page.wait_for_url(lambda u: "id=" in u and job_id not in u)
    full_id = page.url.split("id=")[1].split("&")[0]
    full = _until(lambda: (j := _api(url, f"/api/jobs/{full_id}"))["status"] == "review" and j,
                  what="the whole video's dub")
    assert full["config"]["preview"] is None and full["config"]["targetLang"] == "tr"

    # Both are in the list of dubs.
    page.get_by_role("link", name="Dubs", exact=True).first.click()
    page.wait_for_url(re.compile(r"/app/jobs/?$"))
    assert page.locator("main [data-library] [data-row-link]").count() >= 2


def test_a_dub_that_fails_says_why_and_tries_again(page, server):
    url, work = server
    file_id = _upload(url, HERE / "clip.mp4")
    config = {"targetLang": "ja", "translator": "google", "tts": "edge", "whisperModel": "small"}
    job_id = _api(url, "/api/jobs", {"fileId": file_id, "config": config})["jobId"]
    _until(lambda: _api(url, f"/api/jobs/{job_id}")["status"] == "failed", what="the failure")

    page.goto(f"{url}/en/app/jobs/view/?id={job_id}")
    page.get_by_text("Translation failed: the test asked for it to fail").first.wait_for()
    page.get_by_role("button", name="Try again").first.click()

    history = work / ".voxa_serve" / "history" / f"{job_id}.json"

    def failed_twice():
        events = json.loads(history.read_text(encoding="utf-8")).get("events", [])
        return sum(e.get("type") == "status" and e.get("status") == "failed" for e in events) == 2
    _until(failed_twice, what="the second run")
    page.get_by_text("Translation failed: the test asked for it to fail").first.wait_for()


def test_the_settings_search_opens_the_setting(page, server):
    url, _ = server
    page.goto(f"{url}/en/app/settings/")
    search = page.get_by_role("searchbox", name="Search Settings")
    search.fill("GPU")
    assert "Where the models run" in page.locator("main nav ul").first.text_content()
    search.press("Enter")
    page.wait_for_url(re.compile(r"section=performance"))
    _until(lambda: page.evaluate("document.activeElement?.id") == "device",
           what="the setting to take the focus")


def test_the_language_picked_is_kept_when_the_window_closes(browser, server):
    # A Turkish system, the language set to Azerbaijani, the window closed and opened again:
    # the console came back in Turkish, because the choice lived in a session cookie, which a
    # window drops when it closes. It must outlast the window.
    url, _ = server
    ctx = browser.new_context(locale="tr-TR", reduced_motion="reduce")
    ctx.add_init_script("localStorage.setItem('voxa.welcomed', '1')")
    page = ctx.new_page()
    page.goto(f"{url}/")
    page.wait_for_url("**/tr/app/**", timeout=WAIT)
    page.goto(f"{url}/tr/app/settings/?section=general")
    page.get_by_role("radio", name="Azərbaycanca").click(timeout=WAIT)
    page.wait_for_url("**/az/app/**", timeout=WAIT)
    cookie = next(c for c in ctx.cookies() if c["name"] == "NEXT_LOCALE")
    ctx.close()
    assert cookie["value"] == "az"
    assert cookie["expires"] > time.time() + 300 * 86400     # not a session cookie
    # What a window opened again sends: the kept cookie, from the same Turkish system.
    again = browser.new_context(locale="tr-TR")
    again.add_cookies([cookie])
    reopened = again.new_page()
    reopened.goto(f"{url}/")
    reopened.wait_for_url("**/az/app/**", timeout=WAIT)
    again.close()


@pytest.mark.skipif(not AXE.exists(), reason="axe-core isn't installed: cd web && npm ci")
def test_no_page_breaks_an_accessibility_rule(page, server):
    url, _ = server
    jobs = _api(url, "/api/jobs")["jobs"]
    pages = [("Studio", "/en/app/", "#studio-target"),
             ("Dubs", "/en/app/jobs/", "main [data-library] li" if jobs else "main"),
             ("Voices", "/en/app/voices/", "main [role=tablist]"),
             ("Engines", "/en/app/models/", "main article"),
             ("System", "/en/app/system/", "main section h2"),
             ("Settings", "/en/app/settings/?section=general", "main nav"),
             ("Settings › About", "/en/app/settings/?section=about", "main nav")]
    if jobs:
        pages.append(("a dub", f"/en/app/jobs/view/?id={jobs[0]['id']}", "main video"))
    found = []
    for theme in ("dark", "light"):
        page.goto(f"{url}/en/app/")                    # the console's own storage
        page.evaluate(f"localStorage.setItem('theme', '{theme}')")
        for name, path, ready in pages:
            page.goto(url + path)
            page.wait_for_selector(ready)
            page.wait_for_timeout(500)
            page.add_script_tag(path=str(AXE))
            result = page.evaluate(
                "async (tags) => await axe.run(document, {runOnly: {type: 'tag', values: tags},"
                " resultTypes: ['violations']})", AXE_TAGS)
            found += [f"{theme} {name}: {v['id']} ({v['impact']}) at "
                      f"{', '.join(' '.join(n['target']) for n in v['nodes'][:3])}"
                      for v in result["violations"]]
    assert not found, "\n".join(found)

