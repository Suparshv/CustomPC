import logo from './assets/logo.png';
import './App.css';
import Navbar from "./components/navbar";
import Home from "./pages/home";
import PcBuilder from "./pages/PcBuilder";
import { Routes, Route } from "react-router-dom";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./components/AuthContext";
import { CartProvider } from "./components/cartcontext";
import About from './pages/about';
import Prebuiltpc from './pages/prebuilt';
import { NotificationProvider } from "./components/notificationcontext";
import Support from './pages/support';
import Checkout from './pages/checkout';
import CartPage from './pages/cart';
import Profile from './pages/profile';
import AIAssistant from './components/AIAssistant';
import ScrollToTop from './components/ScrollToTop';


function App() {
  return (
    <>
      <NotificationProvider>
        <AuthProvider>
          <CartProvider>
            <BrowserRouter>
              <ScrollToTop />
              <Navbar />
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/pc" element={<PcBuilder />} />
                <Route path="/about" element={<About />} />
                <Route path="/prebuiltpc" element={<Prebuiltpc/>} />
                <Route path="/support" element={<Support/>} />
                <Route path="/checkout" element={<Checkout/>} />
                <Route path="/cart" element={<CartPage/>} />
                <Route path="/profile" element={<Profile/>} />
              </Routes>
              <AIAssistant />
            </BrowserRouter>
          </CartProvider>
        </AuthProvider>
      </NotificationProvider>
    </>
  );
}

export default App;
