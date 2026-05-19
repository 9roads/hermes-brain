---
name: slack-message-design
description: Draft Slack messages that look native, concise, scannable, human, and intentionally designed. You MUST use this skill before writing or responding to any Slack message.
---

# Slack Message Design

Write Slack messages that look like they belong in Slack: short, readable, visually structured, and easy to act on.

## Core principle

Design only when design helps.

A one-line reply should stay plain. A simple message should not become a card, announcement, or over-designed post. A multi-line update, announcement, request, approval, standup, recap, or decision ask should be shaped so the reader can scan it in a few seconds.

When in doubt, under-format.

A good Slack message answers:

1. What is this about?
2. Why should I care?
3. What is the status or key information?
4. What should I do, who owns it, and by when?

## Design ladder

Pick the smallest useful shape.

### Level 0: Plain reply

Use for quick replies, confirmations, small nudges, and normal chat.

```text
Works for me. Let's ship it!
```

Rules:

- no headline
- no section labels
- no bullets
- no CTA footer
- no emoji unless it genuinely matches the tone
- no bold unless one word or phrase truly needs emphasis

### Level 1: Lightly formatted message

Use for a short update or ask where one visual anchor helps.

```text
✅ **QA is done**
No blockers from the regression pass. Ready for the release branch.
```

Rules:

- one emoji max
- one bold phrase max
- 2–4 lines max
- no field-card structure
- no decorative headings

### Level 2: Structured post

Use for updates, decisions, short recaps, risks, and requests with several facts.

```text
⚠️ **Heads up: onboarding emails are delayed**
Impact: new users may wait ~15 minutes for their first email.
Plan: infra is checking the queue now.
Next update: 2 PM CT.
```

Rules:

- clear top line
- short field lines or bullets
- one idea per line
- action/deadline visible

### Level 3: Designed card or announcement

Use only for launches, company/team announcements, workflow outputs, approvals, incident posts, customer wins, or messages with several sections.

```text
🚀 **Shipped: new onboarding checklist**
What changed: new users now get a guided setup flow.
Who it affects: all self-serve signups.
Details: [Onboarding launch notes]
```

Rules:

- chunk into sections
- use emoji as section markers
- keep sections short
- push long detail to a thread or doc

## Default output behavior

When the user asks for a Slack message or rewrite:

- Output the finished Slack message only, unless they ask for explanation or options.
- Preserve the user's facts. Do not invent owners, metrics, dates, links, names, IDs, or deadlines.
- Choose the smallest useful design level.
- Keep normal messages under 6 lines.
- For longer announcements, use short chunks with clear visual anchors.
- Prefer directness over polish.
- Do not write like an email.
- Do not add a greeting or sign-off unless it materially improves the message.
- Avoid technical implementation details unless the user specifically asks for them.
- Make the output look like something a human teammate would post.

If a necessary detail is missing:

- For a human-facing draft, use readable placeholders like `[owner]`, `[deadline]`, `[Launch doc]`, or `[channel]`.
- For Slack-ready automation text, use Slack mention/link/date syntax only when the required IDs or URLs are provided.
- Do not fabricate Slack IDs, channel IDs, user group IDs, timestamps, links, or handles.

## Human-readable output rules

The message should read like a Slack message, not a payload, template, or system log.

Do not output raw technical material unless specifically requested:

- no naked URLs
- no standalone internal IDs
- no Unix timestamps
- no JSON payloads
- no unformatted ISO dates unless the user asked for exact machine-readable output
- no unexplained ticket IDs, object IDs, or database identifiers
- no raw Slack IDs outside Slack mention tokens

Use human labels instead:

- `Launch notes` instead of `https://...`
- `#growth` instead of `C0123ABC` in human-facing text
- `@design` instead of `S0123ABC` in human-facing text
- `Thursday EOD` instead of `2026-05-21T23:59:00-05:00`
- `tomorrow at 2 PM CT` instead of `1779390000`

