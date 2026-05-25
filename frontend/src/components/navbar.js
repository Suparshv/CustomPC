import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import navd from '../assets/navd.png';
import player1 from '../assets/player1.avif';
import player2 from '../assets/player2.avif';
import player3 from '../assets/player3.avif';
import player4 from '../assets/4.avif';
import mn from '../assets/monitornavbar.png';
import support from '../assets/support.avif';
import AuthCard from './auth';
import { useAuth } from './AuthContext';
import { useCart } from "../components/cartcontext";
import { useNotification } from "./notificationcontext";

export default function Navbar() {
  const { user, login, logout, showAuth, setShowAuth } = useAuth();
  const { cartItems } = useCart();
  const { showNotification } = useNotification();

  // Removed useEffect for justLoggedIn as we no longer reload on login

  const handleLoginSuccess = (userData) => {
    login(userData); // store username & email
    setShowAuth(false);
    showNotification(`${userData.username} logged in`, 'success');
  };
  const handleLogout = () => {
    if (user) {
      showNotification(`${user.username} logged out`, 'success');
    }
    logout();
  };

    // calculate total qty
    const totalItems = Object.values(cartItems).reduce(
      (sum, item) => sum + (item.qty || 0),
      0
    );
    return (
      <>
        <nav className="navbar navbar-expand-sm bg-dark navbar-dark sticky-top">
          <div className="container-fluid">
            <Link className="navbar-brand px-5 ms-5" to="/" id="brand">
              NZXT
            </Link>
            <button
              className="navbar-toggler"
              data-bs-toggle="collapse"
              data-bs-target="#collapsenavbar"
            >
              <span className="navbar-toggler-icon"></span>
            </button>
            <div
              className="collapse navbar-collapse ms-auto"
              id="collapsenavbar"
            >
              <ul className="navbar-nav">
                <li className="nav-item dropdown px-3">
                  <a
                    className="nav-link dropdown-toggle"
                    href="#"
                    data-bs-toggle="dropdown"
                  >
                    Deals
                  </a>
                  <div className="dropdown-menu mega-menu p-3">
                    <div className="row">
                      <div className="col-md-6">
                        <p className="dropdown-header">📢DEALS</p>
                        <a className="dropdown-item pb-1" href="/#offers">
                          Special Offers
                          <p className="text-secondary text-weight-lighter">
                            All exclusive deals available on <br />
                            NZXT.com
                          </p>
                        </a>
                        <br/>
                        <a className="dropdown-item pt-1" href="/prebuiltpc#bestsellers">
                          Best Sellers
                          <br />
                          <p className="text-secondary text-weight-lighter">
                            NZXT Best Selling Products
                          </p>
                        </a>  
                      </div>
                      <div className="col-md-6 text-center py-3">
                        <div className="mega-menu-banner">
                          <p
                            className="pt-3"
                            style={{ fontFamily: "GothamBl", fontSize: "20px" }}
                          >
                            First Month On Us!
                          </p>
                          <p
                            style={{ fontFamily: "GothamM", fontSize: "12px" }}
                          >
                            Buy from here <br/>
                            Get a XBOX game pass subscription!!
                          </p>
                          <img src={navd} className="img-fluid" />
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
                <li className="nav-item dropdown px-3">
                  <a
                    className="nav-link dropdown-toggle"
                    href="#"
                    data-bs-toggle="dropdown"
                  >
                    Gaming PCs
                  </a>
                  <div className="dropdown-menu mega-menu p-3 ">
                    <div className="row">
                      <div className="col-md-6">
                        <Link className="dropdown-item pb-1" to='/prebuiltpc'>
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-pc-display m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M8 1a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1zm1 13.5a.5.5 0 1 0 1 0 .5.5 0 0 0-1 0m2 0a.5.5 0 1 0 1 0 .5.5 0 0 0-1 0M9.5 1a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1zM9 3.5a.5.5 0 0 0 .5.5h5a.5.5 0 0 0 0-1h-5a.5.5 0 0 0-.5.5M1.5 2A1.5 1.5 0 0 0 0 3.5v7A1.5 1.5 0 0 0 1.5 12H6v2h-.5a.5.5 0 0 0 0 1H7v-4H1.5a.5.5 0 0 1-.5-.5v-7a.5.5 0 0 1 .5-.5H7V2z" />
                          </svg>
                          PREBUILT GAMING PCS
                        </Link>
                        <div className="d-flex align-items-center px-3">
                          <img
                            src={player1}
                            className="img-fluid rounded me-2"
                          />
                          <Link className="dropdown-item pb-1" to="/prebuiltpc">
                            Player: One Prime
                            <p className="text-secondary text-weight-lighter d-flex">
                              Play the latest games
                              <br />
                              competitively
                            </p>
                          </Link>
                        </div>
                        <div className="d-flex align-items-center px-3">
                          <img
                            src={player2}
                            className="img-fluid rounded me-2"
                          />
                          <Link className="dropdown-item pb-1" to="/prebuiltpc">
                            Player: Two Prime
                            <p className="text-secondary text-weight-lighter d-flex">
                              High performance Gaming,
                              <br />
                              streaming & creating.
                            </p>
                          </Link>
                        </div>
                        <div className="d-flex align-items-center px-3">
                          <img
                            src={player3}
                            className="img-fluid rounded me-2"
                          />
                          <Link className="dropdown-item pb-1" to="/prebuiltpc">
                            Player: Three Prime
                            <p className="text-secondary text-weight-lighter d-flex">
                              Use ultra settings with high
                              <br />
                              performance
                            </p>
                          </Link>
                        </div><br/>
                        <div className="d-flex align-items-center">
                          <a className="dropdown-item pb-1" href='/pc'>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              className="bi bi-pc"
                              viewBox="0 0 16 16"
                            >
                              <path d="M5 0a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V1a1 1 0 0 0-1-1zm.5 14a.5.5 0 1 1 0 1 .5.5 0 0 1 0-1m2 0a.5.5 0 1 1 0 1 .5.5 0 0 1 0-1M5 1.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5M5.5 3h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1 0-1" />
                            </svg>
                            CUSTOM PCS
                          </a>
                        </div>
                      </div>
                      <div
                        className="col-md-6 text-white p-3 m-3 rounded text-center bg-black"
                        style={{
                          width: "300px",
                          height: "300px",
                          textAlign: "center",
                        }}
                      >
                        <h5 className="text-white" style={{ fontSize: "20px" }}>
                          GeForce RTX 50 Series
                        </h5>
                        <p className="text-white" style={{ fontSize: "14px" }}>
                          Game Changer
                        </p>
                        <img src={player4} className="img-fluid rounded mb-2" />
                        <p className="text-white" style={{ fontSize: "16px" }}>
                          Next-Gen GPU's
                        </p>
                      </div>
                    </div>
                  </div>
                </li>
                <li className="nav-item dropdown px-3">
                  <a
                    className="nav-link dropdown-toggle"
                    href="#"
                    data-bs-toggle="dropdown"
                  >
                    Components
                  </a>
                  <div className="dropdown-menu mega-menu p-3 ">
                    <div className="row">
                      <div className="col-md-4 ">
                        <a
                          className="dropdown-item pb-1"
                          href="/pc#psu"
                          style={{ paddingLeft: "0px" }}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-power m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M7.5 1v7h1V1z" />
                            <path d="M3 8.812a5 5 0 0 1 2.578-4.375l-.485-.874A6 6 0 1 0 11 3.616l-.501.865A5 5 0 1 1 3 8.812" />
                          </svg>
                          POWER SUPPLIES
                        </a><br/>
                        <a
                          className="dropdown-item pb-1"
                          href="/pc#processor"
                          style={{ paddingLeft: "0px" }}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-motherboard-fill m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M5 7h3V4H5z" />
                            <path d="M1 2a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-2H.5a.5.5 0 0 1-.5-.5v-1A.5.5 0 0 1 .5 9H1V8H.5a.5.5 0 0 1-.5-.5v-1A.5.5 0 0 1 .5 6H1V5H.5a.5.5 0 0 1-.5-.5v-2A.5.5 0 0 1 .5 2zm11 .5a.5.5 0 0 0-1 0v7a.5.5 0 0 0 1 0zm2 0a.5.5 0 0 0-1 0v7a.5.5 0 0 0 1 0zM3.5 10a.5.5 0 0 0 0 1h6a.5.5 0 0 0 0-1zm0 2a.5.5 0 0 0 0 1h6a.5.5 0 0 0 0-1zM4 4h-.5a.5.5 0 0 0 0 1H4v1h-.5a.5.5 0 0 0 0 1H4a1 1 0 0 0 1 1v.5a.5.5 0 0 0 1 0V8h1v.5a.5.5 0 0 0 1 0V8a1 1 0 0 0 1-1h.5a.5.5 0 0 0 0-1H9V5h.5a.5.5 0 0 0 0-1H9a1 1 0 0 0-1-1v-.5a.5.5 0 0 0-1 0V3H6v-.5a.5.5 0 0 0-1 0V3a1 1 0 0 0-1 1m7 7.5v1a.5.5 0 0 0 .5.5h2a.5.5 0 0 0 .5-.5v-1a.5.5 0 0 0-.5-.5h-2a.5.5 0 0 0-.5.5" />
                          </svg>
                          MOTHERBOARDS
                        </a>
                        <a className="dropdown-item" href="#">
                          <p className="text-secondary text-weight-lighter">
                            Intel® & AMD®
                          </p>
                        </a>
                        <a
                          className="dropdown-item pb-1"
                          href="/pc#processor"
                          style={{ paddingLeft: "0px" }}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-cpu-fill m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M6.5 6a.5.5 0 0 0-.5.5v3a.5.5 0 0 0 .5.5h3a.5.5 0 0 0 .5-.5v-3a.5.5 0 0 0-.5-.5z" />
                            <path d="M5.5.5a.5.5 0 0 0-1 0V2A2.5 2.5 0 0 0 2 4.5H.5a.5.5 0 0 0 0 1H2v1H.5a.5.5 0 0 0 0 1H2v1H.5a.5.5 0 0 0 0 1H2v1H.5a.5.5 0 0 0 0 1H2A2.5 2.5 0 0 0 4.5 14v1.5a.5.5 0 0 0 1 0V14h1v1.5a.5.5 0 0 0 1 0V14h1v1.5a.5.5 0 0 0 1 0V14h1v1.5a.5.5 0 0 0 1 0V14a2.5 2.5 0 0 0 2.5-2.5h1.5a.5.5 0 0 0 0-1H14v-1h1.5a.5.5 0 0 0 0-1H14v-1h1.5a.5.5 0 0 0 0-1H14v-1h1.5a.5.5 0 0 0 0-1H14A2.5 2.5 0 0 0 11.5 2V.5a.5.5 0 0 0-1 0V2h-1V.5a.5.5 0 0 0-1 0V2h-1V.5a.5.5 0 0 0-1 0V2h-1zm1 4.5h3A1.5 1.5 0 0 1 11 6.5v3A1.5 1.5 0 0 1 9.5 11h-3A1.5 1.5 0 0 1 5 9.5v-3A1.5 1.5 0 0 1 6.5 5" />
                          </svg>
                          CPU
                        </a>
                        <a className="dropdown-item" href="#">
                          <p className="text-secondary text-weight-lighter">
                            Intel® & AMD®
                          </p>
                        </a>
                        <a
                          className="dropdown-item pb-1"
                          href="/pc#gpu"
                          style={{ paddingLeft: "0px" }}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-gpu-card m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M4 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0m7.5-1.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3" />
                            <path d="M0 1.5A.5.5 0 0 1 .5 1h1a.5.5 0 0 1 .5.5V4h13.5a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-.5.5H2v2.5a.5.5 0 0 1-1 0V2H.5a.5.5 0 0 1-.5-.5m5.5 4a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5M9 8a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0" />
                            <path d="M3 12.5h3.5v1a.5.5 0 0 1-.5.5H3.5a.5.5 0 0 1-.5-.5zm4 1v-1h4v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5" />
                          </svg>
                          GPU
                        </a>
                        <a className="dropdown-item" href="#">
                          <p className="text-secondary text-weight-lighter">
                            NVIDIA® & AMD®
                          </p>
                        </a>
                      </div>
                    </div>
                  </div>
                </li>
                <li className="nav-item dropdown px-3">
                  <a
                    className="nav-link dropdown-toggle"
                    href="#"
                    data-bs-toggle="dropdown"
                  >
                    Contact
                  </a>
                  <div className="dropdown-menu mega-menu p-3 ">
                    <div className="row">
                      <div className="col-md-6">
                        <p
                          className="dropdown-header"
                          style={{ fontSize: "12px", paddingLeft: "0px" }}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            fill="currentColor"
                            className="bi bi-person-lines-fill m-1"
                            viewBox="0 0 16 16"
                          >
                            <path d="M6 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m-5 6s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zM11 3.5a.5.5 0 0 1 .5-.5h4a.5.5 0 0 1 0 1h-4a.5.5 0 0 1-.5-.5m.5 2.5a.5.5 0 0 0 0 1h4a.5.5 0 0 0 0-1zm2 3a.5.5 0 0 0 0 1h2a.5.5 0 0 0 0-1zm0 3a.5.5 0 0 0 0 1h2a.5.5 0 0 0 0-1z" />
                          </svg>
                          CONTACT
                        </p>
                        <a className="dropdown-item pb-1" href="/support">
                          Support
                          <p className="text-secondary text-weight-lighter">
                            Customer Care
                          </p>
                        </a>
                        <Link className="dropdown-item pb-1" to="/about">
                          About US
                          <p className="text-secondary text-weight-lighter">
                            Know more about us
                          </p>
                        </Link>
                      </div>
                      <div className="col-md-6 p-3">
                        <h5
                          className="text-white text-bold"
                          style={{ fontSize: "20px" }}
                        >
                          Support
                        </h5>
                        <img
                          src={support}
                          className="img-fluid rounded bg-white"
                        />
                      </div>
                    </div>
                  </div>
                </li>
              </ul>
            </div>
          </div>
          <div className="d-flex justify-content-center container-fluid me-5 ">
            {user ? (
              <div className="dropdown">
                <button
                  className="btn"
                  id="userDropdown"
                  data-bs-toggle="dropdown"
                  aria-expanded="false"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    fill="currentColor"
                    className="bi bi-person text-white icon"
                    viewBox="0 0 16 16"
                  >
                    <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10s-3.516.68-4.168 1.332c-.678.678-.83 1.418-.832 1.664z" />
                  </svg>
                </button>
                <ul
                  className="dropdown-menu mega-menu1"
                  aria-labelledby="userDropdown"
                >
                  <li>
                    <Link className="dropdown-item" to="/profile">
                      {user.username}<br/>
                      Profile
                    </Link>
                  </li>
                  <li>
                    <button className="dropdown-item" onClick={handleLogout}>
                      Logout
                    </button>
                  </li>
                  </ul>
                
              </div>
            ) : (
              <button className="btn" onClick={() => setShowAuth(true)}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  fill="currentColor"
                  className="bi bi-person text-white icon"
                  viewBox="0 0 16 16"
                >
                  <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10s-3.516.68-4.168 1.332c-.678.678-.83 1.418-.832 1.664z" />
                </svg>
              </button>
            )}
            <AuthCard
              show={showAuth}
              onClose={() => setShowAuth(false)}
              onLoginSuccess={handleLoginSuccess}
            />
            <Link to="/cart" className="btn cart-icon position-relative">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                fill="currentColor"
                className="bi bi-cart text-white icon"
                viewBox="0 0 16 16"
              >
                <path d="M0 1.5A.5.5 0 0 1 .5 1H2a.5.5 0 0 1 .485.379L2.89 3H14.5a.5.5 0 0 1 .491.592l-1.5 8A.5.5 0 0 1 13 12H4a.5.5 0 0 1-.491-.408L2.01 3.607 1.61 2H.5a.5.5 0 0 1-.5-.5M3.102 4l1.313 7h8.17l1.313-7zM5 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4m7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m-7 1a1 1 0 1 1 0 2 1 1 0 0 1 0-2m7 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2" />
              </svg>
              {totalItems > 0 && (
                <span className="cart-dot"></span>
              )}
            </Link>
          </div>
        </nav>
      </>
    );
}