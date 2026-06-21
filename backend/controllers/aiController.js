const { GoogleGenAI } = require("@google/genai");
const fs = require('fs');
const path = require('path');

// Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// Load components inventory to pass to LLM
const componentsPath = path.join(__dirname, '../data/components.json');
const inventoryData = JSON.parse(fs.readFileSync(componentsPath, 'utf8'));

const { graphApp } = require("../agents/graph");
const mongoose = require("mongoose");

exports.chatBuilder = async (req, res) => {
  const { message, sessionId } = req.body;

  if (
    !process.env.GEMINI_API_KEY ||
    process.env.GEMINI_API_KEY === "YOUR_GEMINI_API_KEY_HERE"
  ) {
    return res.status(500).json({ error: "Gemini API key is not configured." });
  }
  try {
    console.log("-----------------------------------------");
    console.log("🤖 Starting Multi-Agent Workflow...");

    const Conversation = mongoose.model("Conversation");
    const AgentLog = mongoose.model("AgentLog");

    // --- INPUT GUARDRAIL ---
    // Simple heuristic to block prompt injections
    const lowerMessage = message.toLowerCase();
    if (lowerMessage.includes("ignore previous") || lowerMessage.includes("system instruction")) {
      await AgentLog.create({ sessionId, userPrompt: message, route: "BLOCKED", success: false });
      return res.json({ reply: "I cannot fulfill that request. Please ask a PC hardware-related question." });
    }

    // --- MEMORY: Fetch History ---
    let conversation = await Conversation.findOne({ sessionId });
    if (!conversation) {
      conversation = new Conversation({ sessionId, messages: [] });
    }

    // Append the new user message to the memory
    conversation.messages.push({ role: "user", content: message });
    
    // 1. Prepare the initial state for LangGraph using the FULL conversation history
    const initialState = {
      messages: conversation.messages,
    };

    // 2. Invoke the LangGraph!
    const finalState = await graphApp.invoke(initialState);
    const finalReply = finalState.architectReply || finalState.comparison?.reply || "I cannot assist with that request.";

    // --- MEMORY: Save AI Response ---
    conversation.messages.push({ 
      role: "assistant", 
      content: finalReply,
      build: finalState.draftBuild || null,
      critique: finalState.critique || null,
      reviews: finalState.reviews || null,
      comparisonData: finalState.comparison?.comparisonData || null
    });
    conversation.lastActive = Date.now();
    await conversation.save();

    // --- GUARDRAIL: Log Transaction ---
    await AgentLog.create({ 
      sessionId, 
      userPrompt: message, 
      route: finalState.nextStep || "UNKNOWN", 
      success: true 
    });

    // 3. Send the final results back to the React frontend
    res.json({
      reply: finalReply,
      build: finalState.draftBuild || null,
      critique: finalState.critique || null,
      reviews: finalState.reviews || null,
      comparisonData: finalState.comparison?.comparisonData || null,
    });
  } catch (error) {
    console.error("Multi-Agent Error:", error);
    // Log the failure
    if (req.body.sessionId) {
      const AgentLog = mongoose.model("AgentLog");
      await AgentLog.create({ sessionId: req.body.sessionId, userPrompt: message, route: "ERROR", success: false });
    }
    res.status(500).json({ error: "Failed to process AI response." });
  }
};

// GET endpoint to load chat history on page load
exports.getChatHistory = async (req, res) => {
  const { sessionId } = req.params;
  try {
    const Conversation = mongoose.model("Conversation");
    const convo = await Conversation.findOne({ sessionId });
    res.json({ messages: convo ? convo.messages : [] });
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch history" });
  }
};

exports.chatSupport = async (req, res) => {
  const { message, chatHistory } = req.body;

  if (!process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEY === 'YOUR_GEMINI_API_KEY_HERE') {
    return res.status(500).json({ error: "Gemini API key is not configured on the server." });
  }

  try {
    const systemInstruction = `
You are a helpful customer support agent for a PC hardware store. 
Help users troubleshoot hardware issues (e.g., PC not booting, no display, RAM not recognized).
Be friendly, concise, and provide step-by-step troubleshooting.
`;

    const prompt = `
User message: ${message}
Current Chat History: ${JSON.stringify(chatHistory || [])}
`;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        systemInstruction,
      }
    });

    res.json({ reply: response.text });
  } catch (error) {
    console.error("Gemini Support Error:", error);
    res.status(500).json({ error: "Failed to process AI response." });
  }
};

const { criticAgent } = require("../agents/criticAgent");
exports.checkCompatibility = async (req, res) => {
  const { currentBuild, newItem } = req.body;
  if (
    !process.env.GEMINI_API_KEY ||
    process.env.GEMINI_API_KEY === "YOUR_GEMINI_API_KEY_HERE"
  ) {
    return res
      .status(500)
      .json({ error: "Gemini API key is not configured on the server." });
  }
  try {
    console.log("-----------------------------------------");
    console.log(
      "Manual UI triggered Critic Agent for compatibility check...",
    );

    // 1. Combine what's currently in their cart with the new item they just clicked
    // We format it into the { id: "..." } structure that our Critic Agent expects
    const proposedBuild = [...currentBuild, newItem].map((item) => ({
      id: item.id,
    }));
    // 2. We simulate the LangGraph "State" and pass it directly to the Critic Agent!
    const simulatedState = { draftBuild: proposedBuild };
    const resultState = await criticAgent(simulatedState);
    // 3. The Critic returns { critique: { approved, issues, reply } }
    // We map it back to the { isCompatible, reason } format that your React frontend already expects
    res.json({
      isCompatible: resultState.critique.approved,
      reason:
        resultState.critique.issues.length > 0
          ? resultState.critique.issues.join(" | ")
          : resultState.critique.reply,
    });
  } catch (error) {
    console.error("Manual Compatibility Check Error:", error);
    // Fallback so the user isn't blocked if the AI fails
    res.json({
      isCompatible: true,
      reason: "Fallback: AI check failed, proceed with caution.",
    });
  }
};
