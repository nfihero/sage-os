import { lazy, Suspense, type ComponentProps } from "react";

const Orb = lazy(() => import("./Orb"));

/** three.js is ~1 MB: load it after first paint; a faint ring holds the space meanwhile. */
export default function LazyOrb(props: ComponentProps<typeof Orb>) {
  const size = props.size ?? 200;
  return (
    <Suspense fallback={<div style={{ width: size, height: size }} className="rounded-full border border-cyan/15" />}>
      <Orb {...props} />
    </Suspense>
  );
}
