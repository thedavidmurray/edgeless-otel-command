```
       ┌─────────────────────────────────────────────────────────┐
       │   E D G E L E S S   ::   O T E L   C O M M A N D         │
       │                                                          │
       │       a desktop dashboard for observing agent swarms     │
       │       built for the kind of operator who runs            │
       │       cron jobs at 3 a.m. and reads logs by candlelight  │
       │                                                          │
       └─────────────────────────────────────────────────────────┘
```

# m a n i f e s t o    /    a e s t h e t i c    h a n d b o o k

This is not a marketing page. This is a list of decisions and the reasons
for them, formatted the way an internal memo would be if the company that
ran this software had four employees and seven thousand spans per second.

If you opened this file looking for an installer, see [README.md](README.md).
If you opened it looking for plug-in docs, see [PLUGINS.md](PLUGINS.md).
This document is for people who want to know **why it looks this way**.

──────────────────────────────────────────────────────────────────────────

## §I.  what we are not

We are not Datadog. We do not have a sales team. We will not give you a
sixteen-dimensional drill-down with feature flags gated by your billing tier.
You will not be asked to "talk to an account executive." If you have an
opinion about the colour of a panel border, you can change it in `themes.css`
and not file a ticket about it.

We are also not Jaeger UI. Jaeger UI is a fine reference implementation. It
is also what you would design if you had to please every employer that ever
deployed it. We made different trade-offs. Specifically: we picked one.

We are not Grafana. Grafana is a dashboarding kit. We are a dashboard. The
difference matters: Grafana asks you what you want; we have already decided.

──────────────────────────────────────────────────────────────────────────

## §II.  the aesthetic, stated plainly

```
        ▟███████▙      Pink phosphor on near-black.
        ███████████    Monospaced glyphs. Dense data per pixel.
        ▝█████████▘    Borders that suggest the inside of a machine
         ▝▜█████▘▘     and not the inside of a SaaS dashboard.
```

The reference visuals come from:

- **Synthwave and Outrun** — saturated, two-channel palettes; we ship
  these as themes (`outrun`, `cyberpunk`, `matrix`).
- **The terminal we wish UNIX had given us** — phosphor green, amber on
  black, scanlines, vignette. These are not novelties. They are the only
  pixel-level treatments that survive being looked at for ten hours.
- **Nous Research's documentation typography** — terse, declarative,
  footnoted, ASCII-separated. We aspire to it. We will fall short.
- **The early VLSI photo essays of the 1980s** — circuit-board density,
  small components close together, no whitespace doing nothing.

What we explicitly reject:

- Stock photos of humans pointing at screens.
- Pastel gradients used to mean "modern."
- Drop shadows on cards. Cards are not floating; they are panels.
- Animation that exists to demonstrate that animation is possible.
- The phrase *"powered by AI"* anywhere in the product.

──────────────────────────────────────────────────────────────────────────

## §III.  the seven principles

### 1.  Data first, decoration as evidence

Every visual element corresponds to a real measurement.  The CRT scanlines
are decoration; everything else — bar widths, dot colours, panel pulses,
anomaly badges — is data. If a thing can be moved without changing what
the user knows, it is decoration. Decoration is allowed but it must be
honest about it.

### 2.  Density is a kindness

A dashboard exists because the operator wants to see many things at once.
We do not paginate. We do not collapse panels by default. We do not hide
the things the operator might need. If you came for an iPad app, you
came to the wrong dashboard.

> footnote¹  see the **Static Field** plug-in. ~4000 spans, one screen,
> click any pixel to drill in. that's the model.

### 3.  Borders, not shadows

Edges between things are made by borders, never by drop shadow or
blur. This is for two reasons. (a) Drop shadow is what you reach for
when you don't know what the edge is supposed to mean. (b) Borders are
cheap to render on a slow machine at 3 a.m. when you actually need this.

### 4.  Monospace is non-negotiable in panel content

Variable-width fonts are for documents you read once. Dashboards are
read continuously. Numbers must line up. Identifiers must not jiggle
between renders. The whole product uses `Courier New` falling back to
`Lucida Console` and the system mono. We will not change this.

### 5.  Lowercase, mostly, except when shouting

Lowercase for prose, ALL CAPS for system events. There is no Title Case
in the UI. We are not announcing a feature; we are stating a fact.

### 6.  Colour is semantic, not decorative

```
   cyan      ok / running / nominal
   amber     attention / slow / partial
   red       error / suspended / critical
   text-dim  background information you can ignore
   text-med  context
   bright    the answer to the question you just asked
```

A panel whose border pulses red is telling you something is wrong. A
panel whose border just *happens* to be red because the designer liked
it that day is a lie. We do not lie.

### 7.  The plug-in author is a co-author

We did not build this and then expose a plug-in surface as an
afterthought. Plug-ins extend the same six panels the rest of us use.
There is no "first-class panel" vs. "community panel" distinction. If
you ship a plug-in, you ship a peer.

──────────────────────────────────────────────────────────────────────────

## §IV.  typographic constants

