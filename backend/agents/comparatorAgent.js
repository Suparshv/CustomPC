const { GoogleGenAI } = require("@google/genai");
const { retrieveRelevantComponents } = require("../services/ragService");

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
const MODEL_NAME = process.env.GEMINI_MODEL || "gemini-3.5-flash-lite";

async function comparatorAgent(state) {
  console.log("Agent 4 (Comparator): Generating side-by-side comparison...");

  const lastMessage = state.messages[state.messages.length - 1].content;

  // Use RAG to grab specs for the parts the user is asking to compare
  const relevantParts = await retrieveRelevantComponents(lastMessage, 4);
  const partsText = relevantParts.join("\n---\n");

      const systemInstruction = `
    You are the Comparator Agent. 
    Using the specs provided below, compare the items.
    
    CRITICAL RULES:
    1. Be extremely brief and concise. 
    2. Do NOT use any emojis.
    3. Do NOT use markdown formatting (no **, *, or #).
    
    SPECS:
    ${partsText}
    `;
  const response = await ai.models.generateContent({
    model: MODEL_NAME,
    contents: `User request: ${lastMessage}`,
    config: {
      systemInstruction,
      tools: [{
        functionDeclarations: [{
          name: "submit_comparison",
          description: "Submits the structured comparison data.",
          parameters: {
            type: "OBJECT",
            properties: {
              comparisonData: {
                type: "OBJECT",
                properties: {
                  headers: { type: "ARRAY", items: { type: "STRING" } },
                  rows: { type: "ARRAY", items: { type: "ARRAY", items: { type: "STRING" } } },
                  verdict: { type: "STRING" }
                },
                required: ["headers", "rows", "verdict"]
              },
              reply: { type: "STRING" }
            },
            required: ["comparisonData", "reply"]
          }
        }]
      }],
      toolConfig: {
        functionCallingConfig: {
          mode: "ANY",
          allowedFunctionNames: ["submit_comparison"],
        },
      },
    },
  });

  const call = response.functionCalls?.[0];
  if (!call || call.name !== "submit_comparison") {
    throw new Error("Agent failed to call submit_comparison tool.");
  }
  
  const comparison = call.args;
  console.log(`  [Tokens] Comparator: ${JSON.stringify(response.usageMetadata)}`);

  return {
    comparison: comparison,
    messages: [{ role: "assistant", content: comparison.reply }],
    tokenLog: [{ agent: "comparator", tokens: response.usageMetadata }],
  };
}

module.exports = { comparatorAgent };
