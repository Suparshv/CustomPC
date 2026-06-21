const { GoogleGenAI } = require("@google/genai");
const fs = require("fs");
const path = require("path");

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const specsPath = path.join(__dirname, "../data/componentSpecs.json");
const allSpecs = JSON.parse(fs.readFileSync(specsPath, "utf8"));

async function reviewerAgent(state) {
  console.log("Agent 3 (Reviewer): Analyzing sentiment and pros/cons...");

  const draftBuild = state.draftBuild;
  if (!draftBuild || draftBuild.length === 0) {
    return { reviews: [] };
  }

  const draftedItemsWithSpecs = draftBuild
    .map((item) => allSpecs[item.id])
    .filter(Boolean);

  const systemInstruction = `
    You are the Reviewer Agent.
    For each component in the drafted build, generate a realistic "Pros and Cons" review summary based on its hardware specs, price, and benchmarks.

    CRITICAL RULES:
    1. Be brief and concise.Maximum 1 sentence per pro/con.
    2. Do NOT use any emojis.
    3. Do NOT use markdown formatting.
    4. Provide important pro and con per item.
    `;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: `Drafted Build:\n${JSON.stringify(draftedItemsWithSpecs, null, 2)}`,
    config: {
      systemInstruction,
      tools: [{
        functionDeclarations: [{
          name: "submit_reviews",
          description: "Submits pros and cons reviews for a list of PC components.",
          parameters: {
            type: "OBJECT",
            properties: {
              reviews: {
                type: "ARRAY",
                items: {
                  type: "OBJECT",
                  properties: {
                    component: { type: "STRING" },
                    rating: { type: "STRING" },
                    pros: { type: "ARRAY", items: { type: "STRING" } },
                    cons: { type: "ARRAY", items: { type: "STRING" } },
                    summary: { type: "STRING" }
                  },
                  required: ["component", "rating", "pros", "cons", "summary"]
                }
              }
            },
            required: ["reviews"]
          }
        }]
      }],
      toolConfig: {
        functionCallingConfig: {
          mode: "ANY",
          allowedFunctionNames: ["submit_reviews"],
        },
      },
    },
  });

  const call = response.functionCalls?.[0];
  if (!call || call.name !== "submit_reviews") {
    throw new Error("Agent failed to call submit_reviews tool.");
  }
  
  const reviewsData = call.args;

  return {
    reviews: reviewsData.reviews,
  };
}

module.exports = { reviewerAgent };
