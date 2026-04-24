import { create } from "zustand";

export type AnalysisMode = "beginner" | "advanced";

interface ModeState {
  mode: AnalysisMode;
  setMode: (mode: AnalysisMode) => void;
  toggleMode: () => void;
}

export const useModeStore = create<ModeState>((set, get) => ({
  mode: "beginner",
  setMode: (mode) => set({ mode }),
  toggleMode: () =>
    set({ mode: get().mode === "beginner" ? "advanced" : "beginner" }),
}));
