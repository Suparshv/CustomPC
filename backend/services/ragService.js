const { ChromaClient } = require("chromadb");
const { GoogleGenAI } = require("@google/genai");
const fs = require("fs");
const path = require("path");

// 1. Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// 2. Connect to ChromaDB
const client = new ChromaClient({ host: "localhost", port: 8000 });

// 3. Custom Embedding Function using Google standard text-embedding-004
const googleEmbeddingFunction = {
  generate: async (texts) => {
    const embeddings = [];
    for (const text of texts) {
      try {
        const response = await ai.models.embedContent({
          model: "text-embedding-004",
          contents: text,
        });
        embeddings.push(response.embedding.values || response.embeddings[0].values);
      } catch (err) {
        try {
          const fallbackResponse = await ai.models.embedContent({
            model: "embedding-001",
            contents: text,
          });
          embeddings.push(fallbackResponse.embedding.values || fallbackResponse.embeddings[0].values);
        } catch (e) {
          console.error("Embedding generation error:", e.message);
          throw e;
        }
      }
    }
    return embeddings;
  },
};

// Helper: load all inventory specs directly from disk as text
function getDiskComponents() {
  try {
    const specsPath = path.join(__dirname, "../data/componentSpecs.json");
    if (!fs.existsSync(specsPath)) return [];
    const specsData = JSON.parse(fs.readFileSync(specsPath, "utf8"));
    return Object.entries(specsData).map(
      ([id, specs]) =>
        `ID: ${id}. Product: ${specs.name}. Category: ${specs.category}. Price: ${specs.price} rupees. Details: ${JSON.stringify(specs)}. Best used for: ${specs.bestFor ? specs.bestFor.join(", ") : "general use"}.`
    );
  } catch (err) {
    console.error("Error reading componentSpecs from disk:", err.message);
    return [];
  }
}

async function initializeVectorStore() {
  console.log("Initializing Vector Store...");
  try {
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
      documents.push(docText);
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
    console.error("Error initializing vector store (disk fallback active):", error.message);
  }
}

async function retrieveRelevantComponents(query, nResults = 25) {
  try {
    const collection = await client.getCollection({
      name: "pc_components",
      embeddingFunction: googleEmbeddingFunction,
    });

    const results = await collection.query({
      queryTexts: [query],
      nResults: nResults,
    });

    if (results && results.documents && results.documents[0] && results.documents[0].length > 0) {
      return results.documents[0];
    }
    console.warn("ChromaDB returned 0 results, falling back to local componentSpecs.json");
  } catch (error) {
    console.warn("ChromaDB query failed or container restarted, using disk inventory fallback.");
  }

  // ROBUST FALLBACK: Always ensure Architect receives inventory
  const diskParts = getDiskComponents();
  if (diskParts.length > 0) {
    return diskParts.slice(0, nResults);
  }
  return [];
}

module.exports = {
  initializeVectorStore,
  retrieveRelevantComponents,
};
