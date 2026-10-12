---
version: 1
slug: "ui-src-app-tsx"
primary_target: "ui/src/App.tsx"
related_targets: ["ui/src/components/Home.tsx","ui/src/index.css"]
---

# Home (desktop app window and phone)

Scope: the whole Sage OS app shell and its home view (agent panel, search and chat, inbox / digest / recent notes, systems strip) plus the Systems view. Mode: Operate.

Audience and task: the owner, all day, beside other work: search and ask the library, review inbox cards, switch agents, glance at the machine. Testers next (F1). Content is real (library, inbox, digests, GPU readings); never invented.

Constraints: keep the planet card, Doto numerals and the boot screen; motion only when it means something; standard navigation and controls (Operate); 375 px phone; reduced motion honoured.

## Direction contract

THESIS: The home is a SAGE situation display: everything you need to know is read off phosphor scopes, and the agent lives in the big round one. It refuses the category default of flat dark panels with a sidebar.

OWN-WORLD: Console steel ground (blue-grey, near black) holding glass tube faces. P7 phosphor: a blue-white flash (#d8f3ff) that decays to yellow-green (#9dff5c) on near-black glass (#020806). One round scope with range rings and bearing ticks; rounded-rectangle tube faces with an inner glass curve; square back-lit push-buttons that light when active; amber (#ffb547) only for "needs you", red only for broken. Doto for labels and numerals, JetBrains Mono for data, a system sans for sentences.

STORY: The visitor sees their agent alive in the scope, searches or asks straight away, and notices what changed because it is still glowing.

FIRST VIEWPORT: Left column: the agent scope (planet inside range rings, state readouts on the bezel), agent buttons beneath. Centre: search as a light-pen line across the top of the main tube, the conversation below. Right: inbox tube (tracks to clear), digest and recent notes. Bottom: a console strip of lamps and readouts. Primary action: the search line.

FORM: SAGE Situation Display, IMPECCABLE'S PICK (my rank 1 of 7), chosen over the roll; seed 6b461500.

Signature interaction: P7 afterglow, things that change flash blue-white and decay to green; pointing shows a light-pen reticle.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
