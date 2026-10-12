---
version: 1
slug: "ui-src-app-tsx"
primary_target: "ui/src/App.tsx"
related_targets: ["ui/src/components/Home.tsx","ui/src/index.css","ui/src/components/Readout.tsx"]
---

# Home (desktop app window and phone)

Scope: the app shell and home view (agent panel, search and chat, inbox / digest / recent notes, systems strip) plus the Systems view. Mode: Operate.

Audience and task: the owner, all day, beside other work: search and ask the library, review inbox cards, switch agents, glance at the machine. Testers next (F1). Content is real; never invented.

Constraints: motion only when it means something; standard navigation and controls; 375 px phone; reduced motion honoured.

## Decision (11 Oct 2026)

The owner REJECTED a replacement world (mockup `docs/mockups/home-v3-sage-scope.html`, "SAGE situation display": "way too basic, and it got rid of the design of the planet card that I liked"). The incumbent phosphor terminal world stays. Work on this surface is refinement: make every element match the agent planet card and the clock.

The reference vocabulary (from the planet card and clock), shared in `ui/src/components/Readout.tsx`:

- panels with the notched filled tab title;
- readout rows: small caps label left, mono value right, dashed hairline under each;
- dot-matrix meters (`vram-bar` / `vram-fill`);
- numbers and ages in Doto with the phosphor glow, like the clock;
- no rolling refresh bar (removed: it distracted).

Do not replace the world, fonts or palette without the owner asking.
