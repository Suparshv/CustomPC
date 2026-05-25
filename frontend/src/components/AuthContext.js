import React, { createContext, useState, useContext } from "react";

// 1.context
const AuthContext = createContext(null);

// 2. Provider component
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = sessionStorage.getItem("user");
    return savedUser ? JSON.parse(savedUser) : null;
  });
  
  const [showAuth, setShowAuth] = useState(false);

  // Function to update the state upon login
  const login = (userData) => {
    sessionStorage.setItem("user", JSON.stringify(userData));
    setUser(userData);
  };

  // Function to clear the state upon logout
  const logout = () => {
    sessionStorage.removeItem("user");
    setUser(null);
  };

  // The value that will be available to all children components
  const value = {
    user,
    login,
    logout,
    showAuth,
    setShowAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// 3.  custom hook to easily use the context
export const useAuth = () => {
  return useContext(AuthContext);
};
