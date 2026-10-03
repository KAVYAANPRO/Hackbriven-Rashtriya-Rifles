// Animation preset utilities

export const DURATION = {
  fast: 150,
  normal: 300,
  slow: 500,
  crawl: 800,
};

export const EASING = {
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
};

export const transition = (props = 'all', duration = DURATION.normal, easing = EASING.easeOut) => {
  const propList = Array.isArray(props) ? props.join(', ') : props;
  return `${propList} ${duration}ms ${easing}`;
};

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

export const slideUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
};

export const stagger = (delay = 50) => ({
  animate: { transition: { staggerChildren: delay / 1000 } },
});