Exception: Slack mention tokens are allowed when the output is meant to be sent directly to Slack and the IDs are available. They may look technical in the draft, but they render as normal mentions in Slack.

## Mentions, channels, groups, links, and dates

Use Slack-native references when the message is intended to be posted by an app, workflow, webhook, or integration and the required IDs are available.

### How to get IDs

Most of the time you will not have the actual IDs needed for Slack mentions. Use Composio MCP search tool to get a tool that would allow you to find the right IDs for users, channels, and user groups.

### People

If a Slack user ID is available, mention the user with the ID token:

Example: <@U12345678>

Use this for direct mentions in Slack-ready output. Do not use a fake ID. If the ID is not available, write the person's visible name or handle in the human draft.

### Channels

If a Slack channel ID is available, link the channel with the channel token.

Example: <#C12345678>

### User groups / teams

If a Slack user group ID is available, mention the group with the subteam token.

Example: <!subteam^S12345678>

### Special mentions

Use broad mentions sparingly and only when the user explicitly asks or the urgency clearly justifies it.

Example: `<!here>`, `<!channel>`, `<!everyone>`

Strongly prefer specific people or user groups over broad alerts.

### Links

Never output naked URLs in the Slack message unless the user explicitly asks for raw text.

Use a display name:

```text
Details: [Launch notes]
```

For Slack-ready API/webhook text, use a labeled link when the URL is known:

```text
Details: <https://example.com/launch-notes|Launch notes>
```

If composing a human-facing draft and the URL is not needed in the visible text, use the label only:

```text
Details: Launch notes
```

Good link labels are specific:

- `Launch notes`
- `Dashboard`
- `Customer thread`
- `PR #482`
- `Incident doc`
- `Signup funnel chart`

Bad:

```text
https://example.com/launch-notes
Click here
[link]
```

Use `[link]` only as a placeholder when the user has not provided the URL and no better label is possible.

### Dates and times

Use human-readable dates and times by default.

Good:

```text
Need a decision by Thursday EOD.
Next update: today at 2 PM CT.
Launch window: May 22, 9–11 AM PT.
```

Avoid exposing raw timestamps:

```text
1779390000
2026-05-22T16:00:00Z
```

For app-generated Slack messages where local timezone rendering matters, use Slack date syntax only when the timestamp is available, and always include a readable fallback:

```text
<!date^1779390000^{date_short} at {time}|May 21 at 2:00 PM CT>
```

Do not show Slack date syntax in normal human drafts unless the user asked for Slack-ready automation text.

## Visual grammar

Use these Slack-native design primitives only when they improve scanning.

### 1. Headline line

Use a short top line that tells the reader what kind of message this is.

```text
🚀 **Shipped: [thing]**
```

Good headline traits:

- starts with the outcome, not the backstory
- uses one leading emoji only when helpful
- bolds the phrase people should notice first
- avoids vague titles like “Update” or “FYI” unless the context is tiny

Do not add a headline to a simple reply.

### 2. Chunk heading

Use emoji + bold label when a message has multiple topics.

```text
🏆 **Big win:** [one-sentence summary]
- [supporting fact]
- [supporting fact]
```

Chunk headings are best for announcements, summaries, launches, and weekly updates.

### 3. Field line

Use field lines for requests, approvals, logistics, and forms.

```text
📅 **Date/time:** [value]
👤 **Owner:** [value]
🍽️ **Catering:** [value]
🚫 **Restriction:** [value]
```

Rules:

- one field per line
- label first, value second
- bold the label, not the value
- keep field names stable and predictable
- put the decision/action after the fields

Do not use a field card for a casual DM or one-sentence update.

### 4. Status bullets

Use emoji bullets when each line is one status item.

```text
✅ [done / on track]
🟡 [in progress / needs attention]
🔴 [blocked / needs help]
🚀 [next / coming up]
```

For reflection-style prompts, a more playful triad works well:

```text
🌹 [success]
🌵 [challenge]
🚀 [looking forward to]
```

