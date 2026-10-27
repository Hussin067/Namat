import { useMemo } from 'react'
import { useI18n } from '../../i18n/i18n-context.js'
import { useTheme } from '../../theme/theme-context.js'

/**
 * Colours, fonts and shared options for Chart.js, read from the design tokens
 * in index.css. Recomputed when the theme or language changes, so text, grid
 * lines, tooltips and legends stay readable in light and dark mode and in RTL.
 */
export function useChartTheme() {
  const { theme } = useTheme()
  const { lang, locale } = useI18n()

  return useMemo(() => {
    const css = getComputedStyle(document.documentElement)
    const token = (name) => css.getPropertyValue(name).trim()
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const rtl = lang === 'ar'
    const font = { family: getComputedStyle(document.body).fontFamily, size: 12 }

    const colors = {
      ink: token('--ink'),
      muted: token('--ink-muted'),
      line: token('--line'),
      surface: token('--surface'),
      brand: token('--brand'),
      series: [1, 2, 3, 4, 5, 6, 7].map((i) => token(`--chart-${i}`)),
    }

    // Options every chart shares. Animation is short, and off entirely for
    // people who asked their device for reduced motion.
    const base = {
      responsive: true,
      maintainAspectRatio: false,
      locale,
      animation: reducedMotion ? false : { duration: 250 },
      plugins: {
        legend: { rtl, textDirection: rtl ? 'rtl' : 'ltr', labels: { color: colors.ink, font, boxWidth: 12, boxHeight: 12 } },
        tooltip: {
          rtl,
          textDirection: rtl ? 'rtl' : 'ltr',
          backgroundColor: colors.surface,
          titleColor: colors.ink,
          bodyColor: colors.ink,
          borderColor: colors.line,
          borderWidth: 1,
          padding: 10,
          titleFont: { ...font, weight: '600' },
          bodyFont: font,
          displayColors: true,
          boxPadding: 4,
        },
      },
    }

    // Time always runs left to right (oldest → newest), in every language.
    const axis = (extra = {}) => ({
      grid: { color: colors.line, drawTicks: false },
      border: { display: false },
      ticks: { color: colors.muted, font, padding: 8 },
      ...extra,
    })

    // `theme` is part of the result so charts redraw whenever the CSS variables change.
    return { theme, colors, font, base, axis, rtl, locale }
  }, [theme, lang, locale])
}

/** A colour with transparency, from a #rrggbb token. */
export function withAlpha(hex, alpha) {
  const n = Number.parseInt(hex.replace('#', ''), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}
