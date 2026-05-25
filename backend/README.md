# Backend -Custom PC Builder

This is the Node.js/Express backend API for the custom PC builder application. It handles user authentication, saving PC builds, and integrating with the Google Gemini AI.

## Key Features

- **Auth API**: User signup and login routes.
- **Builds API**: Endpoints to save user-created PC builds to the database.
- **Gemini AI Integration**:
  - `/api/chat/compatibility`: Evaluates arrays of PC parts to determine if they are structurally and technically compatible.
  - `/api/chat/support`: Answers general tech support and hardware questions.
  - `/api/chat/builder`: Conversational agent for recommending PC builds based on the local inventory.

## Prerequisites & Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

\`\`\`env
PORT=5000
MONGO_URI=mongodb://localhost:27017/pcbuilder  # Or your MongoDB Atlas URI
GEMINI_API_KEY=your_gemini_api_key_here
\`\`\`

## Available Scripts

### `npm start`
Starts the Node server normally.

### `npm run dev` (if configured)
Starts the Node server using `nodemon` for hot-reloading during development.

The server will run on [http://localhost:5000](http://localhost:5000) by default.

## Built With

- [Node.js](https://nodejs.org/)
- [Express.js](https://expressjs.com/)
- [Mongoose](https://mongoosejs.com/)
- [@google/genai](https://www.npmjs.com/package/@google/genai)
