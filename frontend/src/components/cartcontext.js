import { createContext, useContext, useState, useEffect } from "react";

const CartContext = createContext();

export function CartProvider({ children }) {
  const [selected, setSelected] = useState({});
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let sum = 0;
    for (const k of Object.keys(selected)) {
      const s = selected[k];
      if (s) sum += s.price * (s.qty || 1);
    }
    setTotal(sum);
  }, [selected]);

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