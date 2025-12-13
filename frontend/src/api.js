import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000'; // Default FastAPI port

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    // 'Content-Type': 'application/json', // Let axios set it automatically for FormData
  },
});

export const runCommand = async (command, extraData = {}) => {
  try {
    const payload = { command, ...extraData };
    const response = await api.post('/run_command', payload, {
      headers: { 'Content-Type': 'application/json' }
    });
    return response.data;
  } catch (error) {
    console.error("API Error:", error);
    return { output: "Error communicating with backend." };
  }
};

export const uploadFile = async (file, type, convert = null) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  if (convert !== null) {
    formData.append('convert', convert);
  }

  try {
    const response = await api.post('/upload', formData);
    return response.data;
  } catch (error) {
    console.error("Upload Error:", error);
    const msg = error.response?.data?.detail || error.message || "Unknown error";
    return { error: `Upload failed: ${msg}` };
  }
};

export const convertFile = async (filename) => {
  const formData = new FormData();
  formData.append('filename', filename);

  try {
    const response = await api.post('/convert', formData);
    return response.data;
  } catch (error) {
    console.error("Convert Error:", error);
    return { error: "Failed to convert file." };
  }
};

// Window control functions
export const splitLeft = async () => {
  try {
    const response = await api.get('/split-left');
    return response.data;
  } catch (error) {
    console.warn("Split left failed:", error);
    return { error: "Window control failed" };
  }
};

export const splitRight = async () => {
  try {
    const response = await api.get('/split-right');
    return response.data;
  } catch (error) {
    console.warn("Split right failed:", error);
    return { error: "Window control failed" };
  }
};

export const maximizeWindow = async () => {
  try {
    const response = await api.get('/max-window');
    return response.data;
  } catch (error) {
    console.warn("Maximize window failed:", error);
    return { error: "Window control failed" };
  }
};

export default api;
