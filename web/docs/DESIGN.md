# Athena Web Design Tokens

Extended from Streamlit demo (`app/components.py` + default light theme).

## Colors

| Token | Hex | Usage |
|-------|-----|--------|
| primary | `#FF4B4B` | CTA, links, brand |
| background | `#FFFFFF` | Page |
| surface | `#F0F2F6` | Sidebar, cards |
| foreground | `#31333F` | Body text |
| verified | `#D4EDDA` | Citation OK |
| not-found | `#F8D7DA` | Citation missing |
| mismatch | `#FFF3CD` | Citation mismatch / warnings |

## Typography

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
```

## Radius

Default `8px` (`rounded-lg`).

## Dark mode

Not in scope for v1; Tailwind `dark:` hooks reserved for later.
