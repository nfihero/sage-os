import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { usePageVisible, useCssColor } from "../theme";

export type OrbState = "idle" | "thinking" | "streaming" | "waiting" | "error";

/** Per-state targets; the shader eases toward them every frame, so changes glide. */
const TARGET: Record<OrbState, { spin: number; energy: number; breath: number; attn: number; err: number }> = {
  idle:      { spin: 0.10, energy: 0.05, breath: 0.25, attn: 0, err: 0 },
  thinking:  { spin: 0.45, energy: 0.45, breath: 1.0, attn: 0, err: 0 },
  streaming: { spin: 0.60, energy: 0.85, breath: 0.6, attn: 0, err: 0 },
  waiting:   { spin: 0.16, energy: 0.30, breath: 1.6, attn: 1, err: 0 },
  error:     { spin: 0.05, energy: 0.10, breath: 0.2, attn: 0, err: 1 },
};

const VERT = /* glsl */ `
  uniform float uTime, uEnergy, uWave, uBreath, uSize, uPx, uHalo, uHit;
  attribute float aRand;
  varying float vFront, vLand, vSpark;
  // cheap 3D value noise -> "continents" so the sphere reads as a world, not a ball
  float h(vec3 p){ return fract(sin(dot(p, vec3(127.1,311.7,74.7))) * 43758.5453); }
  float n3(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x), mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x), mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y), f.z); }
  void main(){
    vec3 p = position;
    float land = smoothstep(0.48, 0.62, n3(p * 2.3) * 0.65 + n3(p * 5.1) * 0.35);
    float band = sin(p.y * 9.0 - uTime * 5.0 + aRand * 1.5);               // text waves travel pole to pole
    float spark = max(band, 0.0) * uWave;
    float breathe = 1.0 + uBreath * 0.035 * sin(uTime * 2.4);
    p *= breathe + spark * 0.09 + uEnergy * 0.035 * sin(uTime * 7.0 + aRand * 6.2832) + uHit * 0.06;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    vFront = (normalMatrix * normalize(position)).z;
    vLand = land; vSpark = spark;
    gl_PointSize = uSize * uPx * (0.55 + 0.75 * land + 0.9 * spark) * (3.0 / -mv.z) * mix(1.0, 4.5, uHalo);
  }`;

const FRAG = /* glsl */ `
  uniform vec3 uColor, uAttn, uErr;
  uniform float uAttnMix, uErrMix, uTime, uHalo, uHit, uGlow;
  varying float vFront, vLand, vSpark;
  void main(){
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float core = mix(smoothstep(0.5, 0.0, d), exp(-d * d * 18.0), uHalo);
    vec3 col = mix(uColor, uAttn, uAttnMix);
    col = mix(col, uErr, uErrMix * (0.6 + 0.4 * step(0.5, fract(uTime * 7.0))));
    col = mix(col, vec3(1.0), vSpark * 0.35 + uHit * 0.4);
    float face = smoothstep(-0.35, 0.6, vFront);
    float a = core * (0.16 + 0.84 * face) * (0.5 + 0.5 * vLand + vSpark);
    // halo pass = cheap bloom: bright dots (land, sparks, hits) bleed the most light
    a *= mix(1.0, uGlow * (0.05 + 0.10 * vLand + 0.35 * vSpark + 0.3 * uHit), uHalo);
    gl_FragColor = vec4(col * mix(0.6 + 0.8 * core, 1.0, uHalo), a);
  }`;

/** Soft round sprite so ring and satellite points glow instead of drawing as squares. */
function glowSprite() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.25, "rgba(255,255,255,.55)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

function fibonacci(n: number) {
  const pos = new Float32Array(n * 3), rnd = new Float32Array(n);
  const g = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), t = g * i;
    pos.set([Math.cos(t) * r, y, Math.sin(t) * r], i * 3);
    rnd[i] = Math.random();
  }
  return { pos, rnd };
}

