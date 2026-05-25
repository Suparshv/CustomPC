import React, { useState, useEffect } from 'react';
import { useAuth } from '../components/AuthContext';
import { useNotification } from '../components/notificationcontext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import '../styles/profile.css';

export default function Profile() {
  const { user, login } = useAuth();
  const { showNotification } = useNotification();
  const navigate = useNavigate();

  const [orders, setOrders] = useState([]);
  const [isEditing, setIsEditing] = useState(false);
  const [profileData, setProfileData] = useState({
    username: '',
    gender: 'male',
    age: '',
    countryCode: '+91',
    mobileNo: '',
    address: {
      addressLine1: '',
      addressLine2: '',
      addressLine3: '',
      area: '',
      city: '',
      state: '',
      pincode: '',
      country: 'IN'
    }
  });

  useEffect(() => {
    if (!user) {
      navigate('/');
      return;
    }

    const fetchProfile = async () => {
      try {
        const res = await axios.get(`http://localhost:5000/api/user/profile?email=${user.email}`);
        const data = res.data.user;
        setProfileData({
          username: data.username || '',
          gender: data.gender || 'male',
          age: data.age || '',
          countryCode: data.countryCode || '+91',
          mobileNo: data.mobileNo || '',
          address: data.address || {
            addressLine1: '', addressLine2: '', addressLine3: '', area: '', city: '', state: '', pincode: '', country: 'IN'
          }
        });
        setOrders(res.data.orders || []);
      } catch (err) {
        console.error("Error fetching profile", err);
      }
    };
    fetchProfile();
  }, [user, navigate]);

  if (!user) return null;

  const handleSave = async () => {
    try {
      const res = await axios.put('http://localhost:5000/api/user/profile', {
        email: user.email,
        ...profileData
      });
      showNotification('Profile updated successfully', 'success');
      setIsEditing(false);
      // Update local auth context if username changed
      login({ ...user, ...res.data.user });
    } catch (err) {
      showNotification('Failed to update profile', 'danger');
    }
  };

  const getAvatar = () => {
    const name = profileData.username || user.username || 'User';
    let initials = name.substring(0, 1);
    if (name.length >= 3) {
      initials += name.substring(2, 3);
    } else if (name.length === 2) {
      initials += name.substring(1, 2);
    }
    return `https://ui-avatars.com/api/?name=${initials.toUpperCase()}&background=random&length=2&size=150&font-size=0.4`;
  };

  return (
    <div className="profile-container">
      <div className="profile-sidebar">
        <img src={getAvatar()} alt="Profile" className="profile-avatar" />
        <h3>{profileData.username || user.username}</h3>
        <p>{user.email}</p>
        <p className="mt-2 text-muted" style={{ fontSize: '12px' }}>
          {orders.length} Orders Placed
        </p>
      </div>

      <div className="profile-content">
        <div className="profile-card">
          <h4>
            Personal Information
            <button className="btn-edit-profile" onClick={() => isEditing ? handleSave() : setIsEditing(true)}>
              {isEditing ? 'Save Changes' : 'Edit Profile'}
            </button>
          </h4>
          
          <div className="row">
            <div className="col-md-6 form-group-profile">
              <label>Username</label>
              <input 
                type="text" 
                className="profile-input" 
                value={profileData.username} 
                disabled={!isEditing}
                onChange={(e) => setProfileData({...profileData, username: e.target.value})}
              />
            </div>
            <div className="col-md-6 form-group-profile">
              <label>Email</label>
              <input type="text" className="profile-input" value={user.email} disabled />
            </div>
            <div className="col-md-4 form-group-profile">
              <label>Gender</label>
              <select 
                className="profile-input" 
                value={profileData.gender}
                disabled={!isEditing}
                onChange={(e) => setProfileData({...profileData, gender: e.target.value})}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="col-md-2 form-group-profile">
              <label>Age</label>
              <input 
                type="number" 
                className="profile-input" 
                value={profileData.age} 
                disabled={!isEditing}
                onChange={(e) => setProfileData({...profileData, age: e.target.value})}
              />
            </div>
            <div className="col-md-6 form-group-profile">
              <label>Mobile Number</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input 
                  type="text" 
                  className="profile-input" 
                  style={{ width: '80px' }} 
                  value={profileData.countryCode} 
                  disabled={!isEditing}
                  onChange={(e) => setProfileData({...profileData, countryCode: e.target.value})}
                />
                <input 
                  type="text" 
                  className="profile-input" 
                  value={profileData.mobileNo} 
                  disabled={!isEditing}
                  onChange={(e) => setProfileData({...profileData, mobileNo: e.target.value})}
                />
              </div>
            </div>
            <div className="col-12 mt-4 mb-2">
              <h5 style={{ fontFamily: "GothamB", fontSize: "16px", borderBottom: "1px solid #eee", paddingBottom: "10px" }}>Shipping Address</h5>
            </div>
            <div className="col-md-12 form-group-profile">
              <label>Address Line 1</label>
              <input type="text" className="profile-input" value={profileData.address.addressLine1} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, addressLine1: e.target.value}})} />
            </div>
            <div className="col-md-6 form-group-profile">
              <label>Address Line 2 (Optional)</label>
              <input type="text" className="profile-input" value={profileData.address.addressLine2} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, addressLine2: e.target.value}})} />
            </div>
            <div className="col-md-6 form-group-profile">
              <label>Area / Landmark</label>
              <input type="text" className="profile-input" value={profileData.address.area} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, area: e.target.value}})} />
            </div>
            <div className="col-md-4 form-group-profile">
              <label>City</label>
              <input type="text" className="profile-input" value={profileData.address.city} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, city: e.target.value}})} />
            </div>
            <div className="col-md-4 form-group-profile">
              <label>State</label>
              <input type="text" className="profile-input" value={profileData.address.state} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, state: e.target.value}})} />
            </div>
            <div className="col-md-4 form-group-profile">
              <label>Pincode</label>
              <input type="text" className="profile-input" value={profileData.address.pincode} disabled={!isEditing} onChange={(e) => setProfileData({...profileData, address: {...profileData.address, pincode: e.target.value}})} />
            </div>
          </div>
        </div>

        <div className="profile-card">
          <h4>Your Orders</h4>
          {orders.length === 0 ? (
            <p className="text-muted">You haven't placed any orders yet.</p>
          ) : (
            orders.map(order => (
              <div key={order._id} className="order-item">
                <div className="order-header">
                  <div>
                    <div className="order-id">Order #{order._id.substring(order._id.length - 8).toUpperCase()}</div>
                    <div className="order-date">{new Date(order.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                  </div>
                  <div>
                    <span className={`order-status status-${order.status ? order.status.toLowerCase() : 'processing'}`}>
                      {order.status || 'Processing'}
                    </span>
                  </div>
                </div>
                <div className="order-body">
                  <div className="order-components">
                    {Object.values(order.components).map((comp, idx) => (
                      <div key={idx} className="order-component-item">
                        • {comp.name} (x{comp.qty})
                      </div>
                    ))}
                  </div>
                  <div className="order-total">
                    ₹{order.total.toLocaleString('en-IN')}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