```
   body                Courier New / Lucida Console / mono
   header              same                   (no display face)
   metric value        20px bold              (the answer)
   metric label         9px UPPERCASE         (what the answer is)
   panel label         10px UPPERCASE         (what panel)
   tag                  9px UPPERCASE         (categorical)
   trace ID            10px mono              (identifier)
   tooltip             10px mono              (transient)
```

There is no h1 / h2 / h3 hierarchy in the UI. We have *panel* and
*content*. If you need a sub-heading inside a panel, you have probably
created two panels by accident.

──────────────────────────────────────────────────────────────────────────

## §V.  colour reference (the six themes)

```
   phosphor    green on black              (the default; CRT phosphor)
   cyberpunk   purple/pink on plum         (loud)
   military    amber/olive on khaki        (radar console)
   amber       amber on near-black         (1970s VT100)
   matrix      bright green on black       (you know the one)
   minimal     greys + a single blue       (for monitors over shoulders)
   outrun      hot pink + violet on black  (synthwave / circuit board)
```

Each is a single `[data-theme=...]` block in `themes.css` overriding
about 20 CSS custom properties. Adding a seventh is a 25-line PR.

──────────────────────────────────────────────────────────────────────────

## §VI.  voice and prose

Every piece of writing in this product follows these rules:

1.  **Lead with the fact.** Not "We're excited to announce…" but
    "Service Map panel: nodes are services, edges are calls."
2.  **No em dashes inside the product UI.** Use hyphens or commas. Em
    dashes in *documentation* are allowed and encouraged; the UI is too
    dense to absorb them.
3.  **Footnotes over parenthetical asides.** Parens interrupt the
    reading flow; a small ¹ does not.
4.  **No emojis in prose.** The Store button is allowed one (🏬) because
    it's an icon, not a sentence. The Outrun swatch is a CSS gradient,
    not an emoji. Anomaly cards do not use emojis to indicate severity;
    they use colour and the words [CRIT] [WARN] [OK].
5.  **Cheek over polish.** A line like "phantom stall: a span open for
    30+ min, possibly never closed" is correct *and* a little funny.
    "Phantom Stall: Threshold Configurable in Settings" is correct and
    completely dead. Pick alive.

──────────────────────────────────────────────────────────────────────────

## §VII.  community plug-ins: the social contract

When you publish a plug-in to the registry, you are agreeing to a small
list of things.

(a)  Your plug-in is MIT, Apache 2.0, BSD, or ISC. If you want a
     copyleft license, that's fine; just keep it out of the index until
     we figure out the discoverability story for AGPL panels.

(b)  Your plug-in does what its description says. If your panel
     "visualizes RSS ingestion latency" we will look at it and check
     that it does not, in fact, exfiltrate trace data to your Discord.

(c)  No obfuscated `index.js`. Users should be able to read the code
     before they run it. If you need a build step, commit the built
     output and the source.

(d)  You disclose any outbound network traffic in the description.
     "Sends summaries to a Slack webhook (URL configured by user)" is
     fine. Sending anything we didn't ask about is not.

(e)  You handle being unloaded. Implement `destroy()` if you've
     attached document-level listeners. A leaky plug-in is rude.

In return, your plug-in:

- Shows up in the Store for every user the day after your PR merges.
- Gets free hosting (you're already on GitHub).
- Is treated as a peer of the built-in panels, with the same API,
  the same lifecycle, and the same right to fail loudly.

──────────────────────────────────────────────────────────────────────────

## §VIII.  what success looks like

In one year, we want to be able to look at this and say:

```
   _ A solo developer running a 6-agent swarm uses this instead of paying
     for an APM seat. They are not lonely; many of them exist.

   _ At least three plug-ins in the registry are things we would never
     have built. The Static Field one didn't have to come from us. The
     Service Map one didn't have to come from us. The next one won't.

   _ The aesthetic is recognizable. If someone takes a screenshot, the
     reader knows what software it is without reading the title bar.

   _ Nobody opens an issue asking us to add login.
```

If we get that, we are done.²

> footnote²  We will not be done. We will probably add things like
> alert webhooks, an HTTP client panel, and an LLM-cost overlay. But
> the *shape* will not change.

──────────────────────────────────────────────────────────────────────────

## §IX.  acknowledgments and lineage

This work draws — without irony, with thanks — from:

- **Jaeger Query API**.  The reason this exists at all.
- **OpenTelemetry**.  The reason it works for more than one stack.
- **Nous Research**.  For the documentation aesthetic, the comfort with
  density, and the patient assumption that the reader is smart.
- **Winamp 2.x skins**.  For making us believe that a piece of software
  can be a venue for craft and not just a venue for shipping.
- **Every person who ever wrote an awesome-list**.  You proved that a
  flat JSON file on GitHub is enough infrastructure for a community.

The aesthetic prefers the *machine* to the *human*. This is not anti-
human; it is anti-decoration-of-humans. There are no faces in the UI
because the UI is not about us. It is about the agents we delegated to.
We watch them from a respectful distance, and we make them legible.

──────────────────────────────────────────────────────────────────────────

```
                                                              [ end of file ]
                                                              v 1.3.1
                                                              2026-05-20
                                                              MIT
```
