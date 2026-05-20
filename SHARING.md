# How to share Edgeless OTel Command

This is an internal playbook for the maintainers (currently: you). It is not
indexed by the registry. It's just a checklist of *where* to post and *what
to say*, with prepared copy you can paste verbatim.

## Audience map

The people who will pay attention:

| Audience | What hooks them |
|----------|-----------------|
| Solo devs running agent swarms (Hermes, Claude Code, custom orchestrators) | "Stop guessing where your bots are stuck" + the screenshot |
| Self-hosting / homelab crowd | Free, Electron, no telemetry, local Jaeger |
| Aesthetic-driven dev tooling crowd (htop, btop, lazygit, glow, fzf) | The Outrun screenshot + the manifesto |
| Open-source observability folks | The plug-in store + decentralized registry pattern |
| Anthropic / Claude Code ecosystem | The `OTEL_EXPORTER_OTLP_ENDPOINT` config in `~/.claude/settings.json` |

Three of those buckets are the priority. The other two are bonus.

## Where to post (in order)

### 1. Show HN

Highest leverage. Post once. Use the title format HN expects.

**Title**:
```
Show HN: Edgeless OTel Command – an observability dashboard for agent swarms
```

**Body** (~150 words, paste as the first comment):
```
Edgeless OTel Command is a desktop dashboard that points at any Jaeger
backend and renders 6 panels of agent-swarm telemetry: throughput, op
breakdown, latency heatmap, live trace log, real-time anomaly detection
(phantom stalls, ghost agents, runaway loops), and a click-through trace
waterfall. It's Electron, MIT, ~3000 LOC.

The thing I think makes it interesting is the plug-in system: panels and
anomaly rules are JS modules with a manifest; install is `git clone` into
userData. The community registry is one JSON file on GitHub raw content —
no server, no DB, no account. A 5-minute "Show HN: my dashboard panel" PR
loop.

Three plug-ins exist as of today (Service Map, Static Field, an Example
scaffold). Seven themes including an Outrun synthwave skin.

Built it because Datadog is too expensive for solo devs running 8 agents
and Jaeger UI is too generic. Curious what you'd want to see in the
registry next.

GitHub: https://github.com/thedavidmurray/edgeless-otel-command
Plug-ins: https://github.com/thedavidmurray/edgeless-otel-plugins-registry
```

**Best times to post** (rough heuristic for HN): Tue–Thu, 7–9 a.m. PT, 1
hour after a quiet news cycle. Avoid Mon (post-weekend flood) and Fri
afternoon (dead).

### 2. r/selfhosted

The homelab crowd loves a free, local-first dashboard.

**Title**:
```
[Tool] Free, local-first observability dashboard for AI agent swarms (Electron, MIT, plug-in store)
```

**Body**: same as HN but lead with the self-hosted angle:

> If you're running Hermes / Claude Code / a custom orchestrator and have
> ever wished you could see what your agents are actually doing in real
> time without paying Datadog $70/month per host, this might help. It
> wraps Jaeger and adds anomaly detection + a plug-in store, all running
> on your own machine.

### 3. r/devops, r/programming

Different audiences than r/selfhosted. r/programming wants the technical
story (decentralized registry, plug-in API). r/devops wants the OTel
angle.

**r/programming title**:
```
I built a desktop OTel dashboard with a decentralized plug-in store on top of a single JSON file in a GitHub repo
```

**r/devops title**:
```
Open-source desktop Jaeger frontend with anomaly detection, themes, and a plug-in system
```

### 4. Lobste.rs

Probably needs an invite. Worth it if you have one. Audience is small but
quality. Tag with `release` and `release announcement`.

### 5. Targeted Discords / Slacks

| Channel | Note |
|---------|------|
| OpenTelemetry community Slack | Post in `#general-discussion` — keep it short, link to GitHub, leave |
| Anthropic Claude developer Discord | The Claude Code OTel integration is the hook here; show the env vars |
| Hermes / agent-swarm communities | The dashboard exists *because* of Hermes-shaped problems |
| r/LocalLLaMA Discord | Some self-hosters there will be running multi-agent setups |

Each gets one message + a screenshot. Don't crosspost in 6 channels of
the same Discord.

### 6. Twitter / X

You don't need this for HN but it amplifies. Format:

```
edgeless otel command — desktop dashboard for watching your agent
swarm in real time

→ free, MIT, electron
→ 7 themes including a synthwave skin
→ plug-in store via github json (no server)
→ anomaly detection, click-through trace drill-down

github.com/thedavidmurray/edgeless-otel-command

[attach screenshot of outrun theme]
```

Lowercase the whole thing — it matches the product's voice.

## What screenshots to attach

The screenshot is most of the pitch. Prepare three:

1. **Default Phosphor theme**, default 6-box layout, with traces flowing.
   This is the "professional" shot. Use it on HN and r/devops.

2. **Outrun theme**, with Static Field plug-in installed, ~500 spans
   visible. This is the "this is a thing with character" shot. Use it on
   r/programming and Twitter.

3. **The Plug-in Store view** with 3+ plug-ins listed. This is the "this
   isn't a dashboard, it's a platform" shot. Use it in the body of
   technical posts.

Take them at 1600×1000 (matches retina), crop tight, no window chrome.

## Things NOT to do

- **Don't pay for promotion.** This is community software. It will lose
  credibility instantly if it's marketed.
- **Don't crosspost the same wording everywhere.** Reddit notices.
  Reword for each audience.
- **Don't oversell.** "An observability dashboard for agent swarms" is
  exactly what it is. Don't call it a platform, a paradigm, or a
  revolution.
- **Don't reply to every comment.** Reply substantively to the first
  10–15 questions; let the rest of the thread go.
- **Don't link to product pages, calendars, or mailing list signups.**
  Repo, manifesto, registry. That's it.

## After it ships

Things that will happen in the first 72 hours if the launch goes well:

- People will install it and immediately hit either (a) "I don't have
  Jaeger running" or (b) "my service name doesn't show up." Have a
  pinned issue or section in `SETUP.md` for both.
- Someone will open a PR adding a plug-in to the registry. Review within
  24h. The submission loop has to feel responsive or the platform
  reputation dies fast.
- Someone will complain about the aesthetic. They are not the audience.
  Thank them and move on.
- Someone will ask if you'll add login / cloud sync / a SaaS tier.
  See §I of MANIFESTO.md.

## What to do *before* posting

- [ ] Pin a recent release on the main repo
- [ ] README has up-to-date screenshot
- [ ] PLUGINS.md links work
- [ ] Registry has at least 3 plug-ins (it does)
- [ ] At least one issue label set up (`good first issue`, `plug-in submission`)
- [ ] CONTRIBUTING.md exists (the registry has one)
- [ ] You're personally available to respond for ~6 hours after posting

## Long-term distribution

These don't matter for the first launch but are worth queueing:

- **A 60-second screencap on YouTube**. Mute. Just the dashboard doing
  things. Title: "edgeless otel command — agent swarm observability".
  Pin in README.
- **A blog post on `edgelesslab.com`**. The 3000-word "why I built this
  and how it works." Reference the manifesto. Use it as canonical link
  in future posts.
- **A talk submission** to one of: OpenObservabilityCon, LocallyOptimal,
  any AI-engineering meetup. The plug-in registry pattern is the talk.
