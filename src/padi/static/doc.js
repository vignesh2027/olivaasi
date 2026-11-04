(function () {
  var root = document.documentElement, body = document.body;
  function save(k, v) { try { localStorage.setItem("padi." + k, v); } catch (e) {} }
  function load(k) { try { return localStorage.getItem("padi." + k); } catch (e) { return null; } }

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

  var a = document.getElementById("player");
  if (!a) return;
  var parts = [].slice.call(document.querySelectorAll("[data-start]")), cur = -1;
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
    for (var k = 0; k < parts.length && t >= +parts[k].getAttribute("data-start"); k++) i = k;
    mark(i, false);
  });
  function go(i) {
    i = Math.max(0, Math.min(parts.length - 1, i));
    a.currentTime = +parts[i].getAttribute("data-start");
    mark(i, true);
    a.play();
  }
  document.getElementById("prev").addEventListener("click", function () { go(cur - 1); });
  document.getElementById("again").addEventListener("click", function () { go(Math.max(cur, 0)); });
  document.getElementById("next").addEventListener("click", function () { go(cur + 1); });
  var speed = document.getElementById("speed");
  speed.addEventListener("change", function () { a.playbackRate = +speed.value; save("speed", speed.value); });
  if (load("speed")) { speed.value = load("speed"); a.playbackRate = +speed.value; }
  parts.forEach(function (el, i) { el.addEventListener("click", function () { go(i); }); });
})();
