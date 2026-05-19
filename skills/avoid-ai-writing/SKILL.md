---
name: avoid-ai-writing
description: Learn how to write better and remove AI writing patterns and make them sound direct, specific, and human. Use for any artefact that will be seen by user like Slack messages, internal notes, emails, posts, docs, launch copy, and other writing.
version: 3.4.0-phoenix.2
license: MIT
metadata:
  hermes:
    tags: [writing, editing, voice, slack, rewrite, ai-writing]
    upstream: https://github.com/conorbronsdon/avoid-ai-writing
    upstream_author: Conor Bronsdon
---

# Avoid AI Writing

Rewrite the user's draft so it sounds like a person wrote it: direct, specific,
plainspoken, and appropriately imperfect. Preserve the user's intent, facts,
constraints, and level of formality.

This Phoenix version always rewrites and returns only the final rewritten text.
All audit notes, issue lists, and final-pass checks are internal. Do not show
the user `Changed:`, `What changed`, `Final pass`, issue lists, rationale,
editing notes, or labels around the rewrite.

## Effort

Adjust effort to the shape and risk of the draft.

### Lightweight Slack Rewrite

Use this for quick Slack replies, short internal notes, and simple status
updates, especially under about 80 words or 3 short sentences.

- Do one focused rewrite pass.
- Return only the rewritten message.
- Keep it casual when the original is casual.
- Fix only obvious AI tells, awkward phrasing, excess polish, and needless
  hedging.
- Do not add an issues list, severity labels, or a second-pass report.

### Standard Rewrite

Use this for longer Slack messages, internal announcements, emails, posts, and
short artifacts that need more than sentence-level cleanup.

- Audit the draft internally, then rewrite it.
- Return only the rewritten text.
- Do a quick final read for leftover filler, repeated sentence shapes, and
  over-polished rhythm, but do not expose notes or a second-pass section.

### Full Rewrite

Use this for public copy, important emails, docs, blog posts, investor/customer
messages, launch announcements, or any draft that is long, structured, or dense
with AI tells. Also use it for long Slack messages where tone and credibility
matter.

Audit the draft internally, rewrite it, then run a final internal pass before
responding. Return only the final corrected draft. Do not show section labels,
change bullets, review notes, or pass/fail commentary.

## What To Fix

Prioritize the edits that most affect whether the text sounds generated:

- Chatbot artifacts: "Certainly", "Great question", "I hope this helps",
  "feel free to reach out", "let me know if you need anything else".
- Meta narration: "Let's dive in", "Let's explore", "in this article we will",
  "to answer your question", "breaking this down".
- Inflated claims: "pivotal moment", "game-changer", "the future looks bright",
  "only time will tell", "poised to revolutionize".
- Promotional filler: "vibrant", "thriving", "nestled", "robust",
  "seamless", "cutting-edge", "world-class", "best-in-class".
- Vague attribution: "experts believe", "studies show", "industry leaders
  agree" without a named source.
- Hollow confidence cues: "it is important to note", "notably",
  "interestingly", "surprisingly", "undoubtedly", "without a doubt".
- Padding: "in order to", "due to the fact that", "when it comes to",
  "at the end of the day", "the reality is that".
- Copula avoidance: "serves as", "features", "boasts", "presents" when "is" or
  "has" is clearer.
- Thesaurus cycling: forced variation like "developers", "engineers",
  "practitioners", and "builders" when one clear word should repeat.
- Formula openings and closings: broad setup before the point, generic summary
  paragraphs, and conclusions that do not add a specific thought.
- Over-structured output: too many headers, numbered lists padded to a count,
  bold label bullets, symmetrical bullet lists, and repetitive paragraph sizes.
- Rhythm problems: same-length sentences, same sentence starts, uniform
  paragraph length, too-clean grammar, and no personal stance where a stance is
  expected.
- Placeholder leaks: visible bracket placeholders, `2025-XX-XX`, todo comments,
  internal citation tokens, or AI-tool URL tracking parameters.

## Word Choices

Use the plain alternative when the flagged word is acting as filler. Keep the
original word when it is precise in context, especially in technical docs.

| Replace                     | Prefer                                         |
| --------------------------- | ---------------------------------------------- |
| leverage, utilize           | use                                            |
| commence, embark            | start, begin                                   |
| ascertain                   | find out, determine                            |
| facilitate                  | help, enable, make possible                    |
| empower                     | let, allow, enable                             |
| streamline                  | simplify, speed up                             |
| foster, cultivate           | build, encourage, support                      |
| bolster                     | support, strengthen                            |
| delve into, deep dive       | examine, look at, dig into                     |
| unpack                      | explain, walk through                          |
| landscape, realm, ecosystem | field, area, market, system                    |
| paradigm                    | model, approach                                |
| robust                      | strong, reliable                               |
| comprehensive               | full, thorough                                 |
| seamless                    | smooth, easy                                   |
| actionable                  | useful, practical, concrete                    |
| impactful                   | effective, meaningful, specific result         |
| intricate, multifaceted     | name the actual complexity                     |
| crucial, paramount          | important, necessary                           |
| significant                 | give the number, comparison, or reason         |
| innovative                  | say what is new                                |
| transformative              | say what changed                               |
| thought leadership          | expertise, point of view, argument             |
| best practices              | proven approach, standard approach, what works |

Watch for boilerplate clusters, even when each phrase is acceptable alone:

- "the integration of"
- "the intersection of"
- "emerging space"
- "community-driven"
- "long-term sustainability"
- "user engagement"
- "designed for long-term..."
- "real" or "actual" before an abstract noun without a named contrast
- stacked hedges such as "could potentially" or "may eventually"

## Slack Bias

Most Phoenix output lands in Slack. For Slack rewrites:

- Prefer concise messages with a clear first sentence.
- Keep human friction when it helps: "I think", "I would", "I am not sure yet",
  "roughly", and short fragments can be better than polished neutrality.
- Preserve useful directness. Do not turn an internal note into marketing copy.
- Avoid visible editing scaffolding.
- Do not over-correct emoji, bullets, or casual punctuation if they fit Slack
  and are not carrying the AI smell.
- Do not add facts, metrics, names, or promises that were not in the original.

## Public Or High-Stakes Bias

For customer, investor, hiring, legal, policy, public, or leadership-facing
text:

- Tighten promotional language harder.
- Remove unsupported certainty and vague attribution.
- Keep claims falsifiable and sourced when the original provides sources.
- Replace broad value claims with the concrete mechanism or consequence.
- Preserve necessary caveats, but remove double hedges.

## Self-Reference

If the draft is about AI writing patterns, examples inside quotes, code blocks,
or clearly marked examples are allowed to contain bad phrasing. Rewrite the
author's prose, not the illustrative bad examples.

## Output Defaults

- Return only the rewritten text for short, medium, and full rewrites.
- Do not include change notes, issue lists, final-pass notes, section labels, or
  explanations.
- If the original already sounds natural, return the smallest useful edit. If no
  edit is needed, return the original text only.
