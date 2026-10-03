// Loads Razorpay Checkout.js on demand, once.
const SRC = 'https://checkout.razorpay.com/v1/checkout.js';
let pending = null;

export function loadRazorpay() {
  if (typeof window !== 'undefined' && window.Razorpay) return Promise.resolve(window.Razorpay);
  if (pending) return pending;
  pending = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = SRC;
    s.async = true;
    s.onload = () => {
      if (window.Razorpay) resolve(window.Razorpay);
      else { pending = null; reject(new Error('Razorpay Checkout loaded but is not available.')); }
    };
    s.onerror = () => {
      pending = null;
      s.remove();
      reject(new Error('Could not load Razorpay Checkout. Check your connection and try again.'));
    };
    document.head.appendChild(s);
  });
  return pending;
}
