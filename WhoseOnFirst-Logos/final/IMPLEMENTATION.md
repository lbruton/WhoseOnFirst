# WhoseOnFirst — Brand Kit Implementation Guide

## Files

| File | Purpose | Where to use |
|------|---------|-------------|
| `icon-logo.svg` | Full app icon with "WHO'S ON / FIRST" text | App store listing, about page, splash screen |
| `icon-bare.svg` | Icon without text (centered, larger person) | Favicon source, PWA icon, tab bar, mobile home screen |
| `banner-logo.svg` | Sidebar header — icon + "WhoseOnFirst" + tagline | Sidebar top (280×48), login page header |
| `banner-logo-compact.svg` | Sidebar header — icon + "WhoseOnFirst" only | Tight sidebar (220×40), mobile header |
| `avatar-admin.svg` | Admin role avatar — green circle, gold star badge | User list, sidebar profile, admin indicators |
| `avatar-viewer.svg` | Viewer role avatar — blue circle, eye badge | User list, sidebar profile, viewer indicators |

## Color Palette

```css
:root {
  /* Primary — Green (from Variant C) */
  --wof-green-600: #059669;
  --wof-green-500: #10B981;

  /* Accent — Gold (1ST badge, admin star) */
  --wof-gold-400: #FCD34D;
  --wof-gold-500: #FBBF24;
  --wof-gold-600: #F59E0B;

  /* Viewer role — Sky blue */
  --wof-blue-500: #0EA5E9;
  --wof-blue-400: #38BDF8;

  /* Sidebar / dark surfaces */
  --wof-sidebar-bg: #1E293B;     /* slate-800 */
  --wof-sidebar-text: #F8FAFC;   /* slate-50 */
  --wof-sidebar-muted: #94A3B8;  /* slate-400 */
}
```

## Typography

The logos use `Inter` as the primary font with fallbacks:

```css
font-family: 'Inter', 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
```

## Usage in Sidebar

Replace the current clock icon + "WhoseOnFirst" text with:

```html
<!-- Sidebar header -->
<div class="sidebar-brand">
  <img src="/assets/img/banner-logo.svg" alt="WhoseOnFirst" height="48" />
</div>

<!-- User profile area -->
<div class="sidebar-user">
  <img src="/assets/img/avatar-admin.svg" alt="Admin" width="32" height="32" />
  <div>
    <span class="user-name">admin</span>
    <span class="user-role">Administrator</span>
  </div>
</div>
```

## Favicon Setup

Use `icon-bare.svg` directly or convert to ICO/PNG:

```html
<!-- SVG favicon (modern browsers) -->
<link rel="icon" type="image/svg+xml" href="/assets/img/icon-bare.svg" />

<!-- PNG fallback -->
<link rel="icon" type="image/png" sizes="32x32" href="/assets/img/favicon-32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/assets/img/favicon-16.png" />
```

## Generating PNG Variants

If you need PNG versions at specific sizes:

```bash
# Requires Inkscape or rsvg-convert
# App icon PNGs
rsvg-convert -w 512 -h 512 icon-logo.svg > icon-512.png
rsvg-convert -w 192 -h 192 icon-logo.svg > icon-192.png
rsvg-convert -w 180 -h 180 icon-logo.svg > apple-touch-icon.png

# Favicons
rsvg-convert -w 32 -h 32 icon-bare.svg > favicon-32.png
rsvg-convert -w 16 -h 16 icon-bare.svg > favicon-16.png

# User avatars
rsvg-convert -w 64 -h 64 avatar-admin.svg > avatar-admin-64.png
rsvg-convert -w 64 -h 64 avatar-viewer.svg > avatar-viewer-64.png
```
