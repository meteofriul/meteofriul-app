import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { EventsRadiusSelect } from "./EventsRadiusSelect";

describe("event radius", () => {
  it("offers every 5 km through 50 and defaults to 20 km", () => {
    const html = renderToStaticMarkup(<EventsRadiusSelect />);
    expect(html.match(/<option /g)).toHaveLength(10);
    for (let radius = 5; radius <= 50; radius += 5) expect(html).toContain(`>${radius} km</option>`);
    expect(html).toContain('value="20" selected=""');
  });
  it("rejects unknown values", () => {
    const onChange = vi.fn();
    const select = EventsRadiusSelect({ onChange });
    select.props.onChange({ target: { value: "500" } });
    expect(onChange).not.toHaveBeenCalled();
    select.props.onChange({ target: { value: "30" } });
    expect(onChange).toHaveBeenCalledWith(30);
  });
});
