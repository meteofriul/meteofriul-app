const green = "#2F7D57", slate = "#49697F";
const SPECIES = { ambrosia: "ragweed", artemisia: "mugwort", betulla: "birch", graminacee: "grass", olivo: "olive", ontano: "alder" };

export function CamsSpeciesIcon({ species }) {
  const key = species.replace(/_pollen$/, "");
  const id = SPECIES[key] || key;
  let drawing;
  if (id.startsWith("particulate")) {
    const fine = id.includes("2.5");
    drawing = <g fill={fine ? "#005A96" : slate} stroke="none">
      {(fine ? [[10,10],[21,8],[31,13],[15,24],[29,29],[9,33]] : [[11,11],[29,12],[20,30]]).map(([x,y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={fine ? 2 : 3.5} />)}
      <path d="M5 18h20q8 0 8-5M8 25h19" fill="none" stroke={fine ? "#005A96" : slate} strokeWidth="2" />
    </g>;
  } else if (id === "ozone" || id === "nitrogen_dioxide") {
    drawing = <g stroke="#063A60"><path d="M10 28 20 12 31 28" fill="none" />
      <circle cx="10" cy="28" r="5" fill="#4D9BC2"/><circle cx="31" cy="28" r="5" fill="#4D9BC2"/>
      <circle cx="20" cy="12" r="6" fill={id === "ozone" ? "#4D9BC2" : "#063A60"}/></g>;
  } else {
    const shapes = {
      ragweed: <><path fill={green} d="M20 4 24 12 22 16 30 11 28 19 24 22 34 20 29 28 22 31 18 31 11 28 6 20 16 22 12 19 10 11 18 16 16 12Z"/><path stroke="#cbe2d4" d="M20 9v27m0-11-7-5m7 9 8-5"/></>,
      mugwort: <><path fill={green} d="m20 4 3 11 8-8-2 10-6 5 11-4-4 10-9 4-6-2-8-9 10 3-7-11 9 5Z"/><path stroke="#b8ccc5" d="M20 10v26m0-10-7-7m7 10 8-6"/></>,
      birch: <><path fill={green} d="m20 4 5 7 1 4 5 3-1 3 4 4-5 2-3 4-6 2-6-2-3-4-5-2 4-4-1-3 5-3 1-4Z"/><path stroke="#cbe2d4" d="M20 11v25m0-11-7-5m7 9 8-6"/></>,
      grass: <><path fill={green} d="M19 36Q4 22 7 6q11 11 12 30M21 36Q20 13 33 4q-2 18-12 32"/><path stroke="#cbe2d4" d="M10 12 18 32m5-2 7-20"/></>,
      olive: <><path fill={green} d="M10 34Q5 13 30 5 32 24 10 34Z"/><path stroke="#cbe2d4" d="M9 36 28 8"/><path stroke={slate} d="M15 29 24 15"/></>,
      alder: <><path fill={green} d="M20 9C5-1 1 20 10 28q10 10 20-1C39 15 33 1 20 9Z"/><path stroke="#cbe2d4" d="M20 13v23m0-14-9-5m9 11 10-6"/></>,
    };
    drawing = <g stroke={green} fill="none">{shapes[id] || <path d="M20 35V8m0 17L10 15m10 5L30 10"/>}</g>;
  }
  return <svg className="mf-cams-species-icon" viewBox="0 0 40 40" aria-hidden="true" focusable="false" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{drawing}</svg>;
}
