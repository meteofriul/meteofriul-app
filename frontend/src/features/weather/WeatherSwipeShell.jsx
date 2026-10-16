import { useRef } from "react";
import { weatherSwipeTarget } from "./weatherSwipeTarget";

const EXCLUDED = "button,a,input,textarea,select,summary,[role=slider],[role=dialog],[contenteditable=true],iframe,video,canvas,.leaflet-container,[class*=radar],[class*=carousel],[class*=webcam],[data-no-weather-swipe]";

export function WeatherSwipeShell({ activeId, disabled, onNavigate, children }) {
  const gesture = useRef(null);
  // The pilot uses explicit section buttons; nested scrolling and dialogs own
  // their gestures. Keep the shell layout without installing swipe handlers.
  if (disabled) return <div className="mf-weather-route-shell">{children}</div>;
  return <div className="mf-weather-route-shell"
    onTouchStart={(event) => {
      gesture.current = null;
      if (disabled || event.touches.length !== 1 || event.target.closest?.(EXCLUDED)) return;
      for (let node = event.target; node && node !== event.currentTarget; node = node.parentElement) {
        if (node.scrollWidth > node.clientWidth + 2 && /auto|scroll/.test(getComputedStyle(node).overflowX)) return;
      }
      const touch = event.touches[0];
      // Leave Android/browser edge navigation alone.
      if (touch.clientX < 24 || touch.clientX > window.innerWidth - 24) return;
      gesture.current = { x: touch.clientX, y: touch.clientY, at: event.timeStamp, activeId };
    }}
    onTouchMove={(event) => {
      const start = gesture.current;
      if (!start) return;
      const touch = event.touches[0];
      if (event.touches.length !== 1 || Math.abs(touch.clientY - start.y) > 24) gesture.current = null;
    }}
    onTouchCancel={() => { gesture.current = null; }}
    onTouchEnd={(event) => {
      const start = gesture.current;
      gesture.current = null;
      if (!start || disabled || start.activeId !== activeId || event.changedTouches.length !== 1) return;
      const touch = event.changedTouches[0];
      const target = weatherSwipeTarget(activeId, touch.clientX - start.x, touch.clientY - start.y, event.timeStamp - start.at);
      if (target) onNavigate?.(target);
    }}
  >{children}</div>;
}
