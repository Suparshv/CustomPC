// Day 12 - routes to the Python agent service (mounted at /api).
const express = require("express");
const { createAgentController } = require("../controllers/agentController");

const router = express.Router();
const agent = createAgentController();

router.post("/agent/chat", agent.chat);
router.post("/agent/approve", agent.approve);
// The only way an AI build reaches the cart: the server checks the approval first.
router.post("/cart/add-build", agent.addBuildToCart);

module.exports = { router, agent };
