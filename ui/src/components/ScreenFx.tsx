import { useState } from "react";

/** One tile of speckle noise, generated once; the grain layer jitters it around to shimmer. */
function noiseTile(size = 180) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d")!;
  const img = g.createImageData(size, size);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 200 + Math.random() * 55;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = Math.random() < 0.5 ? Math.random() * 140 : 0;
  }
  g.putImageData(img, 0, 0);
  return c.toDataURL();
}

/**
 * Always-on screen texture: fine scanlines and a flickering film grain (the rolling refresh bar was removed
 * 11 Oct: it distracted). Pure CSS animation on the compositor (no per-frame JS), click-through,
 * and frozen when Motion is set to reduced.
 */
export default function ScreenFx() {
  const [tile] = useState(noiseTile);
  return (
    <div className="fx" aria-hidden>
      <div className="fx-grain" style={{ backgroundImage: `url(${tile})` }} />
      <div className="fx-lines" />
    </div>
  );
}
