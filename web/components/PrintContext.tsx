"use client";

import { createContext, useContext } from "react";

// True while the report renders everything for "Export PDF" (all modules, every page type expanded).
export const PrintAllContext = createContext(false);
export const usePrintAll = () => useContext(PrintAllContext);
