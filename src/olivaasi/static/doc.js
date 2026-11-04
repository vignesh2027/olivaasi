(function () {
  var root = document.documentElement, body = document.body;
  function save(k, v) { try { localStorage.setItem("olivaasi." + k, v); } catch (e) {} }
  function load(k) { try { return localStorage.getItem("olivaasi." + k); } catch (e) { return null; } }

  var size = document.getElementById("size");
  function setSize(v) { root.style.setProperty("--scale", v / 100); size.value = v; save("size", v); }
  size.addEventListener("change", function () { setSize(size.value); });
  if (load("size")) setSize(load("size"));

  var styles = document.querySelectorAll("input[name=style]");
  function setStyle(v) {
    body.setAttribute("data-style", v);
    for (var i = 0; i < styles.length; i++) styles[i].checked = styles[i].value === v;
    save("style", v);
  }
  for (var i = 0; i < styles.length; i++) styles[i].addEventListener("change", function () { setStyle(this.value); });
  if (load("style")) setStyle(load("style"));

  // On a phone the settings start folded so the lesson is visible at once.
  var settings = document.getElementById("settings");
  if (settings && window.matchMedia && window.matchMedia("(max-width: 40rem)").matches) settings.open = false;

  var a = document.getElementById("player");
  var attr = "data-start", parts = [], cur = -1;
  function collect() {
    [].forEach.call(document.querySelectorAll(".now"), function (el) { el.classList.remove("now"); });
    parts = [].slice.call(document.querySelectorAll("[" + attr + "]"));
    cur = -1;
  }
  var versions = document.querySelectorAll("input[name=version]");
  function setVersion(v) {
    var simple = v === "simple";
    [].forEach.call(document.querySelectorAll("p.orig"), function (el) { el.hidden = simple; });
    [].forEach.call(document.querySelectorAll("p.simple"), function (el) { el.hidden = !simple; });
    for (var i = 0; i < versions.length; i++) versions[i].checked = versions[i].value === v;
    if (a && a.getAttribute("data-src-simple")) {
      a.pause();
      a.src = a.getAttribute(simple ? "data-src-simple" : "data-src");
      attr = simple ? "data-start-s" : "data-start";
    }
    collect();
    save("version", v);
  }
  for (var k = 0; k < versions.length; k++) versions[k].addEventListener("change", function () { setVersion(this.value); });
  if (versions.length && load("version")) setVersion(load("version"));
  if (!a) return;
  // Scripts run: swap the browser's player (six tab stops) for labelled buttons.
  a.removeAttribute("controls");
  a.hidden = true;
  document.getElementById("buttons").hidden = false;
  var play = document.getElementById("play"), time = document.getElementById("time");
  function mmss(t) { t = Math.max(0, Math.floor(t || 0)); return Math.floor(t / 60) + ":" + ("0" + (t % 60)).slice(-2); }
  function showTime() { time.textContent = mmss(a.currentTime) + " / " + mmss(a.duration); }
  play.addEventListener("click", function () { if (a.paused) a.play(); else a.pause(); });
  a.addEventListener("play", function () { play.textContent = "Pause"; });
  a.addEventListener("pause", function () { play.textContent = "Play"; });
  a.addEventListener("ended", function () { play.textContent = "Play"; });
  a.addEventListener("loadedmetadata", showTime);
  a.addEventListener("timeupdate", showTime);
  collect();
  var status = document.getElementById("where");
  function mark(i, announce) {
    if (i === cur) return;
    if (cur >= 0) parts[cur].classList.remove("now");
    cur = i;
    if (i < 0) return;
    var el = parts[i];
    el.classList.add("now");
    var r = el.getBoundingClientRect();
    if (r.top < 120 || r.bottom > window.innerHeight) el.scrollIntoView({ block: "center" });
    if (announce) status.textContent = "Sentence " + (i + 1) + " of " + parts.length;
  }
  a.addEventListener("timeupdate", function () {
    var t = a.currentTime, i = -1;
    for (var k = 0; k < parts.length && t >= +parts[k].getAttribute(attr); k++) i = k;
    mark(i, false);
  });
  function go(i) {
    i = Math.max(0, Math.min(parts.length - 1, i));
    a.currentTime = +parts[i].getAttribute(attr);
    mark(i, true);
    a.play();
  }
  document.getElementById("prev").addEventListener("click", function () { go(cur - 1); });
  document.getElementById("again").addEventListener("click", function () { go(Math.max(cur, 0)); });
  document.getElementById("next").addEventListener("click", function () { go(cur + 1); });
  document.getElementById("nexth").addEventListener("click", function () {
    for (var k = cur + 1; k < parts.length; k++) {
      if (parts[k].closest && parts[k].closest("h1, h2, h3")) { go(k); return; }
    }
    go(parts.length - 1);
  });
  var speed = document.getElementById("speed");
  function setSpeed(v) { speed.value = v; a.defaultPlaybackRate = a.playbackRate = +v; save("speed", v); }
  speed.addEventListener("change", function () { setSpeed(speed.value); });
  if (load("speed")) setSpeed(load("speed"));
  document.addEventListener("click", function (e) {
    var el = e.target.closest ? e.target.closest("[" + attr + "]") : null;
    if (el && parts.indexOf(el) >= 0) go(parts.indexOf(el));
  });
})();