function Sphere({ id, state, color, attn, err, pulse, tool, dots }: {
  id?: string; state: OrbState; color: string; attn: string; err: string; pulse: number; tool: number; dots: number;
}) {
  const group = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Points>(null);
  const sats = useRef<THREE.Points>(null);
  const { pos, rnd } = useMemo(() => fibonacci(dots), [dots]);
  const uniforms = useMemo(() => ({
    uTime: { value: 0 }, uEnergy: { value: 0 }, uWave: { value: 0 }, uBreath: { value: 0 },
    uSize: { value: 2.6 }, uPx: { value: Math.min(window.devicePixelRatio || 1, 2) },
    uColor: { value: new THREE.Color(color) }, uAttn: { value: new THREE.Color(attn) }, uErr: { value: new THREE.Color(err) },
    uAttnMix: { value: 0 }, uErrMix: { value: 0 }, uHalo: { value: 0 }, uHit: { value: 0 }, uGlow: { value: 1 },
  }), []);
  const haloUniforms = useMemo(() => ({ ...uniforms, uHalo: { value: 1 } }), [uniforms]);
  useEffect(() => { uniforms.uColor.value.set(color); uniforms.uAttn.value.set(attn); uniforms.uErr.value.set(err); }, [color, attn, err]);

  // Each streamed chunk bumps the wave; each tool call launches a satellite.
  const wave = useRef(0);
  useEffect(() => { if (pulse) wave.current = Math.min(1.2, wave.current + 0.35); }, [pulse]);
  const hit = useRef(0);
  useEffect(() => {
    if (!id) return;
    const on = (e: Event) => { if ((e as CustomEvent).detail === id) { hit.current = 1; wave.current = Math.min(1.4, wave.current + 0.8); } };
    window.addEventListener("aos-orb-hit", on);
    return () => window.removeEventListener("aos-orb-hit", on);
  }, [id]);
  const satList = useRef<{ t0: number; tilt: number; phase: number }[]>([]);
  useEffect(() => { if (tool) satList.current.push({ t0: performance.now(), tilt: Math.random() * Math.PI, phase: Math.random() * 6.28 }); }, [tool]);

  const ringGeo = useMemo(() => {
    const n = 160, a = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { const t = (i / n) * Math.PI * 2; a.set([Math.cos(t) * 1.42, 0, Math.sin(t) * 1.42], i * 3); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3)); return g;
  }, []);
  const satGeo = useMemo(() => {
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(8 * 3), 3)); return g;
  }, []);

  useFrame((_, dt) => {
    const k = TARGET[state], e = 1 - Math.exp(-dt * 3);
    const u = uniforms;
    u.uTime.value += dt;
    u.uEnergy.value += (k.energy - u.uEnergy.value) * e;
    u.uBreath.value += (k.breath - u.uBreath.value) * e;
    u.uAttnMix.value += (k.attn - u.uAttnMix.value) * e;
    u.uErrMix.value += (k.err - u.uErrMix.value) * e;
    wave.current *= Math.exp(-dt * 1.6);
    hit.current *= Math.exp(-dt * 2.5);
    u.uHit.value = hit.current;
    u.uWave.value = wave.current + (state === "streaming" ? 0.25 : 0);
    if (group.current) { group.current.rotation.y += dt * k.spin; group.current.rotation.x = 0.35 + Math.sin(u.uTime.value * 0.2) * 0.05; }
    if (ring.current) ring.current.rotation.y -= dt * (0.2 + k.spin * 0.6);
    // satellites: live 4 s on tilted orbits
    const now = performance.now();
    satList.current = satList.current.filter((s) => now - s.t0 < 4000).slice(-8);
    const arr = satGeo.attributes.position.array as Float32Array;
    arr.fill(99);
    satList.current.forEach((s, i) => {
      const t = s.phase + (now - s.t0) / 1000 * 2.2, r = 1.25;
      const x = Math.cos(t) * r, z = Math.sin(t) * r;
      arr.set([x, Math.sin(s.tilt) * z, Math.cos(s.tilt) * z], i * 3);
    });
    satGeo.attributes.position.needsUpdate = true;
  });

  const col = new THREE.Color(color);
  const dotTex = useMemo(glowSprite, []);
  return (
    <group ref={group}>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[pos, 3]} />
          <bufferAttribute attach="attributes-aRand" args={[rnd, 1]} />
        </bufferGeometry>
        <shaderMaterial vertexShader={VERT} fragmentShader={FRAG} uniforms={uniforms}
          transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[pos, 3]} />
          <bufferAttribute attach="attributes-aRand" args={[rnd, 1]} />
        </bufferGeometry>
        <shaderMaterial vertexShader={VERT} fragmentShader={FRAG} uniforms={haloUniforms}
          transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
      <points ref={ring} geometry={ringGeo} rotation={[0.22, 0, 0.1]}>
        <pointsMaterial size={0.05} map={dotTex} color={col} transparent opacity={0.7} depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
      <points ref={sats} geometry={satGeo}>
        <pointsMaterial size={0.32} map={dotTex} color={"#ffffff"} transparent opacity={1} depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
    </group>
  );
}

/**
 * An agent's presence: a rotating sphere of glowing dots.
 * `pulse` should increment on every streamed chunk, `tool` on every tool call.
 * `lowPower` (VRAM nearly full) drops to 12 fps so the orb never competes with a model.
 */
export default function Orb({ id, state, tone = "accent", pulse = 0, tool = 0, size = 200, lowPower = false, dots = 2600 }: {
  id?: string; state: OrbState; tone?: "accent" | "claude"; pulse?: number; tool?: number; size?: number | string; lowPower?: boolean; dots?: number;
}) {
  const visible = usePageVisible();
  const color = useCssColor(tone === "claude" ? "--color-orange" : "--color-cyan");
  const attn = useCssColor("--color-amber");
  const err = useCssColor("--color-red");
  return (
    <div style={{ width: size, height: size, filter: `drop-shadow(0 0 14px ${color}55)` }} className="relative shrink-0"
      data-orb-state={state} data-orb-id={id}>
      <Canvas frameloop={visible ? (lowPower ? "demand" : "always") : "never"} dpr={[1, 2]}
        camera={{ position: [0, 0, 3.4], fov: 45 }} gl={{ antialias: false, alpha: true, powerPreference: "low-power" }}>
        <Sphere id={id} state={state} color={color} attn={attn} err={err} pulse={pulse} tool={tool} dots={dots} />
        {lowPower && <LowPowerTicker />}
      </Canvas>
    </div>
  );
}

/** In "demand" mode nothing renders unless invalidated: tick at ~12 fps. */
function LowPowerTicker() {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const id = setInterval(() => invalidate(), 83);
    return () => clearInterval(id);
  }, [invalidate]);
  return null;
}
