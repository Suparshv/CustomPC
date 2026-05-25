// NotificationContext.js
import { createContext, useContext, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

const NotificationContext = createContext(null);

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  const showNotification = useCallback((message, type = "success", timeoutMs = 3000) => {
    const id = Date.now() + Math.random();
    setNotifications((prev) => [...prev, { id, message, type }]);

    // auto remove
    if (timeoutMs > 0) {
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, timeoutMs);
    }
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider
      value={{
        // expose both names so existing calls won't break
        showNotification,
        addNotification: showNotification,
        removeNotification,
      }}
    >
      {children}

      <div className="notification-container">
        <AnimatePresence>
          {notifications.map((n) => (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
              className={`notification ${n.type}`}
              onClick={() => removeNotification(n.id)}
              role="status"
            >
              {n.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <style>{`
        .notification-container {
          position: fixed;
          top: 1rem;
          right: 1rem;
          display: flex;
          flex-direction: column;
          gap: .5rem;
          z-index: 3000;
          pointer-events: none; /* let clicks through unless on a toast */
        }
        .notification {
          pointer-events: auto; /* clickable to dismiss */
          background: #333;
          color: #fff;
          padding: 10px 14px;
          border-radius: 8px;
          min-width: 220px;
          max-width: 360px;
          font-family: GothamM, system-ui, sans-serif;
          box-shadow: 0 6px 18px rgba(0,0,0,.18);
          cursor: pointer;
          line-height: 1.3;
        }
        .notification.success { background: #28a745; }
        .notification.error { background: #dc3545; }
        .notification.info { background: #0d6efd; }
        .notification.warn { background: #ffc107; color: #222; }
      `}</style>
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used inside NotificationProvider");
  return ctx;
}