Status bullets should be skimmed vertically. Do not make each line a paragraph.

### 5. Bullet cluster

Use bullets for 2–5 related facts under one heading.

```text
**Context**
- [fact]
- [fact]
- [fact]
```

Rules:

- bullets should be parallel in shape
- no bullet should be longer than two lines
- avoid nested bullets unless the message is a recap or plan
- if you need more than five bullets, split into sections or move detail to a thread/doc

### 6. Quote or indented block

Use a visually separated block for:

- quoted context
- bug reports
- customer excerpts
- ordered next steps
- “what happens next” after an announcement

```text
> 1️⃣ [next step]
> 2️⃣ [next step]
> 3️⃣ [next step]
```

This is useful when the main message is short but the supporting detail needs to be visually contained.

### 7. CTA footer

End with the action when action is needed.

```text
Need a decision by **[time/date]** so [reason].
```

or

```text
Reply ✅ to approve, or flag concerns by **[deadline]**.
```

Rules:

- one CTA per message when possible
- owner and deadline should be obvious
- avoid vague endings like “thoughts?” unless brainstorming is the point
- avoid “let me know if you have any questions” as filler

## Emoji rules

Use emoji as visual labels, not decoration.

Default limits:

- plain reply: usually 0-1 emoji
- simple message: 0–1 emoji
- structured update: 1 emoji per section if useful
- request/approval card: emoji per field is acceptable
- celebration: more energy is fine, but keep it controlled
- incident or serious issue: use only one alert/status emoji

## Message recipes

Choose the recipe based on the user's intent. Do not announce which recipe you used unless asked.

### Quick update

Use for compact status messages. If it can be one plain sentence, use one plain sentence instead.

```text
✅ **[What changed]**
[Impact in one sentence.]
Next: [owner/action/deadline].
```

### Heads up / risk

Use when people need awareness but not panic.

```text
⚠️ **Heads up: [risk/change]**
Impact: [who/what is affected]
Plan: [what happens next]
```

### Incident / urgent

Use sparse formatting. Do not be cute.

```text
🚨 **Incident: [short name]**
Impact: [scope]
Status: [current state]
Owner: [person/team]
Next update: [time]
```

### Bug/help request with context

Use when asking someone to jump in, review, or fix something.

```text
👋 **Need help with [issue]**

> [brief quoted context, error, customer note, or reproduction detail]

Can someone own this by **[deadline]**? I'm blocked on [reason].
```

### Daily standup

Use one line per category. Keep it boring and scannable.

```text
✅ Yesterday: [done]
🟡 Today: [focus]
🔴 Blocked: [blocker or “none”]
```

### Weekly reflection

Use a lightweight emoji triad.

```text
🌹 [one success]
🌵 [one challenge]
🚀 [one thing you're looking forward to]
```

### Company or team announcement

Use chunked sections. Each section gets a visual anchor.

```text
🦃 **This week at [company/team]**

🏆 **[Main win or headline].** [One-sentence context.]
- [supporting fact]
- [supporting fact]

📣 **[Important update].** [What people need to know.]

📅 **[Deadline / closure / event].** [Action or timing.]
- [step]
- [step]
```

Rules:

- lead with the highest-signal item
- bold section titles, not entire paragraphs
- use bullets only under sections that need detail
- make dates, links, and deadlines visually obvious
- avoid turning announcements into dense essays

### Sales/customer win

Use result first, then context, then next steps.

```text
🏆 **[Customer] [result].**
- [why this matters]
- [customer/context detail]
- [shoutouts or collaboration]

🎉 **What continued success looks like:**
> 1️⃣ [next step]
> 2️⃣ [next step]
> 3️⃣ [next step]
```

Rules:

- do not bury the win
- include shoutouts only if they add meaning
- separate celebration from follow-through
- make next steps concrete

### Request / approval card

Use when a person or team needs to approve, prepare, or respond.

