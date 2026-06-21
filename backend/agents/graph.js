const { StateGraph, Annotation, END, START } = require("@langchain/langgraph");
const { architectAgent } = require("./architectAgent");
const { criticAgent } = require("./criticAgent");
const { reviewerAgent } = require("./reviewerAgent");
const { comparatorAgent } = require("./comparatorAgent");
const { GoogleGenAI } = require("@google/genai");

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// 1. Define the LangGraph "State" (The memory that gets passed between agents)
const GraphState = Annotation.Root({
  messages: Annotation({
    reducer: (x, y) => x.concat(y),
    default: () => [],
  }),
  draftBuild: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
  architectReply: Annotation({
    reducer: (x, y) => y ?? x,
    default: () => null,
  }),
  userBudget: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
  critique: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
  reviews: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
  comparison: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
  nextStep: Annotation({ reducer: (x, y) => y ?? x, default: () => null }),
});

// 2. The Supervisor Agent - Decides who does the work
async function supervisorAgent(state) {
  console.log("Supervisor: Routing the request...");
  const lastMessage = state.messages[state.messages.length - 1].content;

  const systemInstruction = `
    You are the Supervisor routing requests for a PC store.
    If the user asks to compare two or more parts, route to "COMPARATOR".
    If the user asks to build a PC, upgrade a part, or asks for recommendations, route to "ARCHITECT".
    If the user asks a completely irrelevant question, route to "END".
    `;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: `User request: ${lastMessage}`,
    config: { 
      systemInstruction,
      tools: [{
        functionDeclarations: [{
          name: "route_request",
          description: "Routes the user request to the correct agent.",
          parameters: {
            type: "OBJECT",
            properties: {
              route: {
                type: "STRING",
                description: "The agent to route to. Must be ARCHITECT, COMPARATOR, or END."
              }
            },
            required: ["route"]
          }
        }]
      }],
      toolConfig: {
        functionCallingConfig: {
          mode: "ANY",
          allowedFunctionNames: ["route_request"],
        },
      },
    },
  });

  const call = response.functionCalls?.[0];
  if (!call || call.name !== "route_request") {
    throw new Error("Supervisor failed to call route_request tool.");
  }

  const route = call.args.route;
  console.log(` Supervisor decided to route to: ${route}`);

  return { nextStep: route };
}

// 3. Router logic
function routeFromSupervisor(state) {
  if (state.nextStep.includes("COMPARATOR")) return "comparator";
  if (state.nextStep.includes("ARCHITECT")) return "architect";
  return END;
}

// 4. Build the LangGraph Flowchart
const workflow = new StateGraph(GraphState)
  .addNode("supervisor", supervisorAgent)
  .addNode("architect", architectAgent)
  .addNode("critic", criticAgent)
  .addNode("reviewer", reviewerAgent)
  .addNode("comparator", comparatorAgent)

  // Start by sending user input to the Supervisor
  .addEdge(START, "supervisor")

  // Supervisor routes to either Architect, Comparator, or END
  .addConditionalEdges("supervisor", routeFromSupervisor)

  // If Architect is chosen, it drafts a build, then ALWAYS passes to the Critic
  .addEdge("architect", "critic")

  // The Critic reviews it, then ALWAYS passes to the Reviewer
  .addEdge("critic", "reviewer")

  // The Reviewer adds pros/cons, and then the flow ends
  .addEdge("reviewer", END)

  // If Comparator was chosen, it does its job and then ends
  .addEdge("comparator", END);

// Compile it into an executable app
const graphApp = workflow.compile();

module.exports = { graphApp };
