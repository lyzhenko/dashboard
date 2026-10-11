import type { ConfigProviderProps } from 'ant-design-vue'

export type ThemeConfig = NonNullable<ConfigProviderProps['theme']>

/**
 * Палитра: спокойный деловой вид, крупные цифры, ничего кричащего.
 * Цвета продублированы константами, чтобы использовать их в SVG и в CSS.
 */
export const COLORS = {
  primary: '#1f4e79',
  positive: '#237804',
  negative: '#a8071a',
  warning: '#ad6800',
  neutral: '#8c8c8c',
  text: '#1f1f1f',
  textSecondary: '#595959',
  border: '#e6ebf0',
  surface: '#ffffff',
  background: '#f4f6f9',
  bar: '#2f6fa8',
  barSoft: '#a9c6e0',
  line: '#d4770b',
  grid: '#eef1f5',
} as const

export const FONT_BODY =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
export const FONT_HEADING = "'Roboto Slab', 'Inter', Georgia, 'Times New Roman', serif"

export const theme: ThemeConfig = {
  token: {
    colorPrimary: COLORS.primary,
    colorInfo: COLORS.primary,
    colorSuccess: COLORS.positive,
    colorError: COLORS.negative,
    colorWarning: COLORS.warning,
    colorText: COLORS.text,
    colorTextSecondary: COLORS.textSecondary,
    colorBorderSecondary: COLORS.border,
    colorBgLayout: COLORS.background,
    fontFamily: FONT_BODY,
    fontSize: 14,
    borderRadius: 10,
    wireframe: false,
  },
  components: {
    // Карточки KPI читаются как плитки: тонкая рамка вместо тяжёлой тени.
    // Токены конкретных компонентов в типах Ant Design Vue 4.2 не описаны,
    // поэтому настраиваем только общие (alias) токены.
    Card: {
      paddingLG: 20,
    },
  },
}
