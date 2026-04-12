(() => {
  // ✅ Prevent double init (يحمي من الصفحة البيضاء/تكرار listeners)
  if (window.__LIVESTOCK_UI_INIT__) return;
  window.__LIVESTOCK_UI_INIT__ = true;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------- utils ----------
  // ✅ Parsing قوي: يقبل raw مثل "32200.00" ويقبل مُنسّق مثل "32,200.00" أو "32.200,00" أو "٣٢٬٢٠٠٫٠٠"
  const toNum = (v) => {
    if (v === null || v === undefined) return 0;
    let s = String(v).trim();
    if (!s) return 0;

    // تحويل الأرقام العربية/الفارسية إلى لاتينية
    const ar = "٠١٢٣٤٥٦٧٨٩";
    const fa = "۰۱۲۳۴۵۶۷۸۹";
    s = s.replace(/[٠-٩]/g, (ch) => String(ar.indexOf(ch)));
    s = s.replace(/[۰-۹]/g, (ch) => String(fa.indexOf(ch)));

    // Arabic separators: thousands "٬" (U+066C) and decimal "٫" (U+066B)
    s = s.replace(/\u066C/g, ",").replace(/\u066B/g, ".");
    s = s.replace(/\s/g, "");

    // حذف أي رموز غير رقم/فواصل/إشارة
    s = s.replace(/[^0-9.,+-]/g, "");

    const hasComma = s.includes(",");
    const hasDot = s.includes(".");

    if (hasComma && hasDot) {
      const lastComma = s.lastIndexOf(",");
      const lastDot = s.lastIndexOf(".");
      if (lastDot > lastComma) {
        // "1,234.56" => comma thousands
        s = s.replace(/,/g, "");
      } else {
        // "1.234,56" => dot thousands + comma decimal
        s = s.replace(/\./g, "");
        s = s.replace(/,/g, ".");
      }
    } else if (hasComma && !hasDot) {
      // "1,234" thousands OR "1234,56" decimal comma
      if (/^\d{1,3}(,\d{3})+$/.test(s)) s = s.replace(/,/g, "");
      else s = s.replace(/,/g, ".");
    } else if (hasDot && !hasComma) {
      // "1.234.567" thousands dot OR "1234.56" decimal dot
      if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
    }

    const n = Number(s);
    return Number.isFinite(n) ? n : 0;
  };

  // ✅ للعرض فقط: 32,200.00 (آلاف بفاصلة + خانتين)
  const __MONEY_NF = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  // ✅ تقريب آمن لخانتين
  const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;

  const moneyDisp = (v) => __MONEY_NF.format(round2(Math.max(0, toNum(v))));

  // ✅ للإدخال + للإرسال للسيرفر: "60000.00" (raw بدون فواصل)
  const moneyInput = (v) => round2(Math.max(0, toNum(v))).toFixed(2);

  const escapeHtml = (s) =>
    String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  function getCookie(name) {
    const v = `; ${document.cookie}`;
    const parts = v.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  async function getJSON(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    const txt = await res.text();
    let j = {};
    try {
      j = JSON.parse(txt);
    } catch {}
    if (!res.ok) throw new Error(j.error || txt || "فشل الطلب");
    return j;
  }

  // ✅ تطبيع حقول المال قبل الإرسال (Decimal v2)
  function normalizeMoneyFields(data) {
    if (!data || typeof data !== "object") return data;
    const out = { ...data };
    for (const [k, v] of Object.entries(out)) {
      if (v === null || v === undefined) continue;

      if (
        k === "amount" ||
        k === "unit_price" ||
        k === "paid_amount" ||
        k === "amount_paid" ||
        k === "amount_due" ||
        k === "total_amount" ||
        /(_amount|_price)$/.test(k)
      ) {
        out[k] = moneyInput(v); // <-- string raw "0.00"
      }
    }
    return out;
  }

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(normalizeMoneyFields(data)),
    });

    const txt = await res.text();
    let j = {};
    try {
      j = JSON.parse(txt);
    } catch {}

    if (!res.ok) {
      if (j && j.error && (j.outstanding || j.credit_limit || j.projected)) {
        const extra = [
          j.outstanding != null ? `المستحق الحالي: ${moneyDisp(j.outstanding)} ريال` : null,
          j.credit_limit != null ? `حد الائتمان: ${moneyDisp(j.credit_limit)} ريال` : null,
          j.projected != null ? `بعد العملية: ${moneyDisp(j.projected)} ريال` : null,
        ]
          .filter(Boolean)
          .join("\n");
        throw new Error(j.error + (extra ? `\n\n${extra}` : ""));
      }
      throw new Error((j && j.error) || txt || "فشل الطلب");
    }
    return j;
  }

  function stripCountLabel(t) {
    return String(t || "")
      .replace(/^\(\s*[\d.,٬]+\s*\)\s*/, "")
      .trim();
  }
  function isTlyan(kind) {
    return ["HARRI", "SAWAKNI", "NAIMI"].includes(kind);
  }

  // local date helpers (avoid UTC shift)
  function fmtLocalISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }
  function addDays(d, days) {
    const x = new Date(d.getTime());
    x.setDate(x.getDate() + days);
    return x;
  }

  // ---------- tabs (purchase/sale/collections) ----------
  const tabs = $$("[data-tab]");
  const panels = $$("[data-panel]");
  const panelByName = new Map(panels.map((p) => [p.getAttribute("data-panel"), p]));

  // ✅ setTab آمن (يمنع إخفاء كل الأقسام عند hash غلط)
  function setTab(name) {
    if (!panels.length) return;

    const safeName = panelByName.has(name) ? name : "purchase";

    if (tabs.length) {
      tabs.forEach((t) => t.classList.toggle("active", t.getAttribute("data-tab") === safeName));
    }

    panels.forEach((p) => (p.style.display = "none"));

    const target = panelByName.get(safeName) || panels[0];
    if (target) target.style.display = "";

    location.hash = `#${safeName}`;

    if (safeName === "collections") refreshAging();
  }

  tabs.forEach((t) => t.addEventListener("click", () => setTab(t.getAttribute("data-tab"))));

  // ---------- class field toggles ----------
  const NEED_CLASS_TYPES = new Set(["HARRI", "SAWAKNI", "NAIMI"]);
  function toggleClassField(typeValue, wrapEl, selectEl) {
    if (!wrapEl || !selectEl) return;
    const need = NEED_CLASS_TYPES.has(typeValue);
    wrapEl.style.display = need ? "" : "none";
    selectEl.disabled = !need;
    if (!need) selectEl.value = "";
  }

  // ---------- elements ----------
  // purchase
  const pType = $('[data-p="type"]');
  const pClassWrap = $('[data-p="class-wrap"]');
  const pClass = $('[data-p="class"]');
  const pQty = $('[data-p="qty"]');
  const pUnit = $('[data-p="unit"]');
  const pTotal = $('[data-p="total"]');
  const pSave = $('[data-p="save"]');

  // sale
  const sType = $('[data-s="type"]');
  const sClassWrap = $('[data-s="class-wrap"]');
  const sClass = $('[data-s="class"]');
  const sQty = $('[data-s="qty"]');
  const sUnit = $('[data-s="unit"]');
  const sPayMode = $('[data-s="paymode"]');
  const sPaid = $('[data-s="paid"]');
  const sMethod = $('[data-s="method"]'); // optional
  const sTotal = $('[data-s="total"]');
  const sDueHint = $('[data-s="duehint"]');
  const sDueWrap = $('[data-s="due-wrap"]'); // optional
  const sDue = $('[data-s="due"]'); // optional
  const sSave = $('[data-s="save"]');

  // clients search
  const phoneInput = $('[data-s="phone"]');
  const nameInput = $('[data-s="customer"]');
  const dl = $("#clientPhones");

  // collections
  const agingRefreshBtn = $("#agingRefreshBtn");
  const agingMeta = $("#agingMeta");
  const agingTopWrap = $("#agingTopWrap");
  const agingTxWrap = $("#agingTxWrap");

  // ---------- init toggles ----------
  if (pType) {
    pType.addEventListener("change", () => toggleClassField(pType.value, pClassWrap, pClass));
    toggleClassField(pType.value, pClassWrap, pClass);
  }
  if (sType) {
    sType.addEventListener("change", () => toggleClassField(sType.value, sClassWrap, sClass));
    toggleClassField(sType.value, sClassWrap, sClass);
  }

  // ---------- stock ----------
  let STOCK = {};

  function getStock(kind, cls) {
    const m = STOCK[kind];
    if (!m) return 0;
    if (isTlyan(kind)) {
      if (!cls) return 0;
      return Number(m[cls] ?? 0);
    }
    return Number(m["NONE"] ?? m.total ?? 0);
  }

  function updateSaleOptionCounts() {
    if (!sType) return;
    Array.from(sType.options).forEach((opt) => {
      const k = opt.value;
      if (!k) return;
      const total = Number(STOCK[k] && STOCK[k].total != null ? STOCK[k].total : 0);
      opt.textContent = `(${Math.floor(total)}) ${stripCountLabel(opt.textContent)}`;
    });
  }

  function updateStockHints() {
    const pHint = $('[data-p="stockhint"]');
    const sHint = $('[data-s="stockhint"]');

    // purchase
    if (pHint) {
      const k = pType?.value || "";
      const c = pClass?.value || "";
      const q = Number(pQty?.value || 0);

      if (!k) pHint.textContent = "";
      else if (isTlyan(k) && !c) pHint.textContent = "اختر الصنف (جذع/ثني) لعرض الرصيد.";
      else {
        const cur = getStock(k, c);
        const after = cur + (isFinite(q) ? q : 0);
        pHint.textContent = `الرصيد الحالي: ${cur} — بعد الشراء: ${after}`;
      }
    }

    // sale
    if (sHint) {
      const k = sType?.value || "";
      const c = sClass?.value || "";
      const q = Number(sQty?.value || 0);

      if (!k) sHint.textContent = "";
      else if (isTlyan(k) && !c) sHint.textContent = "اختر الصنف (جذع/ثني) لعرض الرصيد.";
      else {
        const cur = getStock(k, c);
        const after = cur - (isFinite(q) ? q : 0);
        sHint.textContent = `الرصيد الحالي: ${cur} — بعد البيع: ${after}`;
      }
    }
  }

  async function refreshStock() {
    try {
      const j = await getJSON("/transactions/api/stock/");
      if (j.ok) {
        STOCK = j.by_kind || {};
        updateSaleOptionCounts();
        updateStockHints();
      }
    } catch {}
  }

  // ---------- calc ----------
  function calcPurchase() {
    const total = Math.max(0, toNum(pQty?.value)) * Math.max(0, toNum(pUnit?.value));
    if (pTotal) pTotal.textContent = moneyDisp(total);
    updateStockHints();
  }

  function calcSale() {
    const total = Math.max(0, toNum(sQty?.value)) * Math.max(0, toNum(sUnit?.value));
    if (sTotal) sTotal.textContent = moneyDisp(total);

    const mode = sPayMode?.value || "PAID";

    if (mode === "PAID") {
      if (sPaid) {
        sPaid.value = moneyInput(total); // raw
        sPaid.disabled = true;
      }
      if (sDueHint) {
        sDueHint.style.display = "none";
        sDueHint.textContent = "";
      }
      if (sDueWrap) sDueWrap.style.display = "none";
      if (sDue) sDue.value = "";
    } else {
      if (sPaid) sPaid.disabled = false;

      const paid = Math.max(0, toNum(sPaid?.value));
      const due = Math.max(0, total - paid);

      if (sDueHint) {
        sDueHint.style.display = "";
        sDueHint.textContent = `المتبقي (آجل): ${moneyDisp(due)} ريال`;
      }

      if (sDueWrap) sDueWrap.style.display = due > 0 ? "" : "none";

      if (due > 0 && sDue && !sDue.value) {
        sDue.value = fmtLocalISO(addDays(new Date(), 30));
      }
      if (due <= 0 && sDue) sDue.value = "";
    }

    updateStockHints();
  }

  [pQty, pUnit].forEach((el) => el && el.addEventListener("input", calcPurchase));
  [sQty, sUnit, sPaid].forEach((el) => el && el.addEventListener("input", calcSale));
  if (sPayMode) sPayMode.addEventListener("change", calcSale);

  calcPurchase();
  calcSale();

  // ---------- clients search ----------
  let phoneMap = new Map();
  let tmr = null;

  async function fetchClients(q) {
    const j = await getJSON(`/transactions/api/clients/search/?q=${encodeURIComponent(q)}`);
    if (!j.ok) return;

    phoneMap.clear();
    if (dl) dl.innerHTML = "";

    (j.items || []).forEach((it) => {
      const phone = String(it.phone || "");
      const name = String(it.name || "");
      if (!phone) return;
      phoneMap.set(phone, name);
      if (dl) {
        const opt = document.createElement("option");
        opt.value = phone;
        opt.label = name;
        dl.appendChild(opt);
      }
    });

    if (nameInput && phoneInput && phoneMap.has(phoneInput.value) && !nameInput.value) {
      nameInput.value = phoneMap.get(phoneInput.value);
    }
  }

  if (phoneInput) {
    phoneInput.addEventListener("input", () => {
      clearTimeout(tmr);
      const q = phoneInput.value.trim();
      if (q.length < 3) return;
      tmr = setTimeout(() => fetchClients(q), 250);
    });
    phoneInput.addEventListener("change", () => {
      if (nameInput && phoneInput && phoneMap.has(phoneInput.value) && !nameInput.value) {
        nameInput.value = phoneMap.get(phoneInput.value);
      }
    });
  }

  [pType, pClass, pQty, sType, sClass, sQty].forEach((el) => {
    if (!el) return;
    el.addEventListener("change", updateStockHints);
    el.addEventListener("input", updateStockHints);
  });

  // ---------- save purchase ----------
  if (pSave) {
    pSave.addEventListener("click", async () => {
      try {
        const kind = pType?.value || "";
        const cls = pClass?.value || "";
        const quantity = Number(pQty?.value || 0);
        const unit_price = pUnit?.value ?? 0;

        const isT = isTlyan(kind);

        if (!kind) { alert("اختر نوع المواشي"); pType?.focus(); return; }
        if (isT && !cls) { alert("اختر الصنف (جذع/ثني) للطليان"); pClass?.focus(); return; }
        if (quantity <= 0) { alert("أدخل الكمية (أكبر من صفر)"); pQty?.focus(); return; }
        if (toNum(unit_price) <= 0) { alert("أدخل سعر الوحدة (أكبر من صفر)"); pUnit?.focus(); return; }

        pSave.disabled = true;

        const r = await postJSON("/transactions/api/purchase/", {
          kind,
          cls: isT ? cls : "NONE",
          quantity,
          unit_price,
        });

        await refreshStock();
        if (r.preview_url) window.open(r.preview_url, "_blank", "noopener");
      } catch (e) {
        alert(String(e.message || e));
      } finally {
        pSave.disabled = false;
      }
    });
  }

  // ---------- save sale ----------
  if (sSave) {
    sSave.addEventListener("click", async () => {
      try {
        const kind = sType?.value || "";
        const cls = sClass?.value || "";
        const quantity = Number(sQty?.value || 0);
        const unit_price = sUnit?.value ?? 0;
        const isT = isTlyan(kind);

        if (!kind) { alert("اختر نوع المواشي"); sType?.focus(); return; }
        if (isT && !cls) { alert("اختر الصنف (جذع/ثني) للطليان"); sClass?.focus(); return; }
        if (quantity <= 0) { alert("أدخل الكمية (أكبر من صفر)"); sQty?.focus(); return; }
        if (toNum(unit_price) <= 0) { alert("أدخل سعر الوحدة (أكبر من صفر)"); sUnit?.focus(); return; }

        const payment_mode = sPayMode?.value || "PAID";
        const paid_amount = sPaid?.value ?? 0;
        const method = sMethod?.value || "CASH";

        const customer_name = String(nameInput?.value || "");
        const customer_phone = String(phoneInput?.value || "");

        if (payment_mode === "CREDIT" && !customer_phone.trim()) {
          alert("رقم الجوال مطلوب عند البيع بالآجل");
          phoneInput?.focus();
          return;
        }

        let due_date = null;
        if (payment_mode === "CREDIT" && sDueWrap && sDueWrap.style.display !== "none" && sDue?.value) {
          due_date = sDue.value;
        }

        sSave.disabled = true;

        const r = await postJSON("/transactions/api/sale/", {
          kind,
          cls: isT ? cls : "NONE",
          quantity,
          unit_price,
          payment_mode,
          paid_amount,
          method,
          due_date,
          customer_name,
          customer_phone,
        });

        await refreshStock();

        if (r.preview_url) window.open(r.preview_url, "_blank", "noopener");
        if (location.hash === "#collections") refreshAging();
      } catch (e) {
        alert(String(e.message || e));
      } finally {
        sSave.disabled = false;
      }
    });
  }

  // ---------- collections / aging ----------
  function setAgingValue(key, v) {
    const el = document.querySelector(`[data-a="${key}"]`);
    if (el) el.textContent = moneyDisp(v);
  }

  function renderAging(j) {
    const totals = (j && j.totals) || {};

    const cur = toNum(totals.current ?? totals.current_raw ?? totals.current_display);
    const b1 = toNum(totals["1_30"] ?? totals.b1_30 ?? totals["b1_30"] ?? totals.b1_30_raw ?? totals.b1_30_display);
    const b2 = toNum(totals["31_60"] ?? totals.b31_60 ?? totals["b31_60"] ?? totals.b31_60_raw ?? totals.b31_60_display);
    const b3 = toNum(totals["61_90"] ?? totals.b61_90 ?? totals["b61_90"] ?? totals.b61_90_raw ?? totals.b61_90_display);
    const b4 = toNum(
      totals["91_plus"] ??
        totals["90_plus"] ??
        totals.b90_plus ??
        totals["b90_plus"] ??
        totals.b90_plus_raw ??
        totals.b90_plus_display ??
        0
    );

    const allKey = totals.total ?? totals.all ?? totals.total_raw ?? totals.total_display;
    const all =
      (allKey !== undefined && allKey !== null && String(allKey).trim() !== "")
        ? toNum(allKey)
        : (cur + b1 + b2 + b3 + b4);

    setAgingValue("current", cur);
    setAgingValue("1_30", b1);
    setAgingValue("31_60", b2);
    setAgingValue("61_90", b3);
    setAgingValue("91_plus", b4);
    setAgingValue("90_plus", b4);
    setAgingValue("all", all);

    if (agingMeta) agingMeta.textContent = `آخر تحديث: ${j.as_of || ""} — إجمالي الآجل: ${moneyDisp(all)} ريال`;

    const top = (j && j.top_overdue_counterparties) || [];
    if (agingTopWrap) {
      if (!top.length) {
        agingTopWrap.innerHTML = `<div class="hint" style="text-align:right;">لا توجد ذمم متأخرة الآن ✅</div>`;
      } else {
        const rows = top
          .map((it) => {
            const id = it.id;
            const name = escapeHtml(it.name || "");
            const phone = escapeHtml(it.phone || "");
            const amt = moneyDisp(it.overdue_amount);
            const days = it.max_days ?? 0;
            return `
              <tr>
                <td>${name}<div style="color:rgba(243,247,255,.72); font-size:12px; margin-top:4px;">${phone || "—"}</div></td>
                <td><span class="badge">متأخر ${days} يوم</span></td>
                <td>${amt}</td>
                <td class="actions">
                  <button class="btn small blue" type="button" data-wa="${id}">واتساب</button>
                  <button class="btn small" style="background:rgba(255,255,255,.10); color:#f3f7ff; border:1px solid rgba(255,255,255,.08);" type="button" data-copy="${id}">نسخ</button>
                </td>
              </tr>
            `;
          })
          .join("");

        agingTopWrap.innerHTML = `
          <table class="table">
            <thead>
              <tr>
                <th>العميل</th>
                <th>الحالة</th>
                <th>المتأخر (ريال)</th>
                <th style="text-align:left;">إجراء</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        `;

        $$("[data-wa]", agingTopWrap).forEach((btn) => {
          btn.addEventListener("click", async () => {
            const id = btn.getAttribute("data-wa");
            try {
              btn.disabled = true;
              const r = await getJSON(`/transactions/api/clients/${id}/whatsapp-reminder/`);
              if (!r.ok) throw new Error(r.error || "فشل");
              if (!r.wa_link) { alert("لا يوجد رقم جوال لهذا العميل."); return; }
              window.open(r.wa_link, "_blank", "noopener");
            } catch (e) {
              alert(String(e.message || e));
            } finally {
              btn.disabled = false;
            }
          });
        });

        $$("[data-copy]", agingTopWrap).forEach((btn) => {
          btn.addEventListener("click", async () => {
            const id = btn.getAttribute("data-copy");
            try {
              btn.disabled = true;
              const r = await getJSON(`/transactions/api/clients/${id}/whatsapp-reminder/`);
              if (!r.ok) throw new Error(r.error || "فشل");
              const msg = r.message || "";
              if (!msg) { alert("لا توجد رسالة."); return; }
              if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(msg);
                alert("✅ تم نسخ الرسالة");
              } else {
                window.prompt("انسخ الرسالة:", msg);
              }
            } catch (e) {
              alert(String(e.message || e));
            } finally {
              btn.disabled = false;
            }
          });
        });
      }
    }

    const txs = (j && j.open_transactions) || [];
    if (agingTxWrap) {
      if (!txs.length) {
        agingTxWrap.innerHTML = `<div class="hint" style="text-align:right;">لا توجد معاملات آجلة.</div>`;
      } else {
        const rows = txs.slice(0, 10).map((tx) => {
          const ref = escapeHtml(tx.reference || `TX#${tx.id}`);
          const cp = escapeHtml(tx.counterparty_name || "");
          const due = escapeHtml(tx.due_date || "");
          const days = tx.days_past_due ?? 0;
          const amt = moneyDisp(tx.amount_due);
          return `
            <tr>
              <td>${ref}<div style="color:rgba(243,247,255,.72); font-size:12px; margin-top:4px;">${cp || "—"}</div></td>
              <td>${due}<div style="color:rgba(243,247,255,.72); font-size:12px; margin-top:4px;">${days > 0 ? `متأخر ${days} يوم` : "غير مستحق"}</div></td>
              <td>${amt}</td>
              <td class="actions">
                <a class="btn small" style="background:rgba(255,255,255,.10); color:#f3f7ff; border:1px solid rgba(255,255,255,.08);" href="/reports/tx/${tx.id}/" target="_blank" rel="noopener">عرض</a>
              </td>
            </tr>
          `;
        }).join("");

        agingTxWrap.innerHTML = `
          <table class="table">
            <thead>
              <tr>
                <th>المعاملة</th>
                <th>الاستحقاق</th>
                <th>المتبقي (ريال)</th>
                <th style="text-align:left;">إجراء</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        `;
      }
    }
  }

  async function refreshAging() {
    if (!agingTopWrap || !agingTxWrap) return;
    try {
      agingTopWrap.textContent = "⏳ جاري التحديث...";
      agingTxWrap.textContent = "⏳ جاري التحديث...";
      const j = await getJSON("/transactions/api/ar/aging/");
      if (!j.ok) throw new Error(j.error || "فشل");
      renderAging(j);
    } catch (e) {
      const msg = String(e.message || e);
      agingTopWrap.innerHTML = `<div class="hint" style="text-align:right;">❌ ${escapeHtml(msg)}</div>`;
      agingTxWrap.innerHTML = `<div class="hint" style="text-align:right;">—</div>`;
    }
  }

  if (agingRefreshBtn) agingRefreshBtn.addEventListener("click", refreshAging);

  // ---------- init ----------
  const hash = (location.hash || "").replace("#", "");
  setTab(hash || "purchase");
  refreshStock();
})();