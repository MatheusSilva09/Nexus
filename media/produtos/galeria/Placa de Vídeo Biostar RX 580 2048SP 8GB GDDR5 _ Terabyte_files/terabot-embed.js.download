(function () {
  if (window.__TERABOT_LOADED__) return;
  window.__TERABOT_LOADED__ = true;

  // ============================================================
  // SNAPSHOT de horário (espelha platform_settings.chat_schedule).
  // Quando mudar em /admin/settings, peça pra republicar este arquivo.
  // O servidor (is_chat_open) continua sendo a fonte da verdade —
  // este snapshot só serve pra evitar invocações desnecessárias da
  // edge function quando sabemos que o chat está fechado.
  // ============================================================
  var TZ = "America/Sao_Paulo";
  var ENABLED = true;
  var WEEKLY = {
    monday:    { enabled: true,  start: "08:30", end: "18:00" },
    tuesday:   { enabled: true,  start: "08:30", end: "18:00" },
    wednesday: { enabled: true,  start: "08:30", end: "18:00" },
    thursday:  { enabled: true,  start: "08:30", end: "18:00" },
    friday:    { enabled: true,  start: "08:30", end: "18:00" },
    saturday:  { enabled: false, start: "09:00", end: "13:00" },
    sunday:    { enabled: false, start: "09:00", end: "13:00" }
  };
  var HOLIDAYS = []; // ["YYYY-MM-DD", ...]

  function isOpenNow() {
    try {
      if (ENABLED === false) return false;
      var fmt = new Intl.DateTimeFormat("en-CA", {
        timeZone: TZ,
        year: "numeric", month: "2-digit", day: "2-digit",
        weekday: "long",
        hour: "2-digit", minute: "2-digit", hour12: false
      });
      var parts = fmt.formatToParts(new Date());
      var p = {};
      for (var i = 0; i < parts.length; i++) p[parts[i].type] = parts[i].value;
      var date = p.year + "-" + p.month + "-" + p.day;
      if (HOLIDAYS.indexOf(date) !== -1) return false;
      var slot = WEEKLY[(p.weekday || "").toLowerCase()];
      if (!slot || !slot.enabled) return false;
      var hh = p.hour === "24" ? "00" : p.hour;
      var nowHM = hh + ":" + p.minute;
      if (nowHM < slot.start || nowHM >= slot.end) return false;
      return true;
    } catch (_e) {
      return true; // fail-open: server valida
    }
  }

  if (!isOpenNow()) return;

  var U = "https://eucinrbdjilnwpgqlteo.supabase.co/functions/v1/serve-terabot-embed";
  var K = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1Y2lucmJkamlsbndwZ3FsdGVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0NzQ0ODEsImV4cCI6MjA5MzA1MDQ4MX0.1fnLjw5lsXHQF2QzqI60RGOn37LThro1ykhyT3KH-8c";
  fetch(U, { headers: { Authorization: "Bearer " + K, apikey: K } })
    .then(function (r) { return r.ok ? r.text() : ""; })
    .then(function (code) {
      if (!code) return;
      var s = document.createElement("script");
      s.text = code;
      (document.head || document.body).appendChild(s);
    })
    .catch(function () {});
})();
