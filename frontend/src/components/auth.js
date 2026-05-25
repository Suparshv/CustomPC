import React, { useState, useEffect } from "react";
import logo from "../assets/logo.avif";

function AuthCard({ show, onClose, onLoginSuccess }) {
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });
  const [message, setMessage] = useState("");

  useEffect(() => {
    setForm({ username: "", email: "", password: "" });
    setMessage("");
    setShowPassword(false);
  }, [mode, show]);

  if (!show) return null;

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint =
        mode === "signup"
          ? "http://localhost:5000/api/signup"
          : "http://localhost:5000/api/login";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
      setMessage(data.message || "Something went wrong. Please try again.");
      setLoading(false);
      return;} 

      if (mode === "login" && data.user) {
        onLoginSuccess(data.user); 
        onClose();
        return;
      }

      setMessage(data.message || "Success!");

    } catch (err) {
      console.error("Auth error:", err);
      setMessage("Error connecting to server");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop-custom">
      <div className="modal-custom p-4 bg-white rounded shadow-sm">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <img
            src={logo}
            width={200}
            height={52}
            className="d-flex align-items-center"
          />
          <button className="btn-close" onClick={onClose}></button>
        </div>
        <h5 style={{ fontFamily: "GothamM", fontSize: "16px" }}>
          {mode === "login" ? "Login in" : "Sign up"}
        </h5>
        <form onSubmit={handleSubmit}>
          {mode === "signup" && (
            <div className="mb-3">
              <input
                type="text"
                className="form-control"
                placeholder="Username"
                name="username"
                value={form.username}
                onChange={handleChange}
                required
              />
            </div>
          )}
          <div className="mb-3">
            <input
              type="email"
              className="form-control"
              placeholder="Email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>
          <div className="mb-3 position-relative">
            <input
              type={showPassword ? "text" : "password"}
              className="form-control"
              placeholder="Password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
            />
            <span
              className="position-absolute top-50 end-0 translate-middle-y px-2 text-primary"
              style={{ cursor: "pointer", fontSize: "12px" }}
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? "Hide" : "Show"}
            </span>
          </div>
          <button
            type="submit"
            className="btn w-100"
            style={{ backgroundColor: "#5a32d1", color: "white" }}
            disabled={loading}
          >
            {loading
              ? "Processing..."
              : mode === "login"
              ? "Continue"
              : "Sign Up"}
          </button>
        </form>
        {message && <div className="alert alert-info mt-3">{message}</div>}
        <div className="text-center mt-3">
          <small>
            {mode === "login"
              ? "Don't have an account? "
              : "Already have an account? "}
            <span
              className="text-primary"
              style={{ cursor: "pointer" }}
              onClick={() => setMode(mode === "login" ? "signup" : "login")}
            >
              {mode === "login" ? "Sign Up" : "Login"}
            </span>
          </small>
        </div>
      </div>
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
          width: 350px;
        }
      `}</style>
    </div>
  );
}

export default AuthCard;
