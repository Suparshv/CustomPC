const express = require('express');
const router = express.Router();
const aiController = require('../controllers/aiController');

// Define AI endpoints
router.post('/builder', aiController.chatBuilder);
router.post('/support', aiController.chatSupport);
router.post('/compatibility', aiController.checkCompatibility);

module.exports = router;
