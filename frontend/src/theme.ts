import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

export const BRAND_GRADIENT = 'linear(to-r, brand.500, accent.500)';

export const theme = extendTheme({
  config,
  fonts: {
    heading: `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`,
    body: `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`,
  },
  colors: {
    brand: {
      50: '#f3efff',
      100: '#e1d6ff',
      200: '#c4adff',
      300: '#a684ff',
      400: '#8b5cf6',
      500: '#7c3aed',
      600: '#6d28d9',
      700: '#5b21b6',
      800: '#4c1d95',
      900: '#2e1065',
    },
    accent: {
      50: '#eaf2ff',
      100: '#cfe0ff',
      200: '#a3c2ff',
      300: '#76a3ff',
      400: '#4f86fb',
      500: '#3b6ff0',
      600: '#2a57d4',
      700: '#1f43aa',
      800: '#183482',
      900: '#10235a',
    },
  },
  radii: {
    card: '1.25rem',
  },
  shadows: {
    glass: '0 8px 32px rgba(76, 29, 149, 0.12)',
    glassHover: '0 16px 48px rgba(76, 29, 149, 0.2)',
    outline: '0 0 0 3px rgba(124, 58, 237, 0.45)',
  },
  semanticTokens: {
    colors: {
      'bg.canvas': { default: 'gray.50', _dark: 'gray.900' },
      'bg.glass': { default: 'whiteAlpha.700', _dark: 'whiteAlpha.100' },
      'border.glass': { default: 'whiteAlpha.800', _dark: 'whiteAlpha.200' },
      'text.muted': { default: 'gray.600', _dark: 'gray.400' },
    },
  },
  styles: {
    global: {
      'html, body': {
        bg: 'bg.canvas',
        color: 'gray.800',
        minHeight: '100%',
      },
      '#root': {
        minHeight: '100vh',
      },
    },
  },
  components: {
    Button: {
      defaultProps: { colorScheme: 'brand' },
      baseStyle: { borderRadius: 'full', fontWeight: 'semibold' },
    },
    Input: {
      defaultProps: { focusBorderColor: 'brand.500' },
    },
    Textarea: {
      defaultProps: { focusBorderColor: 'brand.500' },
    },
    Link: {
      baseStyle: { _hover: { textDecoration: 'none' } },
    },
  },
});
