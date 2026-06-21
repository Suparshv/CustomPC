const { GoogleGenAI } = require("@google/genai");
const fs = require("fs");
const path = require("path");

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// We load the full specs JSON so the critic can cross-reference sockets/TDP
const specsPath = path.join(__dirname, "../data/componentSpecs.json");
const allSpecs = JSON.parse(fs.readFileSync(specsPath, "utf8"));

async function criticAgent(state) {
  console.log("Agent 2 (Critic): Reviewing the draft...");

  // The Critic reads the draft created by the Architect!
  const draftBuild = state.draftBuild;

  // If there is no build drafted then skip critique
  if (!draftBuild || draftBuild.length === 0) {
    return { critique: { approved: true, issues: [] } };
  }

  // Gather the full specs for the drafted items
  const draftedItemsWithSpecs = draftBuild
    .map((item) => allSpecs[item.id])
    .filter(Boolean);

  const systemInstruction = `
    You are the Critic Agent. Your job is to review a drafted PC build and find fatal errors.
    
    CHECK FOR:
    1. Socket Mismatch (e.g. AMD CPU on Intel LGA1700 Motherboard).
    2. RAM Mismatch (e.g. DDR5 RAM on a DDR4 Motherboard).
    3. Severe Bottlenecks (e.g. RTX 4060 paired with a low-end CPU).
    `;

  const prompt = `Drafted Build Specs:\n${JSON.stringify(draftedItemsWithSpecs, null, 2)}`;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: prompt,
    config: {
      systemInstruction,
      tools: [{
        functionDeclarations: [{
          name: "submit_critique",
          description: "Submits the critique of the drafted PC build.",
          parameters: {
            type: "OBJECT",
            properties: {
              approved: { type: "BOOLEAN", description: "Whether the build is approved (true) or has fatal flaws (false)" },
              issues: { 
                type: "ARRAY", 
                items: { type: "STRING" }, 
                description: "List of specific incompatibilities or issues found" 
              },
              reply: { type: "STRING", description: "Conversational message warning the user about the issues, or praising the build if approved." }
            },
            required: ["approved", "issues", "reply"]
          }
        }]
      }],
      toolConfig: {
        functionCallingConfig: {
          mode: "ANY",
          allowedFunctionNames: ["submit_critique"],
        },
      },
    },
  });

  const call = response.functionCalls?.[0];
  if (!call || call.name !== "submit_critique") {
    throw new Error("Agent failed to call submit_critique tool.");
  }
  
  const critique = call.args;

  // Update the LangGraph State
  return {
    critique: critique,
    // We append the critic's verdict to the chat history
    messages: [
      { role: "assistant", content: `[Critic Verdict]: ${critique.reply}` },
    ],
  };
}

module.exports = { criticAgent };