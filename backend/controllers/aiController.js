const { GoogleGenAI } = require("@google/genai");
const fs = require('fs');
const path = require('path');

// Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// Load components inventory to pass to LLM
const componentsPath = path.join(__dirname, '../data/components.json');
const inventoryData = JSON.parse(fs.readFileSync(componentsPath, 'utf8'));

exports.chatBuilder = async (req, res) => {
  const { message, chatHistory } = req.body;

  if (!process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEY === 'YOUR_GEMINI_API_KEY_HERE') {
    return res.status(500).json({ error: "Gemini API key is not configured on the server." });
  }

  try {
    const systemInstruction = `
You are an expert PC builder AI assistant for an NZXT-inspired custom PC store.
You must help the user select PC parts and answer their questions.

CRITICAL RULES:
1. ONLY recommend parts from the exact JSON inventory provided below. Do not suggest parts that are not in the inventory.
2. Ensure compatibility (e.g., DDR5 RAM with DDR5 Motherboards, enough PSU wattage).
3. Always respond with valid JSON containing two fields: "reply" (your conversational text answer to the user) and "build" (an array of objects for the parts you recommend adding/replacing in their cart).
4. If you don't need to add parts (e.g. just answering a question), return an empty array for "build".
5. The "build" array should look like this: [{"category": "processor", "id": "p1"}, {"category": "gpu", "id": "g3"}]. Valid categories are: processor, motherboard, cooling, gpu, ps, ss, ram, psu, cabinet.

INVENTORY:
${JSON.stringify(inventoryData, null, 2)}
`;

    const prompt = `
User message: ${message}
Current Chat History context: ${JSON.stringify(chatHistory || [])}
Remember to output ONLY valid JSON format. Example:
{
  "reply": "Here is a great build for your budget!",
  "build": [{"category": "gpu", "id": "g1"}]
}
`;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        systemInstruction,
        responseMimeType: "application/json"
      }
    });

    const resultText = response.text;
    const jsonResult = JSON.parse(resultText);

    res.json(jsonResult);
  } catch (error) {
    console.error("Gemini API Error:", error);
    res.status(500).json({ error: "Failed to process AI response." });
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

exports.checkCompatibility = async (req, res) => {
  const { currentBuild, newItem } = req.body;

  if (!process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEY === 'YOUR_GEMINI_API_KEY_HERE') {
    return res.status(500).json({ error: "Gemini API key is not configured on the server." });
  }

  try {
    const systemInstruction = `
You are an expert PC builder AI assistant.
Your job is to evaluate if a newly selected PC component is compatible with the user's currently selected components.
Look out for common incompatibilities like:
- Incompatible CPU sockets and Motherboards (e.g. AMD Ryzen on Intel LGA1700).
- Incompatible RAM types (e.g. DDR5 RAM on a DDR4 Motherboard).
- Grossly insufficient Power Supplies (e.g. a 4090 GPU with a 500W PSU).

Return ONLY valid JSON format with two fields:
{
  "isCompatible": true or false,
  "reason": "String explaining the incompatibility if any, or a brief affirmation if compatible."
}
`;

    const prompt = `
Currently selected components in cart:
${JSON.stringify(currentBuild || [], null, 2)}

Newly selected component to add:
${JSON.stringify(newItem, null, 2)}

Evaluate compatibility and return JSON.
`;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        systemInstruction,
        responseMimeType: "application/json"
      }
    });

    const resultText = response.text;
    const jsonResult = JSON.parse(resultText);

    res.json(jsonResult);
  } catch (error) {
    console.error("Gemini Compatibility Check Error:", error);
    res.status(500).json({ error: "Failed to check compatibility." });
  }
};
