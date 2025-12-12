import { create } from 'zustand';

const useUIStore = create((set) => ({
  messages: [
    { id: 1, text: "Hello! I am your In House CogniCAD. How can I help you today", sender: 'bot' }
  ],

  // Storage for separated histories
  chatHistory: {
    'INHOUSE_CAD': [{ id: 1, text: "Hello! I am your In House CogniCAD. How can I help you today", sender: 'bot' }],
    'CATIA_COPILOT': [{ id: 1, text: "Hello! I am your Catia Co-Pilot. How can I help you today", sender: 'bot' }]
  },

  setMessages: (messages) => set({ messages }),

  // Switcher: Saves current messages to oldMode, loads newMode messages
  switchChatHistory: (oldMode, newMode) => set((state) => {
    // 1. Save current
    const updatedHistory = {
      ...state.chatHistory,
      [oldMode]: state.messages
    };
    // 2. Load new (if exists, else default?)
    // (It should exist from init, but good to be safe)
    const nextMessages = updatedHistory[newMode] || [];

    return {
      chatHistory: updatedHistory,
      messages: nextMessages
    };
  }),

  addMessage: (text, sender, action = null) => set((state) => ({
    messages: [...state.messages, { id: `${Date.now()}-${Math.random()}`, text, sender, action }]
  })),
  isLoading: false,
  setLoading: (isLoading) => set({ isLoading }),

  // Script output / Results logic
  latestResult: null,
  setLatestResult: (result) => set({ latestResult: result }),

  // Upload Logic
  uploadProgress: 0,
  setUploadProgress: (progress) => set({ uploadProgress: progress }),
  attachmentPreview: null,
  setAttachmentPreview: (preview) => set({ attachmentPreview: preview }),

  // Wing Optimization Mode
  wingMode: false,
  setWingMode: (mode) => set({ wingMode: mode }),



  measureMode: false,
  setMeasureMode: (active) => set({ measureMode: active, measurePoints: [] }),

  measurePoints: [],
  addMeasurePoint: (point) => set((state) => {
    // Determine new points
    let newPoints;
    if (state.measurePoints.length >= 2) {
      newPoints = [point];
    } else {
      newPoints = [...state.measurePoints, point];
    }
    return { measurePoints: newPoints };
  }),

  transformMode: false,
  setTransformMode: (active) => set({ transformMode: active }),

  // Visual Effects
  colorMode: false,
  setColorMode: (active) => set({ colorMode: active }),

  explodeMode: false,
  setExplodeMode: (active) => set({ explodeMode: active }),

  // Theme
  isDarkMode: false,
  toggleTheme: () => set((state) => ({ isDarkMode: !state.isDarkMode })),

  // Command History
  commandHistory: [],
  addToHistory: (cmd) => set((state) => {
    if (!cmd || !cmd.trim()) return {};
    const trimmed = cmd.trim();
    const last = state.commandHistory.length > 0 ? state.commandHistory[state.commandHistory.length - 1] : null;
    if (last === trimmed) return {}; // No duplicate sequential
    return { commandHistory: [...state.commandHistory, trimmed] };
  }),

  // Viewer Settings
  orientationCubeVisible: true,
  setOrientationCubeVisible: (visible) => set({ orientationCubeVisible: visible }),

  // Model Rotation (Text Command)
  modelRotation: { x: 0, y: 0, z: 0 },
  setModelRotation: (rotation) => set({ modelRotation: rotation }),

  // Camera View Requests (Smart Views)
  requestedView: null,
  setRequestedView: (view) => set({ requestedView: view }),
}));


export default useUIStore;
