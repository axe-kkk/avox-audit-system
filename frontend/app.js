(function () {
  "use strict";

  var API = "/api/v1";

  var STEPS_META = [
    {
      title: "Контакт і сайт компанії",
      desc: "Щоб підготувати звіт, потрібні ваші дані та URL сайту для сканування.",
    },
    {
      title: "Ваша CRM",
      desc: "Оберіть систему, з якою працює відділ продажів або маркетингу.",
    },
    {
      title: "Розмір команди",
      desc: "Скільки людей у продажах / підтримці / роботі з клієнтами (орієнтовно).",
    },
    {
      title: "Вхідні ліди",
      desc: "Скільки заявок / звернень ви отримуєте за місяць.",
    },
    {
      title: "Обробка лідів",
      desc: "Чи встигаєте відповідати всім потенційним клієнтам у часі.",
    },
    {
      title: "Канали зв’язку",
      desc: "Де клієнти можуть вас знайти (можна кілька варіантів).",
    },
    {
      title: "Єдине бачення клієнта",
      desc: "Чи зведені дані про клієнта в одному місці для команди.",
    },
    {
      title: "Upsell і cross-sell",
      desc: "Як ви працюєте з додатковими продажами існуючим клієнтам.",
    },
    {
      title: "Відтік клієнтів",
      desc: "Чи бачите ви ризик втрати клієнта до того, як він піде.",
    },
    {
      title: "Головні виклики",
      desc: "Що найбільше заважає масштабувати дохід (оберіть усе актуальне).",
    },
  ];

  var OPTIONS = {
    crm: [
      { value: "hubspot", title: "HubSpot", desc: "Популярна CRM і маркетинг" },
      { value: "salesforce", title: "Salesforce", desc: "Enterprise CRM" },
      { value: "zoho", title: "Zoho", desc: "Zoho CRM / екосистема" },
      { value: "odoo", title: "Odoo", desc: "ERP / CRM" },
      { value: "other", title: "Інша CRM", desc: "Вкажіть назву на наступному кроці" },
      { value: "no_crm", title: "Немає CRM / інші інструменти", desc: "Таблиці, пошта, месенджери" },
    ],
    team_size: [
      { value: "<10", title: "До 10", desc: "Невелика команда" },
      { value: "10-20", title: "10–20", desc: "" },
      { value: "20-50", title: "20–50", desc: "" },
      { value: "50+", title: "50+", desc: "Велика команда" },
    ],
    monthly_leads: [
      { value: "<100", title: "До 100", desc: "на місяць" },
      { value: "100-500", title: "100–500", desc: "" },
      { value: "500-2000", title: "500–2 000", desc: "" },
      { value: "2000+", title: "2 000+", desc: "" },
    ],
    lead_handling: [
      { value: "all_on_time", title: "Усі вчасно", desc: "Встигаємо відповісти кожному" },
      { value: "probably_miss", title: "Ймовірно губимо частину", desc: "Інколи запізно або губляться звернення" },
      { value: "definitely_lose", title: "Точно губимо ліди", desc: "Відомо про втрати" },
    ],
    channels_used: [
      { value: "phone", title: "Телефон", desc: "" },
      { value: "email", title: "Email", desc: "" },
      { value: "website_chat", title: "Чат на сайті", desc: "" },
      { value: "messenger_whatsapp_viber", title: "WhatsApp / Viber / месенджери", desc: "" },
      { value: "social_dms", title: "Соцмережі (DM)", desc: "" },
      { value: "other", title: "Інше", desc: "" },
    ],
    unified_view: [
      { value: "yes", title: "Так", desc: "Єдиний профіль клієнта для команди" },
      { value: "partially", title: "Частково", desc: "Є фрагменти в різних системах" },
      { value: "no", title: "Ні", desc: "Дані розкидані" },
    ],
    upsell_crosssell: [
      { value: "yes_automated", title: "Так, автоматизовано", desc: "Тригери, сценарії, CRM" },
      { value: "manual_only", title: "Лише вручну", desc: "Менеджери без системи" },
      { value: "no", title: "Ні", desc: "Мало фокусу на допродаж" },
    ],
    churn_detection: [
      { value: "proactive", title: "Проактивно", desc: "Бачимо ризик до відходу" },
      { value: "manual", title: "Вручну", desc: "Реагуємо, коли вже помітили" },
      { value: "we_dont", title: "Не відстежуємо", desc: "" },
    ],
    biggest_frustrations: [
      { value: "revenue_doesnt_scale", title: "Дохід не масштабується", desc: "" },
      { value: "too_many_tools_no_picture", title: "Забагато інструментів, немає картини", desc: "" },
      { value: "dont_know_which_customers", title: "Незрозуміло, на кого фокус", desc: "" },
      { value: "no_upsell_retention_system", title: "Немає upsell / утримання", desc: "" },
      { value: "cant_measure_whats_working", title: "Не вимірюється, що працює", desc: "" },
    ],
  };

  var PIPELINE = [
    { key: "pending", label: "У черзі" },
    { key: "enriching", label: "Сканування сайту" },
    { key: "scoring", label: "Оцінка зрілості" },
    { key: "generating", label: "Звіт і PDF" },
    { key: "completed", label: "Готово" },
  ];

  var STATUS_UK = {
    pending: "У черзі",
    enriching: "Сканування сайту",
    scoring: "Оцінка зрілості",
    generating: "Звіт і PDF",
    completed: "Готово",
    failed: "Помилка",
  };

  var state = {
    step: 0,
    pollTimer: null,
    activeListTimer: null,
    selectedAuditId: null,
  };

  function $(sel) {
    return document.querySelector(sel);
  }

  function showError(msg) {
    var el = $("#form-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function buildOptions() {
    document.querySelectorAll(".options").forEach(function (container) {
      var name = container.dataset.name;
      var type = container.dataset.type;
      var list = OPTIONS[name];
      if (!list) return;
      container.innerHTML = "";
      list.forEach(function (opt) {
        var id = name + "_" + opt.value.replace(/[^a-z0-9]/gi, "_");
        var label = document.createElement("label");
        label.className = "opt-card";
        label.htmlFor = id;
        var input = document.createElement("input");
        input.type = type === "multi" ? "checkbox" : "radio";
        input.name = name;
        input.value = opt.value;
        input.id = id;
        if (type === "single") input.required = true;
        var body = document.createElement("div");
        body.className = "opt-body";
        body.innerHTML =
          "<p class=\"opt-title\">" +
          escapeHtml(opt.title) +
          "</p>" +
          (opt.desc
            ? "<p class=\"opt-desc\">" + escapeHtml(opt.desc) + "</p>"
            : "");
        label.appendChild(input);
        label.appendChild(body);
        container.appendChild(label);
        label.addEventListener("click", function () {
          if (type === "single") {
            container.querySelectorAll(".opt-card").forEach(function (c) {
              c.classList.remove("selected");
            });
            label.classList.add("selected");
          } else {
            window.setTimeout(function () {
              label.classList.toggle("selected", input.checked);
            }, 0);
          }
        });
        input.addEventListener("change", function () {
          if (type === "multi") label.classList.toggle("selected", input.checked);
        });
      });
    });
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function updateCrmOtherVisibility() {
    var wrap = $("#crm-other-wrap");
    var selected = document.querySelector('input[name="crm"]:checked');
    var show = selected && selected.value === "other";
    wrap.classList.toggle("hidden", !show);
    var inp = wrap.querySelector("input");
    if (inp) inp.required = !!show;
  }

  function syncOptionCards(stepEl) {
    if (!stepEl) return;
    stepEl.querySelectorAll(".opt-card").forEach(function (label) {
      var input = label.querySelector("input");
      if (input) label.classList.toggle("selected", input.checked);
    });
  }

  function renderStep() {
    var n = state.step;
    var meta = STEPS_META[n];
    $("#step-indicator").textContent = "Крок " + (n + 1) + " з 10";
    $("#step-title").textContent = meta.title;
    $("#step-desc").textContent = meta.desc;
    $("#step-desc").classList.toggle("hidden", n === 9);

    document.querySelectorAll(".step").forEach(function (el) {
      var active = parseInt(el.dataset.step, 10) === n;
      el.classList.toggle("hidden", !active);
      if (active) syncOptionCards(el);
    });

    $("#btn-back").classList.toggle("hidden", n === 0);
    $("#btn-next").classList.toggle("hidden", n === 9);
    $("#btn-submit").classList.toggle("hidden", n !== 9);

    if (n === 1) updateCrmOtherVisibility();
  }

  function validateStep() {
    showError("");
    var n = state.step;
    var form = $("#audit-form");

    if (n === 0) {
      var fn = form.full_name.value.trim();
      var em = form.work_email.value.trim();
      var url = form.company_url.value.trim();
      if (!fn) return showError("Вкажіть ім’я."), false;
      if (!em || !em.includes("@")) return showError("Вкажіть коректний email."), false;
      if (!url) return showError("Вкажіть URL сайту."), false;
      try {
        new URL(url.startsWith("http") ? url : "https://" + url);
      } catch (e) {
        return showError("Схоже, URL некоректний."), false;
      }
      return true;
    }

    if (n === 1) {
      var crm = form.querySelector('input[name="crm"]:checked');
      if (!crm) return showError("Оберіть варіант CRM."), false;
      if (crm.value === "other") {
        var o = form.crm_other.value.trim();
        if (!o) return showError("Опишіть вашу CRM."), false;
      }
      return true;
    }

    if (n >= 2 && n <= 4) {
      var names = ["team_size", "monthly_leads", "lead_handling"];
      var nm = names[n - 2];
      if (!form.querySelector('input[name="' + nm + '"]:checked'))
        return showError("Оберіть варіант."), false;
      return true;
    }

    if (n === 5) {
      if (!form.querySelectorAll('input[name="channels_used"]:checked').length)
        return showError("Оберіть хоча б один канал."), false;
      return true;
    }

    if (n >= 6 && n <= 8) {
      var names2 = ["unified_view", "upsell_crosssell", "churn_detection"];
      var nm2 = names2[n - 6];
      if (!form.querySelector('input[name="' + nm2 + '"]:checked'))
        return showError("Оберіть варіант."), false;
      return true;
    }

    if (n === 9) {
      if (!form.querySelectorAll('input[name="biggest_frustrations"]:checked').length)
        return showError("Оберіть хоча б один пункт."), false;
    }
    return true;
  }

  function collectPayload() {
    var form = $("#audit-form");
    var url = form.company_url.value.trim();
    if (!/^https?:\/\//i.test(url)) url = "https://" + url;

    var channels = Array.prototype.map.call(
      form.querySelectorAll('input[name="channels_used"]:checked'),
      function (x) {
        return x.value;
      }
    );
    var fr = Array.prototype.map.call(
      form.querySelectorAll('input[name="biggest_frustrations"]:checked'),
      function (x) {
        return x.value;
      }
    );

    var payload = {
      full_name: form.full_name.value.trim(),
      work_email: form.work_email.value.trim(),
      company_url: url,
      crm: form.querySelector('input[name="crm"]:checked').value,
      crm_other:
        form.querySelector('input[name="crm"]:checked').value === "other"
          ? form.crm_other.value.trim()
          : null,
      team_size: form.querySelector('input[name="team_size"]:checked').value,
      monthly_leads: form.querySelector('input[name="monthly_leads"]:checked').value,
      lead_handling: form.querySelector('input[name="lead_handling"]:checked').value,
      channels_used: channels,
      unified_view: form.querySelector('input[name="unified_view"]:checked').value,
      upsell_crosssell: form.querySelector('input[name="upsell_crosssell"]:checked').value,
      churn_detection: form.querySelector('input[name="churn_detection"]:checked').value,
      biggest_frustrations: fr,
    };
    return payload;
  }

  function displayHost(url) {
    try {
      var u = url.indexOf("http") === 0 ? url : "https://" + url;
      return new URL(u).hostname || url;
    } catch (e) {
      return url;
    }
  }

  function renderPipelineInto(container, status) {
    if (!container) return;
    var order = ["pending", "enriching", "scoring", "generating", "completed"];
    var idx = order.indexOf(status);
    if (idx < 0 && status && status !== "failed") idx = 0;
    var html = "";

    if (status === "failed") {
      PIPELINE.slice(0, -1).forEach(function (p) {
        html +=
          '<div class="pipe-item done"><span class="pipe-dot"></span><span>' +
          escapeHtml(p.label) +
          "</span></div>";
      });
      html +=
        '<div class="pipe-item fail"><span class="pipe-dot"></span><span>Помилка</span></div>';
      container.innerHTML = html;
      return;
    }

    PIPELINE.forEach(function (p, i) {
      var cls = "pipe-item";
      if (i < idx) cls += " done";
      else if (i === idx) cls += " active";
      html +=
        '<div class="' +
        cls +
        '"><span class="pipe-dot"></span><span>' +
        escapeHtml(p.label) +
        "</span></div>";
    });
    container.innerHTML = html;
  }

  function updateTrafficLine(data) {
    var el = $("#last-traffic");
    if (!el) return;
    var st = typeof data.status === "string" ? data.status : "";
    var tr = data.traffic;
    if (!tr) {
      if (st === "pending" || st === "enriching") {
        el.textContent =
          "Відвідуваність: оцінка з’явиться після сканування сайту.";
        el.hidden = false;
        return;
      }
      el.textContent = "Відвідуваність: дані недоступні.";
      el.hidden = false;
      return;
    }
    var visits = tr.estimated_monthly_visits;
    if (visits != null && visits !== "") {
      var n = Number(String(visits).replace(/,/g, ""));
      if (!isNaN(n) && isFinite(n) && n > 0) {
        var line =
          "Відвідуваність (оцінка): " +
          Math.round(n).toLocaleString("uk-UA") +
          " / міс.";
        if (tr.traffic_tier_label)
          line += " (" + String(tr.traffic_tier_label) + ")";
        el.textContent = line;
        el.hidden = false;
        return;
      }
    }
    if (tr.insufficient_data)
      el.textContent =
        "Відвідуваність: публічні дані SimilarWeb для цього домену недоступні.";
    else el.textContent = "Відвідуваність: дані недоступні.";
    el.hidden = false;
  }

  function updateSelectedAuditPanel(data) {
    if (!data || data.id == null || data.id !== state.selectedAuditId) return;
    var block = $("#last-audit-block");
    if (!block) return;
    block.hidden = false;
    $("#last-submission-id").textContent =
      "Заявка №" + (data.id != null ? data.id : "—");
    var urlEl = $("#last-submission-url");
    if (urlEl) {
      var u = data.company_url ? displayHost(data.company_url) : "";
      urlEl.textContent = u || "—";
    }
    updateTrafficLine(data);
    var st = typeof data.status === "string" ? data.status : "";
    renderPipelineInto($("#last-pipeline"), st);
    var detail = "";
    if (st === "completed")
      detail = "Звіт згенеровано. Перевірте email / Telegram (якщо налаштовано).";
    else if (st === "failed")
      detail = data.error_message || "Сталася помилка під час обробки.";
    else detail = "Пайплайн виконується на сервері — це може зайняти кілька хвилин.";
    $("#last-status-detail").textContent = detail;

    if (st === "completed") block.dataset.state = "done";
    else if (st === "failed") block.dataset.state = "fail";
    else block.dataset.state = "run";

    if (st === "completed" || st === "failed") {
      if (state.pollTimer && data.id === state.selectedAuditId) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
      fetchActiveAudits();
    }
  }

  function pollSelectedSubmission(id) {
    state.selectedAuditId = id;
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
    var block = $("#last-audit-block");
    if (block) block.hidden = false;
    function pollOnce() {
      return fetch(API + "/submissions/" + id).then(function (r) {
        if (!r.ok) throw new Error("poll_http_" + r.status);
        return r.json();
      });
    }
    state.pollTimer = setInterval(function () {
      pollOnce()
        .then(updateSelectedAuditPanel)
        .catch(function () {});
    }, 2000);
    pollOnce()
      .then(updateSelectedAuditPanel)
      .catch(function () {});
  }

  function selectAudit(id) {
    var sid = parseInt(id, 10);
    if (isNaN(sid)) return;
    if (sid === state.selectedAuditId && state.pollTimer) {
      fetchActiveAudits();
      return;
    }
    pollSelectedSubmission(sid);
    fetchActiveAudits();
  }

  function fetchActiveAudits() {
    fetch(API + "/submissions?active_only=true&per_page=50")
      .then(function (r) {
        if (!r.ok) throw new Error("list");
        return r.json();
      })
      .then(function (data) {
        var items = data.items || [];
        var list = $("#active-audits-list");
        var empty = $("#active-audits-empty");
        if (!list || !empty) return;
        empty.classList.toggle("hidden", items.length > 0);
        if (!items.length) {
          list.innerHTML = "";
          return;
        }
        list.innerHTML = items
          .map(function (it) {
            var focus =
              state.selectedAuditId != null && it.id === state.selectedAuditId
                ? " active-audit-row--focus"
                : "";
            var su = STATUS_UK[it.status] || it.status;
            return (
              '<li class="active-audit-row' +
              focus +
              '" role="button" tabindex="0" data-id="' +
              it.id +
              '"><span class="active-audit-id">№' +
              it.id +
              '</span><span class="active-audit-url">' +
              escapeHtml(displayHost(it.company_url)) +
              '</span><span class="active-audit-status">' +
              escapeHtml(su) +
              "</span></li>"
            );
          })
          .join("");
      })
      .catch(function () {});
  }

  function resetWizard() {
    var form = $("#audit-form");
    form.reset();
    state.step = 0;
    buildOptions();
    renderStep();
    updateCrmOtherVisibility();
    showError("");
    $("#sys-status").textContent =
      "Заявку прийнято. Форму скинуто — можете надіслати наступну.";
  }

  function onSubmit(e) {
    e.preventDefault();
    if (!validateStep()) return;
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
    showError("");
    var payload = collectPayload();
    var btn = $("#btn-submit");
    btn.disabled = true;
    btn.textContent = "Відправка…";

    function formatApiError(body, statusText) {
      if (body == null) return statusText || "Помилка";
      var d = body.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d) && d.length) {
        var parts = d.map(function (x) {
          if (x && typeof x.msg === "string") return x.msg;
          return String(x);
        });
        return parts.join("; ");
      }
      if (d && typeof d === "object" && typeof d.message === "string") return d.message;
      return statusText || "Помилка валідації";
    }

    fetch(API + "/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        if (!r.ok)
          return r.json().then(
            function (j) {
              throw new Error(formatApiError(j, r.statusText));
            },
            function () {
              throw new Error(r.statusText || "Помилка");
            }
          );
        return r.json();
      })
      .then(function (data) {
        resetWizard();
        pollSelectedSubmission(data.id);
        fetchActiveAudits();
        var side = document.querySelector(".audits-sidebar");
        if (side) side.scrollIntoView({ behavior: "smooth", block: "nearest" });
      })
      .catch(function (err) {
        showError(typeof err.message === "string" ? err.message : "Помилка відправки.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Надіслати на аудит";
      });
  }

  function init() {
    buildOptions();
    renderStep();
    fetchActiveAudits();
    state.activeListTimer = setInterval(fetchActiveAudits, 2500);

    $("#btn-next").addEventListener("click", function () {
      if (!validateStep()) return;
      if (state.step < 9) {
        state.step++;
        renderStep();
      }
    });

    $("#btn-back").addEventListener("click", function () {
      if (state.step > 0) {
        state.step--;
        renderStep();
      }
    });

    $("#audit-form").addEventListener("submit", onSubmit);
    $("#audit-form").addEventListener("change", function (e) {
      if (e.target && e.target.name === "crm") updateCrmOtherVisibility();
    });

    var scrollHost = $("#active-audits-scroll");
    if (scrollHost) {
      scrollHost.addEventListener("click", function (e) {
        var row = e.target.closest(".active-audit-row");
        if (!row || !row.dataset.id) return;
        selectAudit(row.dataset.id);
      });
      scrollHost.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" && e.key !== " ") return;
        var row = e.target.closest(".active-audit-row");
        if (!row || !row.dataset.id) return;
        e.preventDefault();
        selectAudit(row.dataset.id);
      });
    }
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
