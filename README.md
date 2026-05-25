# Custom PC Builder

A full-stack e-commerce web application inspired by NZXT, allowing users to browse PC components, build their own custom PC, get AI-powered compatibility checks, and save their builds.

## Project Structure

This project is divided into two main parts:

- **[`frontend/`](./frontend)**: The React.js frontend application. (Runs on port 3000)
- **[`backend/`](./backend)**: The Node.js/Express backend API. (Runs on port 5000)

## Features

- **Custom PC Builder**: Select individual parts (CPU, GPU, RAM, Motherboard, etc.) to build a custom PC.
- **Gemini AI Compatibility Checker**: Uses Google's Gemini AI to verify if your selected parts are compatible in real-time.
- **AI Support Assistant**: Integrated chat assistant to help with PC building questions.
- **User Authentication**: Sign up and login functionality.
- **Cart & Checkout**: Save builds to your cart and proceed to checkout.
- **Responsive UI**: Modern, dark-themed UI built with React and Bootstrap.

## Prerequisites

- **Node.js** (v16 or higher recommended)
- **MongoDB** (Local or Atlas)
- **Google Gemini API Key**

## Getting Started

To run this project locally, you will need to start both the backend and frontend servers in separate terminal windows.

### 1. Setup the Backend
Navigate to the backend directory, install dependencies, and start the server.
\`\`\`bash
cd backend
npm install
npm run start
\`\`\`
*(See the [Backend README](./backend/README.md) for more details on environment variables).*

### 2. Setup the Frontend
Navigate to the frontend directory, install dependencies, and start the development server.
\`\`\`bash
cd frontend
npm install
npm start
\`\`\`
*(See the [Frontend README](./frontend/README.md) for more details).*

## Tech Stack

- **Frontend**: React.js, React Router, Bootstrap, Axios
- **Backend**: Node.js, Express.js, Mongoose, @google/genai
- **Database**: MongoDB
