# Local runtime assets

Runtime assets are checked into Git so a deployed BeautyOS page does not need a third-party CDN. Do not replace them with remote script/font URLs.

- Alpine.js 3.14.8: cdnjs archived distribution, `ajax/libs/alpinejs/3.14.8/cdn.min.js`; upstream MIT license from alpinejs/alpine v3.14.8.
- HTMX 2.0.4: bigskysoftware/htmx v2.0.4, dist/htmx.min.js and upstream license.
- Vazirmatn v33.003: rastikerdar/vazirmatn, variable WOFF2 and OFL.
- Markazi Text: google/fonts, ofl/markazitext, variable TTF and OFL.
- Lucide: existing vendored script retained.

Update vendor assets deliberately and run browser regression tests after changes. npm and pip remain build-time dependencies.
