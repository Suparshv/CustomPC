const express = require('express');
const router = express.Router();
const aiController = require('../controllers/aiController');
const { agent } = require('./agentRoutes');

// Define AI endpoints
router.post('/builder', aiController.chatBuilder);
router.post('/chat-builder', aiController.chatBuilder);
router.post('/support', aiController.chatSupport);
// Day 12: the Python code checker, fail-safe (could_not_verify on any error).
router.post('/compatibility', agent.checkCompatibility);
router.get('/history/:sessionId', aiController.getChatHistory);

module.exports = router;
