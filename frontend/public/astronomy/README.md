# Lunar surface asset

`moon-surface-nasa.webp` is derived from NASA Scientific Visualization Studio's
2026 full-Moon rendering:

- Source: https://svs.gsfc.nasa.gov/5587/
- Original: `phase_full.1571_print.jpg`
- Credit: NASA Scientific Visualization Studio; Ernie Wright (USRA), visualizer;
  Noah Petro (NASA/GSFC), planetary scientist.
- Local transformation: black border trimmed, resized to 256 x 256 pixels, and
  converted to WebP for the application.

The application clips this surface dynamically using its calculated lunar-cycle
progress. The source image is not requested at runtime.
