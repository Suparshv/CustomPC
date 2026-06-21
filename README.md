# Custom PC Builder

A full-stack e-commerce web application inspired by NZXT, allowing users to browse PC components, build their own custom PC, get AI-powered compatibility checks, and save their builds.

## Project Structure

This project is divided into two main parts:

- **[`frontend/`](./frontend)**: The React.js frontend application. (Runs on port 3000)
- **[`backend/`](./backend)**: The Node.js/Express backend API. (Runs on port 5000)

## Core Features

- **Custom PC Builder**: Select individual parts (CPU, GPU, RAM, Motherboard, etc.) to build a custom PC.
- **User Authentication**: Sign up and login functionality.
- **Cart & Checkout**: Save builds to your cart (tied to your user session) and proceed to checkout.
- **Responsive UI**: Modern, dark-themed UI built with React and Bootstrap.

## Advanced AI Architecture (Gemini 2.5 + LangGraph)

This project features a fully autonomous, production-grade **Multi-Agent AI System** that can design, critique, and review PC builds from scratch.

- **LangGraph Multi-Agent Routing**: A graph-based workflow featuring 4 specialized AI agents (Supervisor, Architect, Critic, Reviewer, Comparator).
- **RAG (Retrieval-Augmented Generation)**: The AI actively queries the local component database to ensure it only recommends real, in-stock parts.
- **Strict Function Calling (Tools)**: All LLM outputs are forced into strict JSON schemas via API-level Function Calling to guarantee 0% data hallucination.
- **Conversational Memory**: Chat sessions are persisted in MongoDB, allowing the AI to remember your previous questions.
- **Self-Critiquing Hardware Validation**: The AI automatically checks its own builds for CPU/GPU bottlenecks, Socket Mismatches, and DDR compatibility before showing them to the user.

## Prerequisites

- **Node.js** (v16 or higher recommended)
- **MongoDB** (Local or Atlas)
- **Docker** (Required to run the ChromaDB Vector Database)
- **Google Gemini API Key**

## Getting Started

To run this project locally, you will need to start the vector database, the backend server, and the frontend server.

### 1. Start ChromaDB (Vector Database via Docker)
Before running the backend, you must spin up ChromaDB for the RAG engine to retrieve parts:
```bash
docker pull chromadb/chroma
docker run -p 8000:8000 chromadb/chroma
```

### 2. Setup the Backend
Navigate to the backend directory, install dependencies, and start the server.
```bash
cd backend
npm install
npm run start
```
*(See the [Backend README](./backend/README.md) for more details on environment variables).*

### 3. Setup the Frontend
Navigate to the frontend directory, install dependencies, and start the development server.
```bash
cd frontend
npm install
npm start
```
*(See the [Frontend README](./frontend/README.md) for more details).*

## Tech Stack

- **Frontend**: React.js, React Router, Bootstrap
- **Backend**: Node.js, Express.js, Mongoose
- **AI Engine**: `@google/genai` (Gemini 2.5 Flash), `@langchain/langgraph` (JS v0.2)
- **Database**: MongoDB (User Auth, Cart Sessions), ChromaDB via Docker (Vector Database for RAG)
