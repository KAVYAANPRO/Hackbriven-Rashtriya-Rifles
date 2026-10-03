// Subscription plan definitions
export const PLANS = {
  FREE: {
    id: 'free',
    name: 'Free',
    credits: 5,
    price: 0,
    features: ['5 AI presentations/month', 'Basic templates', 'PNG export'],
  },
  STARTER: {
    id: 'starter',
    name: 'Starter',
    credits: 50,
    price: 299,
    features: ['50 AI presentations/month', 'All templates', 'PDF & PPT export', 'Custom branding'],
  },
  PRO: {
    id: 'pro',
    name: 'Pro',
    credits: 200,
    price: 799,
    features: [
      '200 AI presentations/month',
      'All templates',
      'All export formats',
      'Custom branding',
      'Analytics dashboard',
      'Priority support',
    ],
  },
  ENTERPRISE: {
    id: 'enterprise',
    name: 'Enterprise',
    credits: Infinity,
    price: null,
    features: ['Unlimited presentations', 'Custom AI model', 'SSO', 'Dedicated support', 'API access'],
  },
};

export const PLAN_LIST = Object.values(PLANS);
export const PAID_PLANS = PLAN_LIST.filter((p) => p.price > 0 && p.price !== null);
