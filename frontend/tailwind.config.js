/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        slate900: "#0f172a",
        slate800: "#1e293b",
        slate700: "#334155",
        teal500: "#14b8a6",
        amber500: "#f59e0b",
        rose500: "#f43f5e"
      }
    }
  },
  plugins: []
};
