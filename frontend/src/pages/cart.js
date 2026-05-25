import React from 'react';
import { useCart } from '../components/cartcontext';
import { useAuth } from '../components/AuthContext';
import { useNotification } from '../components/notificationcontext';
import { useNavigate } from 'react-router-dom';
import '../styles/cartpage.css';

export default function CartPage() {
  const { cartItems, updateQuantity, removeItem, total, selected, clearCart } = useCart();
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const navigate = useNavigate();

  const handleCheckout = () => {
    if (!user) {
      showNotification("Please login before checkout.", "danger");
      return;
    }
    navigate('/checkout');
  };

  if (cartItems.length === 0) {
    return (
      <div className="cart-page-container empty-cart text-center py-5">
        <div style={{ fontSize: '80px', color: '#ccc', marginBottom: '20px' }}>🛒</div>
        <h2>Your Cart is Empty</h2>
        <p className="text-muted">Looks like you haven't added any components yet.</p>
        <button className="btn-cart-primary mt-4" onClick={() => navigate('/pc')}>
          Start Building Your PC
        </button>
      </div>
    );
  }

  return (
    <div className="cart-page-container">
      <h2 className="cart-page-header">Shopping Cart</h2>
      
      <div className="cart-page-content">
        <div className="cart-items-list">
          {cartItems.map((item) => {
            const category = Object.keys(selected).find(
              (key) => selected[key]?.id === item.id
            );
            
            return (
              <div key={item.id} className="cart-page-item">
                <div className="cart-item-image-wrapper">
                  {item.image ? (
                    <img src={item.image} alt={item.name} className="cart-page-item-image" />
                  ) : (
                    <div className="cart-page-item-placeholder">No Image</div>
                  )}
                </div>
                
                <div className="cart-page-item-info">
                  <div className="cart-page-item-name">{item.name}</div>
                  <div className="cart-page-item-category text-muted">{category?.toUpperCase() || 'COMPONENT'}</div>
                </div>
                
                <div className="cart-page-item-controls">
                  <div className="cart-page-item-price">
                    ₹{(item.price * item.qty).toLocaleString('en-IN')}
                  </div>
                  <div className="cart-page-item-actions">
                    <input
                      type="number"
                      min="1"
                      value={item.qty}
                      onChange={(e) =>
                        updateQuantity(category, Math.max(1, Number(e.target.value)))
                      }
                      className="cart-page-qty-input"
                    />
                    <button
                      className="btn-remove-item"
                      onClick={() => removeItem(category)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        
        <div className="cart-page-summary">
          <h3>Order Summary</h3>
          <div className="summary-row">
            <span>Subtotal</span>
            <span>₹{Math.round(total / 1.18).toLocaleString('en-IN')}</span>
          </div>
          <div className="summary-row">
            <span>GST (18%)</span>
            <span>₹{(total - Math.round(total / 1.18)).toLocaleString('en-IN')}</span>
          </div>
          <div className="summary-row total-row">
            <span>Total</span>
            <span>₹{total.toLocaleString('en-IN')}</span>
          </div>
          <button className="btn-cart-primary w-100" onClick={handleCheckout}>
            Proceed to Checkout
          </button>
          <button 
            className="btn btn-outline-danger w-100 mt-2" 
            style={{ fontWeight: 'bold' }}
            onClick={() => { clearCart(); showNotification("Cart cleared successfully", "success"); }}
          >
            Clear Cart
          </button>
        </div>
      </div>
    </div>
  );
}
