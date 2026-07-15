"use client";

import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "debrief_api_key";

interface ApiKeyContextValue {
  apiKey: string;
  setApiKey: (key: string) => void;
  ready: boolean;
}

const ApiKeyContext = createContext<ApiKeyContextValue | null>(null);

export function ApiKeyProvider({ children }: { children: React.ReactNode }) {
  const [apiKey, setApiKeyState] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setApiKeyState(localStorage.getItem(STORAGE_KEY) ?? "");
    setReady(true);
  }, []);

  function setApiKey(key: string) {
    setApiKeyState(key);
    localStorage.setItem(STORAGE_KEY, key);
  }

  return (
    <ApiKeyContext.Provider value={{ apiKey, setApiKey, ready }}>{children}</ApiKeyContext.Provider>
  );
}

export function useApiKey(): ApiKeyContextValue {
  const ctx = useContext(ApiKeyContext);
  if (!ctx) throw new Error("useApiKey must be used within an ApiKeyProvider");
  return ctx;
}
