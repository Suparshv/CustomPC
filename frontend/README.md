# Frontend -Custom PC Builder

This is the React frontend for the custom PC builder application. It handles the user interface, routing, and communication with the backend APIs.

## Key Features

- **PC Builder Interface (`/custompc`)**: Interactive UI for selecting PC parts by category (CPU, GPU, Motherboard, etc.).
- **Live AI Compatibility**: Intercepts part additions and calls the Gemini backend API to warn users of hardware mismatches.
- **AI Chat Assistant**: A floating chat widget that uses Gemini to help users with tech support and build recommendations.
- **Authentication**: Custom login and signup modals.
- **Cart & Checkout**: Global cart state management using React Context.

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.
You may also see any lint errors in the console.

## Environment Variables

Currently, the frontend connects directly to `http://localhost:5000`. If you wish to configure a different backend URL, you can update the Axios endpoints or configure a `.env` file with `REACT_APP_API_URL`.

## Built With

- [React](https://reactjs.org/)
- [React Router](https://reactrouter.com/)
- [Bootstrap 5](https://getbootstrap.com/)
- [Axios](https://axios-http.com/)
