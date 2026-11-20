/* Keyboard focus management for the shared teleported form dialogs.
   Existing Alpine close handlers and calendar overlays own Escape behavior. */
(function () {
  "use strict";
  const selector = ".luna-modal-root .luna-modal[role='dialog']";
  let active = null, returnFocus = null, queued = false;
  function visible(node) {
    return !!(node && node.isConnected && node.getClientRects().length &&
      getComputedStyle(node).visibility !== "hidden" && !node.closest("[x-cloak]"));
  }
  function focusable(root) {
    return Array.from(root.querySelectorAll('a[href],button,input,select,textarea,[tabindex],[contenteditable="true"]'))
      .filter(el => el.tabIndex >= 0 && !el.matches(":disabled") && !el.closest("[inert],[aria-hidden='true']") && visible(el));
  }
  function sync() {
    queued = false;
    const next = Array.from(document.querySelectorAll(selector)).filter(visible).at(-1) || null;
    if (next === active) return;
    if (next) {
      if (!active) returnFocus = document.activeElement;
      active = next;
      if (!next.contains(document.activeElement)) {
        (next.querySelector(".inventory-create-modal__title") || focusable(next)[0])?.focus({preventScroll:true});
      }
    } else {
      active = null;
      if (returnFocus && visible(returnFocus) && returnFocus !== document.body) returnFocus.focus({preventScroll:true});
      returnFocus = null;
    }
  }
  function queue() { if (!queued) { queued = true; requestAnimationFrame(sync); } }
  function init() {
    new MutationObserver(records => {
      for (const record of records) {
        if (record.type === "attributes" && (record.target.matches?.(".luna-modal-root") || record.target === document.documentElement)) { queue(); return; }
        if (record.type === "childList" && [...record.addedNodes, ...record.removedNodes].some(node =>
          node.nodeType === 1 && (node.matches?.(".luna-modal-root") || node.querySelector?.(".luna-modal-root")))) { queue(); return; }
      }
    }).observe(document.documentElement,{subtree:true, childList:true, attributes:true, attributeFilter:["style","x-cloak","class"]});
    document.addEventListener("keydown",event=>{
      if(event.key !== "Tab" || !visible(active) || window.__beautyosJalaliCalendarOpen) return;
      const items = focusable(active);
      if(!items.length) { event.preventDefault(); return; }
      const first = items[0], last = items[items.length-1], current = document.activeElement;
      if(!items.includes(current)) { event.preventDefault(); (event.shiftKey?last:first).focus(); }
      else if(event.shiftKey && current===first) { event.preventDefault(); last.focus(); }
      else if(!event.shiftKey && current===last) { event.preventDefault(); first.focus(); }
    });
    // Form-native image fields keep Django's clear checkbox and multipart submission.
    document.addEventListener("change", event => {
      const input=event.target;
      const wrap=input.closest?.("[data-luna-upload]");
      if(!wrap) return;
      const file=wrap.querySelector("input[type=file]");
      const clear=wrap.querySelector("input[type=checkbox]");
      const img=wrap.querySelector("[data-luna-preview]");
      const text=wrap.querySelector("[data-luna-file-name]");
      if(!file || !img || !text) return;
      if(input===clear && clear.checked) file.value="";
      if(input===file && file.files.length && clear) clear.checked=false;
      if(img.dataset.objectUrl){ URL.revokeObjectURL(img.dataset.objectUrl); delete img.dataset.objectUrl; }
      const selected=file.files[0];
      const original=img.dataset.originalSrc || "";
      const removed=!!clear?.checked;
      if(selected && selected.type.startsWith("image/")){
        img.dataset.objectUrl=URL.createObjectURL(selected);
        img.src=img.dataset.objectUrl;
      }else if(original && !removed){img.src=original;}
      else {img.removeAttribute("src");}
      img.hidden=!img.hasAttribute("src");
      const preview=wrap.querySelector(".luna-upload__preview svg,.luna-upload__preview i");
      if(preview) preview.toggleAttribute("hidden",!img.hidden);
      text.textContent=selected?selected.name:removed?"تصویر در زمان ذخیره حذف می‌شود":original?"تصویر فعلی ذخیره شده است":"یک تصویر انتخاب کنید";
    });
    queue();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",init,{once:true}); else init();
})();
