require('dotenv').config();
const express = require("express");
const cors = require("cors");
const mongoose = require("mongoose");
const v = require("validator");
const aiRoutes = require('./routes/aiRoutes');

const app = express();
app.use(cors({ origin: "http://localhost:3000", credentials: true }));
app.use(express.json());

app.get('/', (req, res) => {
  res.send('Backend is running!');
});

// Connect to MongoDB
mongoose
  .connect("mongodb://127.0.0.1:27017/PC", {
    useNewUrlParser: true,
    useUnifiedTopology: true,
  })
  .then(() => console.log("MongoDB Connected"))
  .catch((err) => console.error(err));

mongoose.pluralize(null);

// User Schema
const userSchema = new mongoose.Schema({
  username: { type: String, required: true, minlength: 3 },
  email: {
    type: String,
    required: true,
    unique: true,
    validate: [v.isEmail, "Invalid email"],
  },
  password: { type: String, required: true, minlength: 3 },
  gender: { type: String, enum: ['male', 'female', 'other'], default: 'male' },
  age: { type: Number },
  mobileNo: { type: String },
  countryCode: { type: String, default: '+91' },
  address: {
    addressLine1: String,
    addressLine2: String,
    addressLine3: String,
    area: String,
    city: String,
    state: String,
    pincode: String,
    country: String
  }
});

const User = mongoose.model("User", userSchema);

// PC Build Schema (just for saving configs)
const pcBuildSchema = new mongoose.Schema({
  useremail: { type: String, required: true },
  username: { type: String, required: true },
  components: { type: Object, required: true },
  total: { type: Number, required: true },
  date: { type: Date, default: Date.now },
});
const PCBuild = mongoose.model("pcbuild", pcBuildSchema);

// Order Schema (for checkout)
const orderSchema = new mongoose.Schema({
  email: { type: String, required: true },
  username: { type: String, required: true },
  components: { type: Object, required: true },
  total: { type: Number, required: true },
  shippingAddress: { type: Object },
  paymentMethod: { type: String },
  mobileNo: { type: String },
  status: { type: String, default: 'Processing' }, // 'Processing', 'Shipped', 'Delivered'
  date: { type: Date, default: Date.now },
});
const Order = mongoose.model("Order", orderSchema);

// AI Routes
app.use('/api/chat', aiRoutes);

// Signup route
app.post("/api/signup", async (req, res) => {
  const { username, email, password } = req.body;
  try {
    const exists = await User.findOne({ email });
    if (exists) {
      return res.json({ message: "Email already exists" });
    }
    const user = new User({ username, email, password });
    await user.validate();
    await user.save();
    res.json({ message: "User registered successfully", user: { username, email } });
  } catch (err) {
    if (err.name === "ValidationError") {
      let errors = [];
      for (let field in err.errors) {
        if (field === "username") {
          errors.push("Username must be at least 3 characters.");
        } else if (field === "email") {
          errors.push("Invalid email address.");
        } else if (field === "password") {
          errors.push("Password must be at least 3 characters.");
        }
      }
      return res.status(400).json({ message: errors.join(" ") });
    }

    if (err.code === 11000) {
      return res.status(400).json({ message: "Email already exists" });
    }

    res.status(500).json({ message: "Server error" });
  }
});

// Login route
app.post("/api/login", async (req, res) => {
  const { email, password } = req.body;
  try {
    const user = await User.findOne({ email, password });
    if (!user) {
      return res.json({ message: "Invalid email or password" });
    }
    
    res.json({
      message: "Login successful",
      user: { 
        username: user.username, 
        email: user.email,
        gender: user.gender,
        age: user.age,
        mobileNo: user.mobileNo,
        countryCode: user.countryCode,
        address: user.address
      },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Server error" });
  }
});

// Get User Profile
app.get("/api/user/profile", async (req, res) => {
  const { email } = req.query;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ message: "User not found" });
    
    const orders = await Order.find({ email }).sort({ date: -1 });
    res.json({ user, orders });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Server error" });
  }
});

// Update User Profile
app.put("/api/user/profile", async (req, res) => {
  const { email, username, gender, age, countryCode, mobileNo, address } = req.body;
  try {
    const user = await User.findOneAndUpdate(
      { email },
      { username, gender, age, countryCode, mobileNo, address },
      { new: true }
    );
    res.json({ message: "Profile updated", user });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: "Server error updating profile" });
  }
});

// Save PC build (Config only)
app.post("/api/build", async (req, res) => {
    const { userEmail, components, total, username } = req.body;
    if (!userEmail || !username) {
        return res.status(401).json({ message: "Unauthorized: No user details provided" });
    }
    try {
      const build = new PCBuild({
        useremail: userEmail,
        username: username,
        components: components,
        total: total
      });
      await build.save();
      res.json({ message: "PC Build saved successfully!" });
    } catch (err) {
      console.error(err);
      res.status(500).json({ message: "Server error while saving build" });
    }
});

// Save Order
app.post("/api/order", async (req, res) => {
    const { email, components, total, username, shippingAddress, paymentMethod, mobileNo } = req.body;
    if (!email || !username) {
        return res.status(401).json({ message: "Unauthorized: No user details provided" });
    }
    try {
      const order = new Order({
        email: email,
        username: username,
        components: components,
        total: total,
        shippingAddress,
        paymentMethod,
        mobileNo
      });
      await order.save();

      // Also save to PCBuild collection as requested
      const build = new PCBuild({
        useremail: email,
        username: username,
        components: components,
        total: total
      });
      await build.save();

      // Simulate order processing logic in the background
      setTimeout(async () => {
        try {
          await Order.findByIdAndUpdate(order._id, { status: 'Shipped' });
        } catch(e) {}
      }, 60000); // 1 minute to Shipped
      
      setTimeout(async () => {
        try {
          await Order.findByIdAndUpdate(order._id, { status: 'Delivered' });
        } catch(e) {}
      }, 120000); // 2 minutes to Delivered

      res.json({ message: "Order placed successfully!" });
    } catch (err) {
      console.error(err);
      res.status(500).json({ message: "Server error while saving order" });
    }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
