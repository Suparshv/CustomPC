import { useCart } from "./cartcontext";
import { useState } from "react";
import axios from "axios"
import { useAuth } from "../components/AuthContext";
import { useNotification } from "../components/notificationcontext";
import { useNavigate } from "react-router-dom";

export default function CartDrawer({ isOpen, onClose }) {
  const { cartItems, updateQuantity, removeItem, total, selected } = useCart();
  const [removingItems, setRemovingItems] = useState([]);
  const { user } = useAuth();
  const handleRemove = (category) => {
    setRemovingItems((prev) => [...prev, category]);
    setTimeout(() => {
      removeItem(category);
      setRemovingItems((prev) => prev.filter((c) => c !== category));
    }, 300); 
  };
  const { showNotification } = useNotification();
  const navigate = useNavigate();

  const handleCheckout = () => {
    if (!user) {
      showNotification("Please login before checkout.", "danger");
      return;
    }
    onClose();
    navigate('/checkout');
  };

  return (
    <div className={`cart-drawer ${isOpen ? "open" : ""}`}>
      <div className="cart-header d-flex justify-content-between p-3">
        <h4 className="text1">Cart</h4>
        <button className="btn-close" onClick={onClose}></button>
      </div>

      <div className="cart-body p-3 border-top">
        {cartItems.length === 0 ? (
          <p style={{fontFamily:'GothamM'}}>Your cart is empty</p>
        ) : (
          cartItems.map((item) => {
            const category = Object.keys(selected).find(
              (key) => selected[key].id === item.id
            );
            return (
              <div
                key={item.id}
                className={`cart-item ${
                  removingItems.includes(category) ? "removing" : ""
                }`}
              >
                {item.image && <img src={item.image} alt={item.name} className="cart-item-image" />}
                <div className="cart-item-info">
                  <div className="cart-item-info-name">{item.name}</div>
                  <div className="cart-item-info-price">
                    ₹{(item.price * item.qty).toLocaleString('en-IN')}
                  </div>
                </div>
                
                <div className="cart-item-actions">   
                  <input
                    type="number"
                    min="1"
                    value={item.qty}
                    onChange={(e) =>
                      updateQuantity(
                        category,
                        Math.max(1, Number(e.target.value))
                      )
                    }
                  />
                  <button
                    className="btn btn-sm btn-outline-danger w-100"
                    onClick={() => handleRemove(category)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="cart-footer p-3 border-top">
        <h6 style={{fontFamily:'GothamM'}}>Total: ₹{total.toLocaleString('en-IN')}</h6>
        <button className="button-animate w-100 mt-2" onClick={handleCheckout}>
          <span>Checkout</span>
        </button>
      </div>
    </div>
  );
}
