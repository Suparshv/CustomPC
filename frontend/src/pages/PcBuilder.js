import React, { useState, useEffect } from "react";
import { componentsData } from "../data/components";
import axios from "axios";
import custompc1 from "../assets/custompc1.avif";
import win11 from "../assets/win11.avif";
import nvidia from "../assets/nvidia.avif";
import amd from "../assets/amd.avif";
import intel from "../assets/intel.avif";
import { useCart } from "../components/cartcontext";
import { createPortal } from "react-dom";
import { useAuth } from "../components/AuthContext";
import { useNotification } from "../components/notificationcontext";
import { useNavigate } from "react-router-dom";


function CategoryModal({ show, onClose, category, items, onConfirm, checkingItemId }) {
  const [qtys, setQtys] = useState({});

  useEffect(() => {
    if (show) {
      const o = {};
      items.forEach((it) => (o[it.id] = 1));
      setQtys(o);
    }
  }, [show, items]);

  // lock background scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = show ? "hidden" : "auto";
    return () => (document.body.style.overflow = "auto");
  }, [show]);

  if (!show) return null;

  return createPortal(
    <div className="modal-backdrop-custom">
      <div className="modal-custom">
        <div className="modal-header d-flex justify-content-between">
          <h5>Select {category}</h5>
          <button className="btn-close" onClick={onClose} />
        </div>

        {/* scrollable vertical body */}
        <div className="modal-body scrollable-body">
          <div className="row">
            {items.map((it) => (
              <div className="col-md-6" key={it.id}>
                <div className="product-card position-relative p-3 mb-3">
                  <img
                    src={it.image}
                    className="img-fluid shop"
                    alt={it.name}
                  />
                  <p className="px18">{it.name}</p>
                  <p className="px12">QTY</p>
                  <input
                    type="number"
                    min="1"
                    value={qtys[it.id] || 1}
                    onChange={(e) =>
                      setQtys({
                        ...qtys,
                        [it.id]: Math.max(1, Number(e.target.value)),
                      })
                    }
                  />
                  <p className="px12 pt-1">₹{it.price.toLocaleString()}</p>
                  <button
                    className="btn shop-btn text-white mt-2"
                    onClick={() => {
                      if (checkingItemId !== null) return;
                      const selectedQty = qtys[it.id] || 1;
                      onConfirm(category, it, selectedQty);
                    }}
                    style={{
                      opacity: checkingItemId !== null && checkingItemId !== it.id ? 0.5 : 1,
                      cursor: checkingItemId !== null ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {checkingItemId === it.id ? "Checking..." : "Select"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* styles */}
      <style>{`
        .modal-backdrop-custom {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 2000;
        }
        .modal-custom {
          width: 90%;
          max-width: 1000px;
          background: #fff;
          padding: 20px;
          border-radius: 8px;
          max-height: 90vh;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .scrollable-body {
          overflow-y: auto;
          overflow-x: hidden;
          flex: 1;
          padding-right: 8px;
        }
      `}</style>
    </div>,
    document.body
  );
}

export default function PcBuilder() {
  const { user, setShowAuth } = useAuth();
  const categories = Object.keys(componentsData);
  const { addOrUpdateItem, selected, total } = useCart();
  const navigate = useNavigate();
  const [modal, setModal] = useState({ show: false, category: "" });
  const [checkingItemId, setCheckingItemId] = useState(null);
  const [compatibilityWarning, setCompatibilityWarning] = useState({
    show: false,
    reason: "",
    category: "",
    item: null,
    qty: 1
  });

  useEffect(() => {
    if (window.location.hash) {
      setTimeout(() => {
        const id = window.location.hash.substring(1);
        const el = document.getElementById(id);
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }, []);

  const openModal = (category) => setModal({ show: true, category });
  const closeModal = () => setModal({ show: false, category: "" });
  const { showNotification } = useNotification();
  
  const onConfirm = async (category, item, qty) => {
    const currentBuild = Object.values(selected);
    
    // Skip API check if this is the very first item being added to cart
    if (currentBuild.length === 0) {
      addOrUpdateItem(category, item, qty);
      showNotification("Added to cart!", "success");
      closeModal();
      return;
    }

    setCheckingItemId(item.id);
    try {
      const res = await axios.post("http://localhost:5000/api/chat/compatibility", {
        currentBuild,
        newItem: item
      });

      if (res.data.isCompatible === false) {
        setCompatibilityWarning({
          show: true,
          reason: res.data.reason,
          category,
          item,
          qty
        });
        setCheckingItemId(null);
        return;
      }
    } catch (err) {
      console.error("Compatibility check failed", err);
      // Fallback: proceed to add if API fails so user isn't blocked completely
    }

    setCheckingItemId(null);
    addOrUpdateItem(category, item, qty);
    showNotification("Added to cart!", "success");
    closeModal();
  };

  const forceAddIncompatibleItem = () => {
    const { category, item, qty } = compatibilityWarning;
    addOrUpdateItem(category, item, qty);
    showNotification("Added to cart despite warning!", "warning");
    setCompatibilityWarning({ show: false, reason: "", category: "", item: null, qty: 1 });
    closeModal();
  };

  const closeWarningModal = () => {
    setCompatibilityWarning({ show: false, reason: "", category: "", item: null, qty: 1 });
  };

  const handleCheckout = () => {
    if (!user) {
      showNotification("Please login to proceed to checkout", "warning");
      setShowAuth(true);
      return;
    }
    navigate('/checkout');
  };

  const handleSaveOnly = async () => {
    if (!user) {
      showNotification("Please login to save your build", "danger");
      return;
    }
    if (Object.keys(selected).length === 0) {
      showNotification("Your build is empty!", "danger");
      return;
    }
    
    try {
      const payload = {
        username: user.username,
        userEmail: user.email,
        total,
        components: Object.values(selected).map((item) => ({
          name: item.name,
          price: item.price,
          qty: item.qty,
        })),
      };
      await axios.post("http://localhost:5000/api/build", payload);
      showNotification("Build saved successfully!", "success");
    } catch (err) {
      showNotification("Failed to save build", "danger");
    }
  };

  return (
    <>
      <section className="product-categories py-1">
        <div className="container">
          <div className="row justify-content-center text-center">
            <div className="col-md-3 col-6">
              <img src={win11} alt="Windows 11" />
            </div>
            <div className="col-md-3 col-6">
              <img src={nvidia} alt="Nvidia" />
            </div>
            <div className="col-md-3 col-6">
              <img src={amd} alt="AMD" />
            </div>
            <div className="col-md-3 col-6 ">
              <img src={intel} alt="Intel" />
            </div>
          </div>
        </div>
      </section>

      <div className="container">
        <div className="position-relative text-white">
          <img
            src={custompc1}
            className="img-fluid"
            style={{ minWidth: "100%" }}
            alt="Custom PC"
          />
          <div className="position-absolute top-50 end-0 text-center ml-5 translate-middle">
            <h1
              className="text-black"
              style={{
                fontFamily: "GothamB",
                fontSize: "40px",
                color: "black",
              }}
            >
              Build A Custom PC
            </h1>
            <p
              style={{
                fontFamily: "GothamM",
                fontSize: "16px",
                color: "black",
                textAlign: "left",
              }}
            >
              Custom PCs designed by you, built by us.
            </p>
          </div>
        </div>

        {categories.map((cat) => (
          <div className="row pt-4" key={cat} id={cat}>
            <div className="col-md">
              <div className="product-card position-relative p-3">
                <h5 className="px18">
                  {cat === "ps"
                    ? "Primary Storage(OS) SSD"
                    : cat === "ss"
                    ? "Secondary Storage"
                    : cat === "gpu" ? "GPU"
                    : cat === "psu" ? "PSU"
                    : cat === "ram" ? "RAM"
                    : cat.charAt(0).toUpperCase() + cat.slice(1)}
                </h5>

                <p className="px12" id={`select${cat}`}>
                  {selected[cat]
                    ? `${selected[cat].name} x${selected[cat].qty} — ₹${(
                        selected[cat].price * selected[cat].qty
                      ).toLocaleString()}`
                    : "No selection"}
                </p>

                <div className="d-flex justify-content-end">
                  <button
                    className="btn plus-btn text-white"
                    onClick={() => openModal(cat)}
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}

        <div className="row pt-5">
          <div className="col-md">
            <div className="product-card position-relative p-3">
              <h5 className="px18">
                Total: (Including GST){" "}
                <span className="d-flex justify-content-end">
                  ₹{total.toLocaleString()}
                </span>
              </h5>
              <div className="pb-4">
                <button
                  className="btn shop-btn text-white mt-2 w-100"
                  onClick={handleCheckout}
                >
                  Pay Now
                </button>
                <button
                  className="btn shop-btn1  mt-2 w-100"
                  onClick={handleSaveOnly}
                >
                  Save Build
                </button>
              </div>
            </div>
          </div>
        </div>

        {modal.show && (
          <CategoryModal
            show={modal.show}
            onClose={closeModal}
            category={modal.category}
            items={componentsData[modal.category]}
            onConfirm={onConfirm}
            checkingItemId={checkingItemId}
          />
        )}

        {compatibilityWarning.show && (
          <div className="modal-backdrop-custom" style={{ zIndex: 3000 }}>
            <div className="modal-custom" style={{ maxWidth: '600px', borderTop: '5px solid #ff4d4f' }}>
              <div className="modal-header d-flex justify-content-between text-danger">
                <h5>⚠️ Compatibility Warning</h5>
                <button className="btn-close" onClick={closeWarningModal} />
              </div>
              <div className="modal-body pt-4 pb-4">
                <p style={{ fontSize: '16px', fontFamily: 'GothamM' }}>{compatibilityWarning.reason}</p>
                <p className="text-muted mt-3 mb-0" style={{ fontSize: '14px' }}>
                  Do you want to ignore this warning and add the component anyway, or go back to select another model?
                </p>
              </div>
              <div className="modal-footer d-flex justify-content-end border-top pt-3">
                <button className="btn btn-outline-secondary me-3 px-4 py-2" onClick={closeWarningModal}>
                  Select another model
                </button>
                <button className="btn btn-danger px-4 py-2 text-white" onClick={forceAddIncompatibleItem}>
                  Ignore & Add Anyway
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Extra padding to prevent overlap with floating AI Assistant button */}
        <div style={{ height: '80px' }}></div>
      </div>
    </>
  );
}
