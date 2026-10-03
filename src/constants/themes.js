// Presentation theme definitions for deck generation
export const DECK_THEMES = [
  { id: 'dark-minimal', name: 'Dark Minimal', bg: '#0f172a', accent: '#6366f1' },
  { id: 'light-clean', name: 'Light Clean', bg: '#ffffff', accent: '#4f46e5' },
  { id: 'midnight-blue', name: 'Midnight Blue', bg: '#1e3a5f', accent: '#38bdf8' },
  { id: 'forest-deep', name: 'Forest Deep', bg: '#1a2e1a', accent: '#4ade80' },
  { id: 'sunset-warm', name: 'Sunset Warm', bg: '#1c1410', accent: '#fb923c' },
  { id: 'rose-gold', name: 'Rose Gold', bg: '#2d1b1b', accent: '#f43f5e' },
  { id: 'slate-pro', name: 'Slate Pro', bg: '#1e293b', accent: '#94a3b8' },
  { id: 'corporate-blue', name: 'Corporate Blue', bg: '#f8fafc', accent: '#1d4ed8' },
];

export const DEFAULT_THEME_ID = 'dark-minimal';
export const getTheme = (id) => DECK_THEMES.find((t) => t.id === id) ?? DECK_THEMES[0];
