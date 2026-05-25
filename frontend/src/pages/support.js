import support from '../assets/support.webp'
import "bootstrap/dist/css/bootstrap.min.css";
import "../styles/about.css"; 
import { Link } from 'react-router-dom';
import React, { useState } from "react";

export default function Support() {
  const [active, setActive] = useState("hq");
  return (
        <div className="about-page" >
          <section className="container py-5">
            <div className="row align-items-center">
              <div className="col-md-6 text-center text-md-start">
                <h2 style={{fontFamily:"GothamB",fontSize:"48px"}}>
                  Support
                </h2>
                <p className="mt-3" style={{fontFamily:"GothamM",fontSize:"18px",color:"#1c1c1c"}}>
                  Find additional customer support articles and FAQ.
                </p>
              </div>
              <div className="col-md-6 text-center">
                <img src={support} alt="Gaming Setup" className="img-fluid rounded" />
              </div>
            </div>
          </section>
        
        <section className="py-4">
        <div className="container">
          <ul className="nav nav-tabs justify-content-start gap-3 border-0">
            <li className="nav-item">
              <button
                className={`nav-link support-tab ${active === "hq" ? "active" : ""}`}
                onClick={() => setActive("hq")}
                type="button"
              >
                Headquarters
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link support-tab ${active === "hours" ? "active" : ""}`}
                onClick={() => setActive("hours")}
                type="button"
              >
                Customer Support Hours
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link support-tab ${active === "contact" ? "active" : ""}`}
                onClick={() => setActive("contact")}
                type="button"
              >
                Contact
              </button>
            </li>
          </ul>

          <div className="tab-shell mt-3">
            {active === "hq" && (
              <div className="tab-pane-custom fade-in">
                <h6 className="fw-semibold mb-2">Address:</h6>
                <p className="mb-4">
                  NZXT, Inc. <br />
                  605 E. Huntington Drive, Suite 213 <br />
                  Monrovia, CA 91016
                </p>
                <p className="mb-2"><strong>Phone:</strong> +1-626-385-8272</p>
                <p className="mb-0"><strong>Support:</strong> +1-800-228-9395</p>
              </div>
            )}

            {active === "hours" && (
              <div className="tab-pane-custom fade-in">
                <h6 className="fw-semibold mb-2">Customer Support Hours</h6>
                <ul className="list-unstyled mb-0">
                  <li>Mon – Fri: 9:00 AM – 6:00 PM (PST)</li>
                  <li>Sat – Sun: Closed</li>
                </ul>
              </div>
            )}

            {active === "contact" && (
              <div className="tab-pane-custom fade-in">
                <h5 className="fw-semibold mb-3">Contact Us</h5>
                <h6 className="mb-3">Email:nzxt@help.com</h6>
              </div>
            )}
          </div>
        </div>
      </section>
      <style>{`
        .support-tab{
          border:none !important;
          background:transparent !important;
          font-weight:600;
          color:#6c757d;
          padding:.75rem 1rem;
          position:relative;
        }
        .support-tab.active{
          color:#000;
        }
        .support-tab.active::after{
          content:"";
          position:absolute;
          left:0; right:0; bottom:-8px;
          height:3px; border-radius:2px;
          background:#000;
        }

        .tab-shell{
          background:#fff;
          border:1px solid #e9ecef;
          border-radius:1rem;
          padding:1.25rem 1.25rem 1.5rem;
          box-shadow:0 8px 20px rgba(0,0,0,.06);
        }
        .fade-in{
          animation:fade-in .25s ease-out;
        }
        @keyframes fade-in{
          from{opacity:0; transform:translateY(4px)}
          to{opacity:1; transform:translateY(0)}
        }
      `}
      </style>
    </div> 
  );
}
