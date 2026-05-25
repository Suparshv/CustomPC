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

A `.env.example` file is provided. Copy it and fill in your values:

```bash
cp .env.example .env
```

Then edit the `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here   # Get free at https://aistudio.google.com/app/apikey
PORT=5000
```

> **Note:** MongoDB is hardcoded to connect to a local instance at `mongodb://127.0.0.1:27017/PC`. Make sure MongoDB is running locally before starting the server.

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
