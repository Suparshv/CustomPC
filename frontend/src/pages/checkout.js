import React, { useState, useEffect } from 'react';
import { useCart } from '../components/cartcontext';
import { useAuth } from '../components/AuthContext';
import { useNotification } from '../components/notificationcontext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import '../styles/checkout.css';

const COUNTRIES = [
  { name: 'India', code: 'IN', flag: '🇮🇳' },
  { name: 'United States', code: 'US', flag: '🇺🇸' },
  { name: 'United Kingdom', code: 'GB', flag: '🇬🇧' },
  { name: 'Canada', code: 'CA', flag: '🇨🇦' },
  { name: 'Australia', code: 'AU', flag: '🇦🇺' },
  { name: 'Germany', code: 'DE', flag: '🇩🇪' },
  { name: 'France', code: 'FR', flag: '🇫🇷' },
  { name: 'Japan', code: 'JP', flag: '🇯🇵' },
];

export default function Checkout() {
  const { cartItems, total, clearCart } = useCart();
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [address, setAddress] = useState({
    addressLine1: '',
    addressLine2: '',
    addressLine3: '',
    area: '',
    city: '',
    state: '',
    pincode: '',
    country: 'IN'
  });
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [paymentDetails, setPaymentDetails] = useState({
    cardNumber: '',
    upiId: ''
  });
  const [isOrderSuccessful, setIsOrderSuccessful] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [savedAddress, setSavedAddress] = useState(null);
  const [useSavedAddress, setUseSavedAddress] = useState(false);

  useEffect(() => {
    if (!user) {
      showNotification('Please login to checkout', 'danger');
      navigate('/');
      return;
    }
    
    // Fetch user profile to get address
    const fetchProfile = async () => {
      try {
        const res = await axios.get(`http://localhost:5000/api/user/profile?email=${user.email}`);
        if (res.data.user && res.data.user.address && res.data.user.address.addressLine1) {
          setSavedAddress(res.data.user.address);
          setUseSavedAddress(true); // Default to using saved address if available
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchProfile();
  }, [user, navigate, showNotification]);

  if (isOrderSuccessful) {
    return (
      <div className="checkout-container text-center py-5">
        <div style={{ background: '#28a745', color: 'white', borderRadius: '50%', width: '100px', height: '100px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '50px', marginBottom: '20px' }}>
          ✓
        </div>
        <h2 style={{ fontFamily: 'GothamB', color: '#28a745' }}>Ordered Successfully!</h2>
        <p className="mt-3 text-muted">Your custom PC build has been saved.</p>
        <button className="btn-checkout-next w-auto px-5 mt-4" onClick={() => navigate('/')}>
          Back to Home
        </button>
      </div>
    );
  }

  if (cartItems.length === 0) {
    return (
      <div className="checkout-container text-center">
        <h2>Your Cart is Empty</h2>
        <button className="btn-checkout-next mt-4 w-auto" onClick={() => navigate('/pc')}>
          Build a PC
        </button>
      </div>
    );
  }

  const handleNextStep = (nextStep) => {
    if (nextStep === 3) {
      if (!useSavedAddress && (!address.addressLine1 || !address.city || !address.state || !address.pincode)) {
        showNotification('Please fill in required address details', 'danger');
        return;
      }
    }
    setStep(nextStep);
  };

  const handlePayment = async () => {
    if (paymentMethod === 'card' && !paymentDetails.cardNumber) {
      showNotification('Please enter card number', 'danger');
      return;
    }
    if (paymentMethod === 'upi' && !paymentDetails.upiId) {
      showNotification('Please enter UPI ID', 'danger');
      return;
    }
    
    setIsLoading(true);
    try {
      const payload = {
        username: user?.username,
        email: user?.email,
        shippingAddress: useSavedAddress ? savedAddress : address,
        paymentMethod: paymentMethod,
        mobileNo: user?.mobileNo || '',
        components: cartItems.map((item) => ({
          name: item.name,
          price: item.price,
          qty: item.qty,
        })),
        total,
      };
      
      await axios.post("http://localhost:5000/api/order", payload);
      setIsLoading(false);
      setIsOrderSuccessful(true);
      clearCart();
    } catch (err) {
      console.error(err);
      setIsLoading(false);
      const errorMessage = err.response?.data?.message || err.message || "Checkout failed. Try again.";
      showNotification(`Error: ${errorMessage}`, "danger");
    }
  };

  const subtotal = Math.round(total / 1.18);
  const gst = total - subtotal;



  return (
    <div className="checkout-container">
      <h2 className="checkout-header">Checkout</h2>

      {/* Step 1: Order Summary */}
      <div className="accordion-section">
        <div className="accordion-header" onClick={() => setStep(1)} style={{ cursor: 'pointer' }}>
          <h4>1. Order Summary</h4>
          <span>{step > 1 ? '✓' : ''}</span>
        </div>
        {step === 1 && (
          <div className="accordion-body">
            {cartItems.map((item) => (
              <div key={item.id} className="checkout-item">
                {item.image && <img src={item.image} alt={item.name} className="checkout-item-image" />}
                <div className="checkout-item-info">
                  <div className="checkout-item-name">{item.name}</div>
                  <div className="text-muted" style={{ fontSize: '12px' }}>Qty: {item.qty}</div>
                </div>
                <div className="checkout-item-price">
                  ₹{(item.price * item.qty).toLocaleString('en-IN')}
                </div>
              </div>
            ))}
            
            <div className="checkout-summary">
              <div className="checkout-summary-row">
                <span>Subtotal</span>
                <span>₹{subtotal.toLocaleString('en-IN')}</span>
              </div>
              <div className="checkout-summary-row">
                <span>GST (18%)</span>
                <span>₹{gst.toLocaleString('en-IN')}</span>
              </div>
              <div className="checkout-summary-total">
                <span>Total (Including GST)</span>
                <span>₹{total.toLocaleString('en-IN')}</span>
              </div>
            </div>
            
            <button className="btn-checkout-next" onClick={() => handleNextStep(2)}>
              Add Address to Ship To
            </button>
          </div>
        )}
      </div>

      {/* Step 2: Shipping Address */}
      <div className="accordion-section">
        <div className="accordion-header" onClick={() => step > 1 && setStep(2)} style={{ cursor: step > 1 ? 'pointer' : 'default', opacity: step >= 2 ? 1 : 0.6 }}>
          <h4>2. Shipping Address</h4>
          <span>{step > 2 ? '✓' : ''}</span>
        </div>
        {step === 2 && (
          <div className="accordion-body fade-in">
            <div className="d-flex align-items-center mb-4">
              <button className="btn btn-link text-dark p-0 me-3" onClick={() => setStep(1)} title="Go Back" style={{ fontSize: '24px', textDecoration: 'none', lineHeight: '1' }}>
                ←
              </button>
              <h4 className="m-0">Shipping Address</h4>
            </div>

            {savedAddress && (
              <div className="mb-4 p-3 border rounded shadow-sm" style={{ backgroundColor: useSavedAddress ? '#f0f8ff' : '#fff', cursor: 'pointer', transition: 'all 0.3s' }} onClick={() => setUseSavedAddress(!useSavedAddress)}>
                <div className="form-check">
                  <input className="form-check-input" type="checkbox" checked={useSavedAddress} onChange={() => setUseSavedAddress(!useSavedAddress)} />
                  <label className="form-check-label fw-bold" style={{ cursor: 'pointer' }}>
                    Use my saved address
                  </label>
                </div>
                {useSavedAddress && (
                  <div className="mt-2 text-muted px-4">
                    {savedAddress.addressLine1}<br/>
                    {savedAddress.addressLine2 && <>{savedAddress.addressLine2}<br/></>}
                    {savedAddress.area && <>{savedAddress.area}<br/></>}
                    {savedAddress.city}, {savedAddress.state} - {savedAddress.pincode}<br/>
                    {savedAddress.country}
                  </div>
                )}
              </div>
            )}

            {!useSavedAddress && (
              <div className="row mt-4">
                <div className="col-md-12 mb-3 form-group-checkout">
                  <label>Address Line 1*</label>
                  <input type="text" className="checkout-input" value={address.addressLine1} onChange={e => setAddress({...address, addressLine1: e.target.value})} placeholder="Flat, House no., Building, Company, Apartment" />
                </div>
                <div className="col-md-6 checkout-form-group">
                  <label>Address Line 2</label>
                  <input 
                    type="text" className="checkout-input" placeholder="Street, Sector, Village"
                    value={address.addressLine2} onChange={(e) => setAddress({...address, addressLine2: e.target.value})}
                  />
                </div>
                <div className="col-md-6 checkout-form-group">
                  <label>Address Line 3</label>
                  <input 
                    type="text" className="checkout-input" placeholder="Landmark (Optional)"
                    value={address.addressLine3} onChange={(e) => setAddress({...address, addressLine3: e.target.value})}
                  />
                </div>
                <div className="col-md-6 checkout-form-group">
                  <label>Area / Locality</label>
                  <input 
                    type="text" className="checkout-input" placeholder="Area"
                    value={address.area} onChange={(e) => setAddress({...address, area: e.target.value})}
                  />
                </div>
                <div className="col-md-6 checkout-form-group">
                  <label>City*</label>
                  <input 
                    type="text" className="checkout-input" placeholder="City"
                    value={address.city} onChange={(e) => setAddress({...address, city: e.target.value})}
                  />
                </div>
                <div className="col-md-4 checkout-form-group">
                  <label>State*</label>
                  <input 
                    type="text" className="checkout-input" placeholder="State"
                    value={address.state} onChange={(e) => setAddress({...address, state: e.target.value})}
                  />
                </div>
                <div className="col-md-4 checkout-form-group">
                  <label>Pincode / ZIP*</label>
                  <input 
                    type="text" className="checkout-input" placeholder="e.g. 110001"
                    value={address.pincode} onChange={(e) => setAddress({...address, pincode: e.target.value})}
                  />
                </div>
                <div className="col-md-4 checkout-form-group">
                  <label>Country*</label>
                  <select 
                    className="checkout-input"
                    value={address.country}
                    onChange={(e) => setAddress({...address, country: e.target.value})}
                  >
                    {COUNTRIES.map(c => (
                      <option key={c.code} value={c.code}>
                        {c.flag} {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
            
            <div className="d-flex justify-content-end align-items-center mt-4 border-top pt-3">
              <button className="btn-checkout-next px-5 py-2 shadow-sm" style={{ borderRadius: '8px' }} onClick={() => handleNextStep(3)}>
                Continue to Payment
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Step 3: Payment */}
      <div className="accordion-section">
        <div className="accordion-header" style={{ opacity: step === 3 ? 1 : 0.6 }}>
          <h4>3. Payment</h4>
        </div>
        {step === 3 && (
          <div className="accordion-body">
            <div className="d-flex align-items-center mb-4">
              <button className="btn btn-link text-dark p-0 me-3" onClick={() => setStep(2)} title="Go Back" style={{ fontSize: '24px', textDecoration: 'none', lineHeight: '1' }}>
                ←
              </button>
              <h4 className="m-0">Payment Method</h4>
            </div>
            <div className="payment-options">
              <div 
                className={`payment-option ${paymentMethod === 'card' ? 'selected' : ''}`}
                onClick={() => setPaymentMethod('card')}
              >
                💳 Credit / Debit Card
              </div>
              <div 
                className={`payment-option ${paymentMethod === 'upi' ? 'selected' : ''}`}
                onClick={() => setPaymentMethod('upi')}
              >
                📱 UPI
              </div>
            </div>

            <div className="mt-4">
              {paymentMethod === 'card' && (
                <div className="checkout-form-group">
                  <label>Card Number</label>
                  <input 
                    type="text" 
                    className="checkout-input" 
                    placeholder="1234 5678 9101 1121"
                    value={paymentDetails.cardNumber}
                    onChange={(e) => setPaymentDetails({...paymentDetails, cardNumber: e.target.value})}
                  />
                </div>
              )}

              {paymentMethod === 'upi' && (
                <div className="checkout-form-group">
                  <label>UPI ID</label>
                  <input 
                    type="text" 
                    className="checkout-input" 
                    placeholder="example@upi"
                    value={paymentDetails.upiId}
                    onChange={(e) => setPaymentDetails({...paymentDetails, upiId: e.target.value})}
                  />
                </div>
              )}
            </div>
            
            <div className="d-flex justify-content-end align-items-center mt-4 border-top pt-3">
              <button className="btn-checkout-next px-5 py-2 shadow-sm" onClick={handlePayment} disabled={isLoading} style={{ borderRadius: '8px' }}>
                {isLoading ? 'Processing...' : `Pay Now`}
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
