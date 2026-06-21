import { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from "./AuthContext";

const CartContext = createContext();

export function CartProvider({ children }) {
  const { user } = useAuth();
  
  const [selected, setSelected] = useState({});
  const [total, setTotal] = useState(0);

  // Switch cart when user logs in/out
  useEffect(() => {
    const key = `pc_cart_${user ? user.email : 'guest'}`;
    const saved = localStorage.getItem(key);
    setSelected(saved ? JSON.parse(saved) : {});
  }, [user]);

  // Save cart changes to localStorage for the active user
  useEffect(() => {
    const key = `pc_cart_${user ? user.email : 'guest'}`;
    localStorage.setItem(key, JSON.stringify(selected));
    
    let sum = 0;
    for (const k of Object.keys(selected)) {
      const s = selected[k];
      if (s) sum += s.price * (s.qty || 1);
    }
    setTotal(sum);
  }, [selected, user]);

  const addOrUpdateItem = (category, item, qty) => {
    setSelected((prev) => ({
      ...prev,
      [category]: { ...item, qty },
    }));
  };

  const updateQuantity = (category, qty) => {
    setSelected((prev) => ({
      ...prev,
      [category]: { ...prev[category], qty },
    }));
  };

  const removeItem = (category) => {
    setSelected((prev) => {
      const updated = { ...prev };
      delete updated[category];
      return updated;
    });
  };

  const clearCart = () => setSelected({});

  const cartItems = Object.values(selected);

  return (
    <CartContext.Provider
      value={{
        selected,
        total,
        cartItems,
        addOrUpdateItem,
        updateQuantity,
        removeItem,
        clearCart,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);