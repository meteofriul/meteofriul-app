// This separate development entry never mounts App or imports live API clients.
// The normal Vite build has only index.html as its input.
if (import.meta.env.DEV && ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname)) {
  const [{ createRoot }, { default: CommunityPreview }] = await Promise.all([
    import("react-dom/client"),
    import("./CommunityPreview.jsx"),
  ]);
  createRoot(document.getElementById("root")).render(<CommunityPreview />);
} else {
  document.getElementById("root").textContent = "Anteprima disponibile soltanto nell'ambiente locale.";
}
