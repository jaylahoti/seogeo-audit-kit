"use client";

import { createContext, useContext } from "react";

// Lets a report section reload the audit (e.g. after "Count every page" finishes).
export const RefreshContext = createContext<() => Promise<void>>(async () => {});
export const useReportRefresh = () => useContext(RefreshContext);
