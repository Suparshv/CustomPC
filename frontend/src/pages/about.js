import React from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "../styles/about.css"; 
import { Link } from 'react-router-dom';
import deskImg from "../assets/about.webp";
import simplyBest from "../assets/a1.webp";
import endToEnd from "../assets/a2.webp";
import minimalFlare from "../assets/a3.webp";
import builtToLast from "../assets/a4.webp";
import covered from "../assets/a5.webp";

export default function About() {
  return (
    <div className="about-page">
      <section className="container py-5">
        <div className="row align-items-center">
          <div className="col-md-6 text-center text-md-start">
            <h2 style={{fontFamily:"GothamB",fontSize:"48px"}}>
              For the <span className="purple-heart">💜</span> of the <br/>game.
            </h2>
            <p className="mt-3" style={{fontFamily:"GothamM",fontSize:"18px",color:"#1c1c1c"}}>
              Let’s unlock your potential. With the best tools,<br/> anyone can jump
              in and play. No intimidation, no <br/>sweat.
            </p>
          </div>
          <div className="col-md-6 text-center">
            <img src={deskImg} alt="Gaming Setup" className="img-fluid rounded" />
          </div>
        </div>
      </section>

      <section className="container py-5">
        <div className="row text-center g-4" >
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}> 
              <h5 className="mt-3 text-md-start" style={{fontFamily:"GothamB",fontSize:"72px"}}>How We Make it Easy</h5>
          </div>
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}>
            <img src={simplyBest} alt="Simply the Best" className="img-fluid" />
            <h5 className="mt-3 px28">Simply the Best</h5>
            <h6 className="p18" style={{color:"#1c1c1c"}}>
              We offer a streamlined selection of high-performance parts, letting you
              dive into gaming faster and without fuss.
            </h6>
          </div>
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}>
            <img src={endToEnd} alt="End-to-End Solutions" className="img-fluid" />
            <h5 className="mt-3 px28">End-to-End Solutions</h5>
            <h6 className="p18" style={{color:"#1c1c1c"}}>
              We make hardware, software, and services<br/> that guide you along your
              journey, each<br/>  step of the way.
            </h6>
          </div>
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}>
            <img src={minimalFlare} alt="Minimal Flare" className="img-fluid" />
            <h5 className="mt-3 px28">Minimal Flare</h5>
            <h6 className="p18" style={{color:"#1c1c1c"}}>
              We design timeless products with<br/>  powerful specs to feel seamlessly<br/>
              anywhere, for anyone.
            </h6>
          </div>
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}>
            <img src={builtToLast} alt="Built to Last" className="img-fluid" />
            <h5 className="mt-3 px28">Built to Last</h5>
            <h6 className="p18" style={{color:"#1c1c1c"}}>
              Our products are engineered for<br/>  endurance, built with high-quality<br/> 
              components, and rigorously tested.
            </h6>
          </div>
          <div className="col-md-4 m-5 p-4 w-25" style={{backgroundColor:"#F5F5F5"}}>
            <img src={covered} alt="We Got You Covered" className="img-fluid" />
            <h5 className="mt-3 px28">We Got You Covered</h5>
            <h6 className="p18" style={{color:"#1c1c1c"}}>
              From our top-quality support team to our <br/>  comprehensive warranty, we aim for <br/> 
              ensure peace of mind.
            </h6>
          </div>
        </div>
      </section>

      <section className="community-section text-center text-white py-5 mx-5" style={{ background: 'linear-gradient(90deg,#b6edf7, #76e8f7, #00b8faff)'}}>
        <h4 style={{fontFamily:'GothamB',fontSize:'48px'}}>
          We’ve been serving the PC gaming <br/> community since 2004. It’s not just our
          job,<br/> it’s our passion.
        </h4>
        <h5 className="mt-2" style={{fontFamily:'GothamBl',color:'black',fontSize:'40px'}}>NZXT</h5>
      </section>

      <section className="container py-5 text-center">
        <h3 style={{fontFamily:'GothamB',fontSize:'40px'}}>We Love Our Community</h3>
      </section>
    </div>
  );
}