```text
🤝 **[Request type]**
Hi [owner] 👋 — [requester] requested [thing].

📅 **Date/time:** [value]
👤 **People:** [value]
📍 **Location:** [value]
📝 **Notes:** [value]

Reply ✅ to approve, or flag concerns by **[deadline]**.
```

For app/workflow outputs, keep the same structure but use the shortest possible button label, such as `Approve`, `Confirm booking`, `Assign`, or `Review`.

### Decision ask

Use when the message needs a call, not just discussion.

```text
👀 **Decision needed: [topic]**
Context: [one sentence]

Options:
- **A:** [tradeoff]
- **B:** [tradeoff]

My take: [recommendation]
Need a call by **[deadline]**.
```

Rules:

- include a recommendation when possible
- keep options symmetric
- make the deadline explicit
- do not ask for open-ended feedback if a decision is needed

### Feedback request

Use when asking for review without creating ambiguity.

```text
👀 **Feedback wanted: [thing]**
Looking for: [specific feedback]
Not looking for: [out of scope, if useful]
Deadline: [time/date]
Link: [display-name link]
```

### Meeting recap

Use decisions and actions first. Notes are secondary.

```text
📝 **[Meeting/topic] recap**

**Decisions**
- [decision]
- [decision]

**Actions**
- [owner]: [action] by [deadline]
- [owner]: [action] by [deadline]

**Notes**
- [only if needed]
```

### Launch / shipped

Use for product, feature, process, or internal launch updates.

```text
🚀 **Shipped: [thing]**
What changed: [one sentence]
Who it affects: [audience]
Details: [display-name link]
```

### Kudos / celebration

Use warm, specific praise. Avoid generic applause.

```text
🙌 **Huge thanks to [person/team]** for [specific thing].
Impact: [what changed / who benefited]
```

## Audience tuning

### Public channel

Make the message self-contained. Assume many readers lack context.

Include:

- short context
- impact
- next action
- owner/deadline if relevant

### Thread reply

Do not restate the whole topic. Answer the narrow point.

Good:

```text
On pricing: I'd keep it simple for v1.
```

Bad:

```text
Thanks everyone for the thoughtful discussion. I wanted to share a few thoughts about the broader context...
```

### DM or small group

Be lighter and more direct. Less structure is usually better.

### Executive / leadership channel

Lead with decision, risk, or result. Put details below.

### External Slack Connect

Use slightly less emoji, clearer context, and explicit next steps.

## Brevity rules

Before finalizing, cut:

- throat-clearing
- generic enthusiasm
- repeated context
- obvious explanations
- passive voice
- “just,” “quick,” “wanted to,” “circling back,” “following up,” unless genuinely useful
- “let me know if you have questions” filler
- sign-offs
- long paragraphs
- raw technical artifacts that do not help the reader act

Replace soft, vague asks with specific asks.

Weak:

```text
Would love any thoughts when people have a chance.
```

Better:

```text
Please review the pricing section by **Thursday EOD**.
```

## Density rules

- 1 idea: one line
- 2–3 facts: short bullets
- 3+ categories: emoji + bold section headings
- request/logistics: field card
- sequence/plan: numbered list or quoted block
- long detail: summarize in channel, move detail to a thread/doc

No paragraph should be longer than 2–3 lines in Slack.

## What not to do

Do not produce messages like:

```text
Hey team, hope everyone is doing well! I just wanted to provide a quick update on a few different things that are happening across the company this week...
```

Do not:

- over-format a simple message
- turn a one-line answer into a designed card
- add emoji or bold just because the message is for Slack
- use all caps for urgency
- bury the action at the end of a long paragraph
- put multiple unrelated asks in one message
- fabricate user/channel/group mentions
- expose standalone internal IDs
- output naked URLs
- output Unix timestamps or raw ISO dates in normal human drafts
- use unresolved `@here`, `@channel`, or `@everyone` unless the user explicitly asks
- use tables unless the user specifically wants a table
- include JSON, Block Kit, payloads, API terms, or implementation notes unless requested
