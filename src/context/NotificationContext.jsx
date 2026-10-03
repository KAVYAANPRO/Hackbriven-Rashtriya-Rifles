import { createContext, useContext, useState, useCallback } from 'react';

const NotificationContext = createContext(null);

let notificationId = 0;

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  const notify = useCallback(({ message, type = 'info', duration = 4000 }) => {
    const id = ++notificationId;
    setNotifications((prev) => [...prev, { id, message, type }]);
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, []);

  const dismiss = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const success = useCallback((msg, opts = {}) => notify({ message: msg, type: 'success', ...opts }), [notify]);
  const error = useCallback((msg, opts = {}) => notify({ message: msg, type: 'error', ...opts }), [notify]);
  const warn = useCallback((msg, opts = {}) => notify({ message: msg, type: 'warning', ...opts }), [notify]);

  return (
    <NotificationContext.Provider value={{ notifications, notify, dismiss, success, error, warn }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotification must be used within NotificationProvider');
  return ctx;
}
