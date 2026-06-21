const { retrieveRelevantComponents } = require("../services/ragService");
const { GoogleGenAI } = require("@google/genai");

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// every agent is a function that receives the current "state"
async function architectAgent(state) {
  console.log("Agent 1 (Architect): Drafting a build...");

  // 1. Get the latest message the user sent from the state
  const lastMessage = state.messages[state.messages.length - 1];
  const userMessage = lastMessage.content;

  // 2. Use RAG to fetch enough parts to make a complete build (25 parts)
  const relevantParts = await retrieveRelevantComponents(userMessage, 25);
  const partsText = relevantParts.join("\n---\n"); // Combine them into text

  // 3. Set up the Architect's instructions
  const systemInstruction = `
    You are the Architect Agent for a custom PC store.
    Your job is to draft a PC build based ONLY on the provided relevant parts.
    
    AVAILABLE RELEVANT INVENTORY (Retrieved from Database):
    ${partsText}

    CRITICAL RULES:
    1. Do not hallucinate parts. Only use the IDs provided above.
    2. If the user asks for a FULL PC build, you MUST include exactly 1 component from EACH of the 9 categories: processor, motherboard, gpu, ram, ps, ss, psu, cabinet, and cooling. ('ps' is Primary Storage, 'ss' is Secondary Storage). Do not skip any! If they only want parts, only output those.
    3. ENSURE HARDWARE COMPATIBILITY: Do NOT bottleneck a high-end GPU with a weak CPU. Ensure the Motherboard socket matches the CPU socket. Ensure Motherboard RAM type matches the RAM. 
    4. Do NOT use any emojis or markdown formatting.
    5. Keep your "reply" extremely brief and concise. Maximum 3 sentences.
    `;

  // 4. Send to Gemini
  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: `User request: ${userMessage}`,
    config: {
      systemInstruction,
      tools: [{
        functionDeclarations: [{
          name: "submit_draft_build",
          description: "Submits the drafted PC build based on the user's request and available inventory.",
          parameters: {
            type: "OBJECT",
            properties: {
              reply: { type: "STRING", description: "Brief 1-3 sentence reply to the user" },
              build: {
                type: "ARRAY",
                items: {
                  type: "OBJECT",
                  properties: {
                    category: { type: "STRING" },
                    id: { type: "STRING" }
                  },
                  required: ["category", "id"]
                }
              },
              budget: { type: "NUMBER", description: "The user's budget if mentioned" }
            },
            required: ["reply", "build"]
          }
        }]
      }],
      toolConfig: {
        functionCallingConfig: {
          mode: "ANY",
          allowedFunctionNames: ["submit_draft_build"],
        },
      },
    },
  });

  const call = response.functionCalls?.[0];
  if (!call || call.name !== "submit_draft_build") {
    console.error("Agent response:", response.text);
    throw new Error("Agent failed to call submit_draft_build tool.");
  }
  
  const parsedResponse = call.args;

  // 5. Update the LangGraph State
  // We return an object containing the fields we want to update in the state
  return {
    draftBuild: parsedResponse.build,
    architectReply: parsedResponse.reply,
    userBudget: parsedResponse.budget,
    // Add an internal message to the chat history so the next agent can see what happened
    messages: [{ role: "assistant", content: parsedResponse.reply }],
  };
}

module.exports = { architectAgent };
