import React from "react";
import img1 from '../assets/1.png';
import img2 from '../assets/2.png';
import img3 from '../assets/3.png';
import img4 from '../assets/4.png';
import img5 from '../assets/5.png';
import img6 from '../assets/6.png';
import rtx50_2 from '../assets/rtx50(2).png';
import logo from '../assets/logo.png';
import img1_1 from '../assets/1-1.png';
import img2_1 from '../assets/2-1.avif';
import img3_1 from '../assets/3-1.png';
import img4_1 from '../assets/4-1.png';
import img5_1 from '../assets/5-1.png';
import img6_1 from '../assets/6-1.png';
import ptp from '../assets/ptp.png';
import img8_1 from '../assets/8-1.png';
import img9_1 from '../assets/9-1.png';
import custompc1 from '../assets/custompc1.avif';
import { Link } from "react-router-dom";
import { useCart } from "../components/cartcontext";
import { useNotification } from "../components/notificationcontext";


const pc1={id:1,name:'Player PC | 5080 Edition',price:255000}
const pc2={id:2,name:'Player PC | 5090 Edition',price:390000}
const pc4={id:4,name:'Player: Two',price:125100}
export default function Home() {
    const { addOrUpdateItem } = useCart();
    const { showNotification } = useNotification();
    const handleShop = (pc) => {
        const category = `prebuilt-${pc.id}`;
        addOrUpdateItem(category, pc, 1); // qty = 1 by default
        showNotification("Added to cart!", "success");
    };
    
    return (
      <>
        <section className="product-categories py-1">
          <div className=" d-flex justify-content-around align-items-center text-center">
            <div className="col-md-2 col-6 category-item">
              <a href="/prebuiltpc">
                <img src={img1} className="category-icon" />
              </a>
              <p>Best Sellers</p>
            </div>
            <div className="col-md-2 col-6 category-item">
              <Link to="/pc">
                <img src={img2} className="category-icon" />
              </Link>
              <p>Custom Pc</p>
            </div>
            <div className="col-md-2 col-6 category-item">
              <a href="#nzxt">
                <img src={img3} className="category-icon" />
              </a>
              <p>50 Series Gaming PCs</p>
            </div>
            <div className="col-md-2 col-6 category-item">
              <Link to="/prebuiltpc">
                <img src={img5} className="category-icon" />
              </Link>
              <p>Prebuilt PCs</p>
            </div>
          </div>
        </section>
        <div class="gpusection">
          <img class="img-fluid" src={rtx50_2}/>
          <div class="text">
            <img src={logo} class="img-fluid" />
            <h1>
              GeForce RTX 50 Series
              <br />
              Gaming PCs are Here
            </h1>
            <p>Game-changing capabilities for gamers and creators.</p>
            <Link to='/prebuiltpc'>
            <button type="button" class="btn btn-outline-light btn-lg shop">
              Shop Now
            </button></Link>
          </div>
        </div>

        <div className="container mt-5" id ='nzxt'>
          <h2
            className="text-center"
            style={{ fontFamily: "GothamB", fontSize: "36px" }}
          >
            NZXT Gaming PCs
          </h2>
          <p
            className="text-center pb-3"
            style={{
              fontFamily: "GothamM",
              fontSize: "16px",
              color: "#737279",
              fontWeight: "lighter",
            }}
          >
            We use the latest generation performance components and <br />
            configurations to get you gaming, fast.
          </p>

          <div className="row g-5">
            <div className="col-md-4">
              <div className="product-card position-relative p-3">
                <img src={img1_1} className="img-fluid shop" />
                <h5 className="mt-3 px18">{pc1.name}</h5>
                <p className="px12">H6 Flow RTX 5080 Gaming PC</p>
                <hr />
                <p className="pt-1 px12b mb-0"> Key Specs</p>
                <p className="text-muted px12">
                  Windows 11 Home
                  <br />
                  AMD Ryzen™ 7 9800X3D <br />
                  NVIDIA® GeForce RTX™ 5080
                </p>
                <hr />
                <p className="px12b">₹{pc1.price.toLocaleString('en-IN')}</p>
                <button className="btn shop-btn text-white" onClick={() => handleShop(pc1)}>Cart</button>
              </div>
            </div>

            <div className="col-md-4">
              <div className="product-card position-relative p-3">
                <span className="badge-custom bg-primary">Coming Soon</span>
                <img src={img2_1} className="img-fluid shop" />
                <h5 className="mt-3 px18">{pc2.name}</h5>
                <p className="px12">H9 Elite RTX 5090 Gaming PC</p>
                <hr />
                <p className="pt-1 px12b mb-0"> Key Specs</p>
                <p className="text-muted px12">
                  Windows 11 Home
                  <br />
                  AMD Ryzen™ 9 9800X3D
                  <br />
                  NVIDIA® GeForce RTX™ 5090
                </p>
                <hr />
                <p className="px12b">₹{pc2.price.toLocaleString('en-IN')}</p>
                <button
                  className="btn shop-btn btn-secondary text-white "
                  disabled
                >
                  Cart
                </button>
              </div>
            </div>
            <div className="col-md-4" id="offers">
              <div className="product-card position-relative p-3">
                <span className="badge-custom bg-success">10% Off</span>
                <img src={img4_1} className="img-fluid shop" />
                <h5 className="mt-3 px18">{pc4.name}</h5>
                <p className="px12">H6 Flow RTX 4070 Gaming PC</p>
                <hr />
                <p className="pt-1 px12b mb-0"> Key Specs</p>
                <p className="text-muted small px12">
                  Windows 11 Home
                  <br />
                  AMD Ryzen™ 5 7600X
                  <br />
                  NVIDIA® GeForce RTX™ 4070
                </p>
                <hr />
                <div style={{ paddingBottom: "10px" }}>
                  <span className="text-decoration-line-through text-muted px12">
                    ₹1,39,700
                  </span>
                  <span className="px12b">₹{pc4.price.toLocaleString('en-IN')}</span>
                </div>
                <button className="btn shop-btn text-white "onClick={() => handleShop(pc4)}>Cart</button>
              </div>
            </div>
          </div>
        </div>
        <div className="container mt-5">
          <h2
            className="text-center"
            style={{ fontFamily: "GothamB", fontSize: "36px" }}
          >
            Custom Gaming PCs
          </h2>
          <p
            className="text-center pb-3"
            style={{
              fontFamily: "GothamM",
              fontSize: "16px",
              color: "#737279",
              fontWeight: "lighter",
            }}
          >
            Build your Dream Rig
          </p>
        </div>
        <div className="position-relative text-white">
          <img
            src={custompc1}
            className="img-fluid"
            style={{ width: "100%" }}
          />
          <div className="position-absolute top-50 end-0 text-center pe-5 me-5 translate-middle">
            <h1
              className="text-black"
              style={{
                fontFamily: "GothamB",
                fontSize: "48px",
                color: "black",
              }}
            >
              Build A Custom PC
            </h1>
            <p
              style={{
                fontFamily: "GothamM",
                fontSize: "18px",
                color: "black",
                textAlign: "left",
              }}
            >
              Custom PCs designed by you, built by us.
            </p>
            <Link to="/pc" className="btn shop-btn text-white">
              Customize a PC
            </Link>
          </div>
        </div>
      </>
    );
}