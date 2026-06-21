const { ChromaClient } = require("chromadb");
const { GoogleGenAI } = require("@google/genai");
const fs = require("fs");
const path = require("path");

// 1. Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// 2. Connect to ChromaDB (using the new syntax to fix the path warning)
const client = new ChromaClient({ host: "localhost", port: 8000 });

// 3. Create a Custom Embedding Function to silence ChromaDB warnings
const googleEmbeddingFunction = {
  generate: async (texts) => {
    const embeddings = [];
    for (const text of texts) {
      try {
        // Using the latest Gemini Embedding model available to your account
        const response = await ai.models.embedContent({
          model: "gemini-embedding-2",
          contents: text,
        });
        embeddings.push(response.embeddings[0].values);
      } catch (err) {
        // Fallback to the older v1 model if v2 fails
        const fallbackResponse = await ai.models.embedContent({
          model: "gemini-embedding-001",
          contents: text,
        });
        embeddings.push(fallbackResponse.embeddings[0].values);
      }
    }
    return embeddings;
  },
};


async function initializeVectorStore() {
  console.log("Initializing Vector Store...");
  try {
    // We pass our custom function here so ChromaDB stops complaining
    const collection = await client.getOrCreateCollection({
      name: "pc_components",
      embeddingFunction: googleEmbeddingFunction,
    });

    const specsPath = path.join(__dirname, "../data/componentSpecs.json");
    if (!fs.existsSync(specsPath)) {
      console.log("No componentSpecs.json found, skipping RAG init.");
      return;
    }

    const specsData = JSON.parse(fs.readFileSync(specsPath, "utf8"));

    const ids = [];
    const documents = [];
    const metadatas = [];

    for (const [id, specs] of Object.entries(specsData)) {
      const docText = `ID: ${id}. Product: ${specs.name}. Category: ${specs.category}. Price: ${specs.price} rupees. Details: ${JSON.stringify(specs)}. Best used for: ${specs.bestFor ? specs.bestFor.join(", ") : "general use"}.`;
      ids.push(id);
      documents.push(docText); // ChromaDB will automatically convert this to embeddings using our function above
      metadatas.push({
        category: specs.category,
        price: specs.price,
        name: specs.name,
      });
    }

    // Save to ChromaDB
    await collection.upsert({
      ids: ids,
      documents: documents,
      metadatas: metadatas,
    });

    console.log(`✅ Vector Store initialized with ${ids.length} components.`);
  } catch (error) {
    console.error("Error initializing vector store:", error);
  }
}

async function retrieveRelevantComponents(query, nResults = 5) {
  try {
    const collection = await client.getCollection({
      name: "pc_components",
      embeddingFunction: googleEmbeddingFunction,
    });

    // Search ChromaDB using plain text! It handles the embedding automatically.
    const results = await collection.query({
      queryTexts: [query],
      nResults: nResults,
    });

    if (results && results.documents && results.documents[0]) {
      return results.documents[0];
    }
    return [];
  } catch (error) {
    console.error("Error retrieving from vector store:", error);
    return [];
  }
}

module.exports = {
  initializeVectorStore,
  retrieveRelevantComponents,
};
