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
import React from "react";
import allgame from '../assets/allgaming.png'
import { useCart } from '../components/cartcontext';
import { useNotification } from "../components/notificationcontext";


const pc1={id:1,name:'Player PC | 5080 Edition',price:255000}
const pc2={id:2,name:'Player PC | 5090 Edition',price:390000}
const pc3={id:3,name:'Player: One',price:71000}
const pc4={id:4,name:'Player: Two',price:125100}
const pc5={id:5,name:'Player: Three',price:180000}
const pc6={id:6,name:'Player: One Prime',price:106000}
const pc7={id:7,name:'Player: Two Prime',price:175000}
const pc8={id:8,name:'Player: Three Prime',price:290000}
const pc9={id:9,name:'Player PC | 4070 Edition',price:148000}

export default function Prebuiltpc(){
    const { addOrUpdateItem } = useCart();
    const { showNotification } = useNotification();
    
    const handleShop = (pc) => {
        const category = `prebuilt-${pc.id}`;
        addOrUpdateItem(category, pc, 1); // qty = 1 by default
        showNotification("Added to cart!", "success");
    };
    return (
        <>
            <div class="gpusection">
                <img className="img-fluid" src={allgame} style={{ width: '100%', objectFit: 'cover' }} alt="Gaming PCs" />
                    <div class="text">
                        <h1>
                            Gaming PCs for every 
                            <br />
                            kind of player.
                        </h1>
                        <p style={{fontSize:'16px'}}>Choose your path to play: Player PC, Flex subscription.<br/> Every NZXT PC is prebuilt to perform.</p>
                    </div>
            </div>
            <div className="container mt-5">
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
            
                      <div className="row g-5" id="bestsellers">
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
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc1)}>Shop</button>
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
                              Shop
                            </button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
                          <div className="product-card position-relative p-3">
                            <img src={img3_1} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc3.name}</h5>
                            <p className="px12">H5 Flow RTX 4060 Gaming PC</p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              Intel Core™ i5-13400F
                              <br />
                              NVIDIA® GeForce RTX™ 4060
                            </p>
                            <hr />
                            <p className=" px12b">₹{pc3.price.toLocaleString('en-IN')}</p>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc3)}>Shop</button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
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
                            <button className="btn shop-btn text-white"onClick={() => handleShop(pc4)} >Shop</button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
                          <div className="product-card position-relative p-3">
                            <span className="badge-custom bg-success">10% Off</span>
                            <img src={img5_1} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc5.name}</h5>
                            <p className="px12">H7 Flow RTX 4070 Ti SUPER Gaming PC</p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              Intel Core™ i7-13700K
                              <br />
                              NVIDIA® GeForce RTX™ 4070 Ti SUPER
                            </p>
                            <hr />
                            <div style={{ paddingBottom: "10px" }}>
                              <span className="text-decoration-line-through text-muted px12">
                                ₹2,00,000
                              </span>
                              <span className="px12b">₹{pc5.price.toLocaleString('en-IN')}</span>
                            </div>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc5)}>Shop</button>
                          </div>
                        </div>
            
                        <div className=" col-md-4">
                          <div className="product-card position-relative p-3">
                            <img src={img6_1} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc6.name}</h5>
                            <p className="px12">H5 Flow RGB RTX 4060 Ti Gaming PC</p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              Intel Core™ i5-13400F
                              <br />
                              NVIDIA® GeForce RTX™ 4060 Ti 8GB
                            </p>
                            <hr />
                            <p className="px12b">₹{pc6.price.toLocaleString('en-IN')}</p>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc6)}>Shop</button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
                          <div className="product-card position-relative p-3">
                            <img src={ptp} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc7.name}</h5>
                            <p className="px12">H6 Flow RGB RTX 4070Ti SUPER Gaming PC</p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              AMD Ryzen™ 7 7700X
                              <br />
                              NVIDIA® GeForce RTX™ 4070 Ti SUPER
                            </p>
                            <hr />
                            <div style={{ paddingBottom: "10px" }}>
                              <span className="px12b">₹{pc7.price.toLocaleString('en-IN')}</span>
                            </div>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc7)}>Shop</button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
                          <div className="product-card position-relative p-3">
                            <img src={img8_1} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc8.name}</h5>
                            <p className="px12">H9 Elite RGB RTX 4080 SUPER Gaming PC</p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              Intel Core™ i9-14900KF
                              <br />
                              NVIDIA® GeForce RTX™ 4080 SUPER
                            </p>
                            <hr />
                            <p className="px12b">₹{pc8.price.toLocaleString('en-IN')}</p>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc8)}>Shop</button>
                          </div>
                        </div>
            
                        <div className="col-md-4">
                          <div className="product-card position-relative p-3">
                            <img src={img9_1} className="img-fluid shop" />
                            <h5 className="mt-3 px18">{pc9.name}</h5>
                            <p className="px12">
                              Limited Edition H7 Elite RTX 4070 Gaming PC
                            </p>
                            <hr />
                            <p className="pt-1 px12b mb-0"> Key Specs</p>
                            <p className="text-muted small px12">
                              Windows 11 Home
                              <br />
                              Intel® Core™ i7 14700KF
                              <br />
                              NVIDIA® GeForce RTX™4070
                            </p>
                            <hr />
                            <p className="px12b">₹{pc9.price.toLocaleString('en-IN')}</p>
                            <button className="btn shop-btn text-white" onClick={() => handleShop(pc9)}>Shop</button>
                          </div>
                        </div>
                      </div>
                    </div>
        </>
    )
}