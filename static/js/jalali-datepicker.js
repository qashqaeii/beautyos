/* BeautyOS — Persian (Jalali) date picker · week starts Saturday */
(function () {
  const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  const LATIN_DIGITS = "0123456789";
  const toFa = (s) => String(s).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[+d]);
  const toEn = (s) =>
    String(s)
      .replace(/[۰-۹]/g, (d) => LATIN_DIGITS[PERSIAN_DIGITS.indexOf(d)])
      .trim();

  const MONTHS_FA = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
  ];
  const WEEKDAYS_FA = ["ش", "ی", "د", "س", "چ", "پ", "ج"]; /* شنبه … جمعه */

  function jalaliIsLeap(jy) {
    // Match jdatetime's 33-year leap cycle used by the Django backend.
    return [1, 5, 9, 13, 17, 22, 26, 30].includes(((jy % 33) + 33) % 33);
  }

  function jalaliMonthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return jalaliIsLeap(jy) ? 30 : 29;
  }

  function gregorianToJalali(gy, gm, gd) {
    const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let jy = gy <= 1600 ? 0 : 979;
    gy -= gy <= 1600 ? 621 : 1600;
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days =
      365 * gy +
      Math.floor((gy2 + 3) / 4) -
      Math.floor((gy2 + 99) / 100) +
      Math.floor((gy2 + 399) / 400) -
      80 +
      gd +
      g_d_m[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      jy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    let jm;
    let jd;
    if (days < 186) {
      jm = 1 + Math.floor(days / 31);
      jd = 1 + (days % 31);
    } else {
      jm = 7 + Math.floor((days - 186) / 30);
      jd = 1 + ((days - 186) % 30);
    }
    return { jy, jm, jd };
  }

  function jalaliToGregorian(jy, jm, jd) {
    jy -= 979;
    let days =
      365 * jy +
      Math.floor(jy / 33) * 8 +
      Math.floor(((jy % 33) + 3) / 4) +
      (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186) +
      jd +
      78; // Gregorian epoch offset; inverse of the -80 in gregorianToJalali.
    let gy = 1600 + 400 * Math.floor(days / 146097);
    days %= 146097;
    if (days > 36524) {
      gy += 100 * Math.floor(--days / 36524);
      days %= 36524;
      if (days >= 365) days++;
    }
    gy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      gy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    const gd_m = [0, 31, (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let gm = 0;
    let gd = days + 1;
    for (gm = 1; gm <= 12 && gd > gd_m[gm]; gm++) gd -= gd_m[gm];
    return { gy, gm, gd };
  }

  function isoFromJalali(jy, jm, jd) {
    const { gy, gm, gd } = jalaliToGregorian(jy, jm, jd);
    return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
  }

  function jalaliFromIso(iso) {
    if (!iso || iso.length < 10) return null;
    const gy = +iso.slice(0, 4);
    const gm = +iso.slice(5, 7);
    const gd = +iso.slice(8, 10);
    return gregorianToJalali(gy, gm, gd);
  }

  function displayFromIso(iso) {
    const j = jalaliFromIso(iso);
    if (!j) return "";
    return toFa(`${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")}`);
  }

  function parseDisplay(text) {
    const en = toEn(text).replace(/-/g, "/").replace(/\./g, "/");
    const parts = en.split("/").filter(Boolean);
    if (parts.length !== 3) return null;
    const jy = +parts[0];
    const jm = +parts[1];
    const jd = +parts[2];
    if (!jy || jm < 1 || jm > 12 || jd < 1 || jd > jalaliMonthLength(jy, jm)) return null;
    return { jy, jm, jd, iso: isoFromJalali(jy, jm, jd) };
  }

  function extractDateDigits(text) {
    return toEn(text).replace(/\D/g, "").slice(0, 8);
  }

  function formatJalaliDigits(digits) {
    if (!digits) return "";
    if (digits.length <= 4) return toFa(digits);
    if (digits.length <= 6) return toFa(`${digits.slice(0, 4)}/${digits.slice(4)}`);
    return toFa(`${digits.slice(0, 4)}/${digits.slice(4, 6)}/${digits.slice(6)}`);
  }

  function caretAfterJalaliFormat(digitsLen) {
    if (digitsLen <= 4) return digitsLen;
    if (digitsLen <= 6) return digitsLen + 1;
    return digitsLen + 2;
  }

  function isoWeekdaySat0(iso) {
    if (!iso) return null;
    const gy = +iso.slice(0, 4);
    const gm = +iso.slice(5, 7);
    const gd = +iso.slice(8, 10);
    const d = new Date(gy, gm - 1, gd);
    return (d.getDay() + 1) % 7;
  }

  function emitJalaliChange(el, name, iso) {
    el.dispatchEvent(
      new CustomEvent("jalali-change", { bubbles: true, detail: { name, iso: iso || "" } })
    );
  }

  /** Saturday = 0 … Friday = 6 */
  function jalaliWeekday(jy, jm, jd) {
    const { gy, gm, gd } = jalaliToGregorian(jy, jm, jd);
    const d = new Date(gy, gm - 1, gd);
    const js = d.getDay(); /* Sun=0 */
    return (js + 1) % 7;
  }

  function todayIso() {
    const t = new Date();
    return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
  }

  function lucideRefreshIn(root) {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
    }
  }

  const POPOVER_WIDTH = 288;
  const POPOVER_EDGE = 8;
  const POPOVER_EST_HEIGHT = 328;
  const POPOVER_Z_INDEX = 280;

  function popoverAnchorEl(root, refs) {
    if (refs) {
      if (refs.calendarBtn) return refs.calendarBtn;
      if (refs.anchorTrigger) return refs.anchorTrigger;
      if (refs.displayInput) {
        const control = root.querySelector(".jalali-date__control");
        if (control) return control;
      }
    }
    return (
      root.querySelector(".jalali-date__control") ||
      root.querySelector(".jalali-date__inline-trigger")
    );
  }

  function jalaliPopoverMixin() {
    return {
      birthPicker: false,
      directNavigation: false,
      popoverStyle: {},
      popoverPlacement: "below",
      jalaliDismissPointer(event) {
        if (!this.open) return;
        const target = event.target;
        if (!(target instanceof Node)) return;
        if (target.closest && target.closest("[data-jalali-calendar-trigger]")) return;
        const pop = this.$refs.popover;
        if (this.$el.contains(target)) return;
        if (pop && pop.contains(target)) return;
        this.closeCalendar();
      },
      _applyPopoverStyle() {
        const pop = this.$refs.popover;
        const style = this.popoverStyle;
        if (!pop || !style || !style.position) return;
        Object.assign(pop.style, style);
        pop.style.opacity = "1";
        pop.style.visibility = "visible";
      },
      handleEscapeKey(event) {
        if (!this.open) return;
        event.stopPropagation();
        this.closeCalendar();
      },
      isIsoDisabled(iso) {
        return Boolean(this.maxIso && iso && iso > this.maxIso);
      },
      _bindPopoverFollow() {
        if (this._jalaliFollowBound) return;
        this._jalaliFollowBound = true;
        this._jalaliFollow = () => {
          if (!this.open) return;
          this.positionPopover();
        };
        window.addEventListener("resize", this._jalaliFollow, { passive: true });
        window.addEventListener("scroll", this._jalaliFollow, { passive: true, capture: true });
      },
      _unbindPopoverFollow() {
        if (!this._jalaliFollowBound || !this._jalaliFollow) return;
        window.removeEventListener("resize", this._jalaliFollow);
        window.removeEventListener("scroll", this._jalaliFollow, true);
        this._jalaliFollowBound = false;
      },
      positionPopover() {
        const anchor = popoverAnchorEl(this.$el, this.$refs);
        if (!anchor) return;
        if (typeof anchor.scrollIntoView === "function") {
          try {
            anchor.scrollIntoView({ block: "nearest", inline: "nearest" });
          } catch (_e) {
            /* noop */
          }
        }
        const r = anchor.getBoundingClientRect();
        if (this.directNavigation) {
          this.positionCompactPopover(r);
          return;
        }
        const width = Math.min(POPOVER_WIDTH, window.innerWidth - POPOVER_EDGE * 2);
        const gap = 6;
        let top = r.bottom + gap;
        let placement = "below";
        const spaceBelow = window.innerHeight - r.bottom - gap;
        const spaceAbove = r.top - gap;
        const viewportPad = POPOVER_EDGE;
        if (spaceBelow < POPOVER_EST_HEIGHT && spaceAbove > spaceBelow) {
          placement = "above";
          top = Math.max(viewportPad, r.top - gap - POPOVER_EST_HEIGHT);
        } else {
          top = Math.min(top, window.innerHeight - POPOVER_EST_HEIGHT - viewportPad);
        }
        const anchorCenter = r.left + r.width / 2;
        let left = anchorCenter - width / 2;
        left = Math.max(
          viewportPad,
          Math.min(left, window.innerWidth - width - viewportPad)
        );
        this.popoverPlacement = placement;
        this.popoverStyle = {
          position: "fixed",
          top: `${Math.max(viewportPad, top)}px`,
          left: `${left}px`,
          width: `${width}px`,
          maxWidth: `calc(100vw - ${POPOVER_EDGE * 2}px)`,
          maxHeight: `${Math.min(POPOVER_EST_HEIGHT, window.innerHeight - viewportPad * 2)}px`,
          overflowY: "auto",
          zIndex: String(POPOVER_Z_INDEX),
        };
        this._applyPopoverStyle();
      },
      positionCompactPopover(r) {
        const pop = this.$refs.popover;
        if (!pop || !pop.getClientRects().length) return;
        const edge = POPOVER_EDGE;
        const gap = 6;
        const width = Math.min(272, window.innerWidth - edge * 2);
        const available = Math.max(1, window.innerHeight - edge * 2);
        // Give the actual month's grid room first, instead of clipping it to a fixed estimate.
        Object.assign(pop.style, {width: `${width}px`, maxHeight: "none", overflowY: "visible"});
        const naturalHeight = Math.ceil(pop.getBoundingClientRect().height);
        const height = Math.min(naturalHeight, available);
        const below = window.innerHeight - r.bottom - gap - edge;
        const above = r.top - gap - edge;
        const useAbove = below < height && above > below;
        const targetTop = useAbove ? r.top - gap - height : r.bottom + gap;
        const top = Math.max(edge, Math.min(targetTop, window.innerHeight - edge - height));
        const left = Math.max(edge, Math.min(r.left + (r.width - width) / 2, window.innerWidth - edge - width));
        this.popoverPlacement = useAbove ? "above" : "below";
        this.popoverStyle = {
          position: "fixed", top: `${top}px`, left: `${left}px`,
          width: `${width}px`, maxWidth: `calc(100vw - ${edge * 2}px)`,
          // Only exceptionally short viewports need an accessible scrolling fallback.
          maxHeight: naturalHeight > available ? `${available}px` : "none",
          overflowY: naturalHeight > available ? "auto" : "visible",
          zIndex: String(POPOVER_Z_INDEX),
        };
        this._applyPopoverStyle();
      },
      _finishPopoverPosition() {
        this.positionPopover();
        const pop = this.$refs.popover;
        const anchor = popoverAnchorEl(this.$el, this.$refs);
        if (pop && anchor) {
          const pr = pop.getBoundingClientRect();
          const r = anchor.getBoundingClientRect();
          const gap = 8;
          if (pr.bottom > window.innerHeight - gap) {
            const top = Math.max(gap, r.top - gap - pr.height);
            this.popoverPlacement = "above";
            this.popoverStyle = { ...this.popoverStyle, top: `${top}px` };
          }
          if (pr.top < gap) {
            this.popoverStyle = { ...this.popoverStyle, top: `${gap}px` };
          }
          this._applyPopoverStyle();
        }
        const style = this.popoverStyle || {};
        return Boolean(style.position === "fixed" && style.top);
      },
      openCalendar() {
        if (this.iso) {
          const j = jalaliFromIso(this.iso);
          if (j) {
            this.viewJy = j.jy;
            this.viewJm = j.jm;
          }
        }
        const anchor = popoverAnchorEl(this.$el, this.$refs);
        if (anchor && typeof anchor.scrollIntoView === "function") {
          try {
            anchor.scrollIntoView({ block: "nearest", inline: "nearest" });
          } catch (_e) {
            /* noop */
          }
        }
        this.open = true;
        const finalizeOpen = () => {
          const ready = this._finishPopoverPosition();
          if (!ready) this.positionPopover();
          this._bindPopoverFollow();
          lucideRefreshIn(this.$el);
          const pop = this.$refs.popover;
          if (pop) lucideRefreshIn(pop);
          window.__beautyosJalaliCalendarOpen = true;
          return ready;
        };
        this.$nextTick(() => {
          if (finalizeOpen()) return;
          requestAnimationFrame(() => {
            if (!this.open) return;
            if (finalizeOpen()) return;
            requestAnimationFrame(() => {
              if (!this.open) return;
              finalizeOpen();
            });
          });
        });
      },
      closeCalendar() {
        this.open = false;
        this._unbindPopoverFollow();
        window.__beautyosJalaliCalendarOpen = false;
        const pop = this.$refs.popover;
        if (pop) {
          pop.style.opacity = "";
          pop.style.visibility = "";
        }
      },
      toggleCalendar() {
        if (this.open) this.closeCalendar();
        else this.openCalendar();
      },
    };
  }

  function registerJalaliAlpine() {
    Alpine.data("jalaliDateField", (config) => ({
      ...jalaliPopoverMixin(),
      name: config.name,
      iso: config.iso || "",
      display: config.display ? toFa(config.display) : "",
      maxIso: config.maxIso || "",
      birthPicker: Boolean(config.birthPicker),
      monthsFaList: MONTHS_FA,
      open: false,
      viewJy: 1403,
      viewJm: 1,
      weekdays: WEEKDAYS_FA,
      get maxJalaliYear() {
        if (!this.maxIso) return 1450;
        const j = jalaliFromIso(this.maxIso);
        return j ? j.jy : 1450;
      },
      init() {
        if (this.iso) {
          const j = jalaliFromIso(this.iso);
          if (j) {
            this.viewJy = j.jy;
            this.viewJm = j.jm;
            this.display = displayFromIso(this.iso);
          }
        } else {
          const j = jalaliFromIso(todayIso());
          this.viewJy = j.jy;
          this.viewJm = j.jm;
        }
        this.$nextTick(() => lucideRefreshIn(this.$el));
      },
      setIso(iso) {
        const next = iso || "";
        if (this.iso !== next) {
          this.iso = next;
          emitJalaliChange(this.$el, this.name, next);
        } else if (!next) {
          this.iso = "";
          emitJalaliChange(this.$el, this.name, "");
        }
      },
      onDisplayPaste(event) {
        event.preventDefault();
        const text = (event.clipboardData || window.clipboardData).getData("text") || "";
        const digits = extractDateDigits(text);
        this.display = formatJalaliDigits(digits);
        this.syncIsoFromDisplay(false);
        const el = this.$refs.displayInput;
        if (el) {
          const pos = this.display.length;
          requestAnimationFrame(() => {
            try {
              el.setSelectionRange(pos, pos);
            } catch (_e) {
              /* noop */
            }
          });
        }
      },
      onDisplayInput(event) {
        const el = event.target;
        const deleting = Boolean(event.inputType && event.inputType.startsWith("delete"));
        const raw = el.value || "";
        const digits = extractDateDigits(raw);
        const formatted = formatJalaliDigits(digits);
        this.display = formatted;
        this.syncIsoFromDisplay(!deleting && digits.length === 8);
        const pos = caretAfterJalaliFormat(digits.length);
        requestAnimationFrame(() => {
          try {
            el.setSelectionRange(pos, pos);
          } catch (_e) {
            /* noop */
          }
        });
      },
      syncIsoFromDisplay(requireFull) {
        const digits = extractDateDigits(this.display);
        if (!digits) {
          this.setIso("");
          return;
        }
        const parsed = parseDisplay(this.display);
        if (parsed) {
          if (this.isIsoDisabled(parsed.iso)) {
            this.setIso("");
            return;
          }
          this.setIso(parsed.iso);
          this.viewJy = parsed.jy;
          this.viewJm = parsed.jm;
          return;
        }
        if (requireFull || digits.length === 8) {
          this.setIso("");
        }
      },
      get monthLabelFa() {
        return `${MONTHS_FA[this.viewJm - 1]} ${toFa(this.viewJy)}`;
      },
      get cells() {
        const len = jalaliMonthLength(this.viewJy, this.viewJm);
        const firstWd = jalaliWeekday(this.viewJy, this.viewJm, 1);
        const cells = [];
        const today = todayIso();
        const sel = this.iso;
        for (let i = 0; i < firstWd; i++) {
          cells.push({ inMonth: false, label: "", selected: false, today: false });
        }
        for (let d = 1; d <= len; d++) {
          const iso = isoFromJalali(this.viewJy, this.viewJm, d);
          const disabled = this.isIsoDisabled(iso);
          cells.push({
            inMonth: true,
            jy: this.viewJy,
            jm: this.viewJm,
            jd: d,
            label: toFa(d),
            selected: sel === iso,
            today: today === iso,
            disabled,
          });
        }
        while (cells.length % 7 !== 0) {
          cells.push({ inMonth: false, label: "", selected: false, today: false, disabled: false });
        }
        return cells;
      },
      prevMonth() {
        if (this.viewJm === 1) {
          this.viewJm = 12;
          this.viewJy -= 1;
        } else this.viewJm -= 1;
      },
      nextMonth() {
        if (this.viewJm === 12) {
          this.viewJm = 1;
          this.viewJy += 1;
        } else this.viewJm += 1;
      },
      pick(cell) {
        if (!cell.inMonth || cell.disabled) return;
        const iso = isoFromJalali(cell.jy, cell.jm, cell.jd);
        if (this.isIsoDisabled(iso)) return;
        this.setIso(iso);
        this.display = toFa(`${cell.jy}/${String(cell.jm).padStart(2, "0")}/${String(cell.jd).padStart(2, "0")}`);
        this.closeCalendar();
      },
      pickToday() {
        const iso = todayIso();
        if (this.isIsoDisabled(iso)) return;
        this.setIso(iso);
        this.display = displayFromIso(iso);
        const j = jalaliFromIso(iso);
        if (j) {
          this.viewJy = j.jy;
          this.viewJm = j.jm;
        }
        this.closeCalendar();
      },
      commitTyped() {
        const digits = extractDateDigits(this.display);
        if (!digits) {
          this.display = "";
          this.setIso("");
          return;
        }
        const parsed = parseDisplay(this.display);
        if (!parsed) {
          this.setIso("");
          return;
        }
        if (this.isIsoDisabled(parsed.iso)) {
          this.setIso("");
          return;
        }
        this.setIso(parsed.iso);
        this.display = toFa(`${parsed.jy}/${String(parsed.jm).padStart(2, "0")}/${String(parsed.jd).padStart(2, "0")}`);
        this.viewJy = parsed.jy;
        this.viewJm = parsed.jm;
      },
    }));

    Alpine.data("jalaliWeekPicker", (initialIso) => ({
      ...jalaliPopoverMixin(),
      iso: initialIso || todayIso(),
      display: displayFromIso(initialIso || todayIso()),
      open: false,
      viewJy: 1403,
      viewJm: 1,
      weekdays: WEEKDAYS_FA,
      _ignoreBlurSubmit: false,
      init() {
        const j = jalaliFromIso(this.iso) || jalaliFromIso(todayIso());
        this.viewJy = j.jy;
        this.viewJm = j.jm;
        this.display = displayFromIso(this.iso);
        this.$nextTick(() => lucideRefreshIn(this.$el));
      },
      get monthLabelFa() {
        return `${MONTHS_FA[this.viewJm - 1]} ${toFa(this.viewJy)}`;
      },
      get cells() {
        const len = jalaliMonthLength(this.viewJy, this.viewJm);
        const firstWd = jalaliWeekday(this.viewJy, this.viewJm, 1);
        const cells = [];
        const today = todayIso();
        for (let i = 0; i < firstWd; i++) cells.push({ inMonth: false, label: "" });
        for (let d = 1; d <= len; d++) {
          const iso = isoFromJalali(this.viewJy, this.viewJm, d);
          cells.push({
            inMonth: true,
            jy: this.viewJy,
            jm: this.viewJm,
            jd: d,
            label: toFa(d),
            selected: this.iso === iso,
            today: today === iso,
          });
        }
        while (cells.length % 7 !== 0) cells.push({ inMonth: false, label: "" });
        return cells;
      },
      prevMonth() {
        if (this.viewJm === 1) {
          this.viewJm = 12;
          this.viewJy -= 1;
        } else this.viewJm -= 1;
      },
      nextMonth() {
        if (this.viewJm === 12) {
          this.viewJm = 1;
          this.viewJy += 1;
        } else this.viewJm += 1;
      },
      submitWeek() {
        const form = this.$el.closest("form");
        if (!form) return;
        const hidden = form.querySelector('[name="week"]');
        if (hidden) hidden.value = this.iso;
        form.submit();
      },
      onDisplayInput(event) {
        const el = event.target;
        const digits = extractDateDigits(el.value || "");
        const formatted = formatJalaliDigits(digits);
        this.display = formatted;
        const parsed = parseDisplay(formatted);
        if (parsed) this.iso = parsed.iso;
        else if (!digits) this.iso = "";
        const pos = caretAfterJalaliFormat(digits.length);
        requestAnimationFrame(() => {
          try {
            el.setSelectionRange(pos, pos);
          } catch (_e) {
            /* noop */
          }
        });
      },
      onDisplayPaste(event) {
        event.preventDefault();
        const text = (event.clipboardData || window.clipboardData).getData("text") || "";
        const digits = extractDateDigits(text);
        this.display = formatJalaliDigits(digits);
        const parsed = parseDisplay(this.display);
        if (parsed) this.iso = parsed.iso;
        else if (!digits) this.iso = "";
      },
      commitTyped() {
        const digits = extractDateDigits(this.display);
        if (!digits) {
          this.display = "";
          this.iso = "";
          return;
        }
        const parsed = parseDisplay(this.display);
        if (!parsed) return;
        this.iso = parsed.iso;
        this.display = displayFromIso(this.iso);
        this.submitWeek();
      },
      formatOnBlur() {
        const digits = extractDateDigits(this.display);
        if (!digits) {
          this.display = "";
          this.iso = "";
          return;
        }
        const parsed = parseDisplay(this.display);
        if (parsed) {
          this.iso = parsed.iso;
          this.display = displayFromIso(this.iso);
          this.viewJy = parsed.jy;
          this.viewJm = parsed.jm;
        }
      },
      pick(cell) {
        if (!cell.inMonth) return;
        this.iso = isoFromJalali(cell.jy, cell.jm, cell.jd);
        this.display = displayFromIso(this.iso);
        this.closeCalendar();
        this.submitWeek();
      },
      pickToday() {
        const iso = todayIso();
        this.iso = iso;
        this.display = displayFromIso(iso);
        const j = jalaliFromIso(iso);
        if (j) {
          this.viewJy = j.jy;
          this.viewJm = j.jm;
        }
        this.closeCalendar();
        this.submitWeek();
      },
    }));

    function isoAddDays(iso, days) {
      const gy = +iso.slice(0, 4);
      const gm = +iso.slice(5, 7);
      const gd = +iso.slice(8, 10);
      const d = new Date(gy, gm - 1, gd);
      d.setDate(d.getDate() + days);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }

    Alpine.data("staffHoursWeekdaySync", (weekStartIso) => ({
      weekStart: weekStartIso || todayIso(),
      dateHint: "",
      init() {
        this.$el.addEventListener("jalali-change", (e) => {
          if (e.detail.name !== "reference_date") return;
          this.syncFromReferenceIso(e.detail.iso);
        });
        const refHidden = this.$el.querySelector('[name="reference_date"]');
        if (refHidden && refHidden.value) {
          this.syncFromReferenceIso(refHidden.value);
        } else {
          this.applyWeekdaySelect();
        }
        const wd = this.$el.querySelector('[name="weekday"]');
        if (wd) {
          wd.addEventListener("change", () => this.applyWeekdaySelect());
        }
      },
      syncFromReferenceIso(iso) {
        if (!iso) {
          this.dateHint = "";
          return;
        }
        const wd = isoWeekdaySat0(iso);
        const select = this.$el.querySelector('[name="weekday"]');
        if (select !== null && wd !== null) select.value = String(wd);
        const display = this.$el.querySelector(".jalali-date__display");
        this.dateHint = display ? display.value : displayFromIso(iso);
      },
      applyWeekdaySelect() {
        const select = this.$el.querySelector('[name="weekday"]');
        const refHidden = this.$el.querySelector('[name="reference_date"]');
        if (!select || !refHidden) return;
        const wd = parseInt(select.value, 10);
        if (Number.isNaN(wd)) return;
        const iso = isoAddDays(this.weekStart, wd);
        refHidden.value = iso;
        this.dateHint = displayFromIso(iso);
        const root = this.$el.querySelector("[data-jalali-date]");
        if (root && root._x_dataStack && root._x_dataStack[0]) {
          const data = root._x_dataStack[0];
          data.iso = iso;
          data.display = this.dateHint;
        }
        emitJalaliChange(this.$el, "reference_date", iso);
      },
    }));

    Alpine.data("jalaliDaySubmit", (initialIso, serverToday) => ({
      ...jalaliPopoverMixin(),
      directNavigation: true,
      monthsFaList: MONTHS_FA,
      minIso: "1900-01-01",
      maxIso: "2200-12-31",
      _dayForm: null,
      iso: initialIso || todayIso(),
      display: displayFromIso(initialIso || todayIso()),
      open: false,
      viewJy: 1403,
      viewJm: 1,
      weekdays: WEEKDAYS_FA,
      init() {
        // Capture the original form before the calendar is teleported into body.
        this._dayForm = this.$el.closest("form");
        const j = jalaliFromIso(this.iso) || jalaliFromIso(todayIso());
        this.viewJy = j.jy;
        this.viewJm = j.jm;
        this.display = displayFromIso(this.iso);
        this.$nextTick(() => lucideRefreshIn(this.$el));
      },
      get yearOptions() {
        const first = jalaliFromIso(this.minIso).jy;
        const last = jalaliFromIso(this.maxIso).jy;
        return Array.from({ length: last-first+1 }, (_, i) => ({value:first+i,label:toFa(first+i)}));
      },
      get monthOptions() {
        return MONTHS_FA.map((label,i)=>({value:i+1,label,disabled:!this.monthInBounds(this.viewJy,i+1)}));
      },
      monthInBounds(jy,jm) {
        return isoFromJalali(jy,jm,1)<=this.maxIso &&
          isoFromJalali(jy,jm,jalaliMonthLength(jy,jm))>=this.minIso;
      },
      isIsoDisabled(iso) {
        return !iso || iso<this.minIso || iso>this.maxIso;
      },
      setViewYear(year) {
        const first=jalaliFromIso(this.minIso),last=jalaliFromIso(this.maxIso);
        if (!Number.isInteger(year) || year<first.jy || year>last.jy) return;
        this.viewJy=year;
        if (year===first.jy) this.viewJm=Math.max(first.jm,this.viewJm);
        if (year===last.jy) this.viewJm=Math.min(last.jm,this.viewJm);
      },
      setViewMonth(month) {
        if (Number.isInteger(month) && month>=1 && month<=12 && this.monthInBounds(this.viewJy,month)) this.viewJm=month;
      },
      shiftedMonth(delta) {
        const index=this.viewJy*12+this.viewJm-1+delta;
        return {jy:Math.floor(index/12),jm:index%12+1};
      },
      canMoveMonth(delta) {
        const {jy,jm}=this.shiftedMonth(delta);
        return this.monthInBounds(jy,jm);
      },
      moveMonth(delta) {
        if (!this.canMoveMonth(delta)) return;
        const {jy,jm}=this.shiftedMonth(delta);
        this.viewJy=jy;
        this.viewJm=jm;
      },
      get monthLabelFa() {
        return `${MONTHS_FA[this.viewJm - 1]} ${toFa(this.viewJy)}`;
      },
      get cells() {
        const len = jalaliMonthLength(this.viewJy, this.viewJm);
        const firstWd = jalaliWeekday(this.viewJy, this.viewJm, 1);
        const cells = [];
        const today = serverToday || todayIso();
        for (let i = 0; i < firstWd; i++) cells.push({ inMonth: false, label: "" });
        for (let d = 1; d <= len; d++) {
          const iso = isoFromJalali(this.viewJy, this.viewJm, d);
          cells.push({
            inMonth: true,
            jy: this.viewJy,
            jm: this.viewJm,
            jd: d,
            label: toFa(d),
            selected: this.iso === iso,
            today: today === iso,
            disabled: this.isIsoDisabled(iso),
          });
        }
        while (cells.length % 7 !== 0) cells.push({ inMonth: false, label: "" });
        return cells;
      },
      prevMonth() { this.moveMonth(-1); },
      nextMonth() { this.moveMonth(1); },
      pick(cell) {
        if (!cell.inMonth || cell.disabled) return;
        const iso = isoFromJalali(cell.jy, cell.jm, cell.jd);
        if (this.isIsoDisabled(iso)) return;
        this.iso = iso;
        this.display = displayFromIso(this.iso);
        this.closeCalendar();
        this.submitDayForm();
      },
      pickToday() {
        const iso = serverToday || todayIso();
        if (this.isIsoDisabled(iso)) return;
        this.iso = iso;
        this.display = displayFromIso(iso);
        const j = jalaliFromIso(iso);
        if (j) {
          this.viewJy = j.jy;
          this.viewJm = j.jm;
        }
        this.closeCalendar();
        this.submitDayForm();
      },
      submitDayForm() {
        const form = this._dayForm;
        if (!form) return;
        const hidden = form.querySelector('[name="day"]');
        if (hidden) hidden.value = this.iso;
        form.submit();
      },
    }));
  }

  document.addEventListener("alpine:init", registerJalaliAlpine);
})();
