---
name: avoid-ai-writing
description: Write or revise non-Slack Loisa outputs so they sound direct, specific, and human. Use for internal notes, emails, posts, docs, launch copy, website copy, memos, and other written artifacts. Do not use this for Slack message formatting; use the Slack message skill for Slack-native replies.
version: 3.4.0-loisa.2
license: MIT
metadata:
  hermes:
    tags: [writing, editing, voice, slack, rewrite, ai-writing]
    upstream: https://github.com/conorbronsdon/avoid-ai-writing
    upstream_author: Conor Bronsdon
---

# Avoid AI Writing for Artifacts

Write Hermes output so it sounds like a person wrote it: direct, specific, plainspoken, and appropriately imperfect. Preserve the user's intent, facts, constraints, and level of formality.

This skill is for the artifact itself, not the Slack wrapper around it. If Hermes is writing a Slack reply, use the Slack message skill. If Hermes is previewing a non-Slack artifact inside Slack, use this skill for the artifact body and the Slack message skill for the surrounding Slack message.

Always return the finished artifact unless the user explicitly asks for rationale, alternatives, or review notes. Keep audit notes, issue lists, and final-pass checks internal. Do not show `Changed:`, `What changed`, `Final pass`, issue lists, rationale, editing notes, or labels around the output.

## Effort

Adjust effort to the shape and risk of the artifact.

### Light Pass

Use this for short internal notes, simple email replies, brief updates, and small copy blocks.

- Do one focused pass.

- Return only the finished text.

- Keep casual writing casual.

- Fix only obvious AI tells, awkward phrasing, excess polish, and needless hedging.

- Do not add an issues list, severity labels, or a second-pass report.

### Standard Pass

Use this for internal announcements, emails, posts, short docs, and artifacts that need more than sentence-level cleanup.

- Audit the output internally, then write the final version.

- Return only the finished text.

- Do a quick final read for leftover filler, repeated sentence shapes, and over-polished rhythm, but do not expose notes or a second-pass section.

### Full Pass

Use this for public copy, important emails, docs, blog posts, investor/customer messages, launch announcements, website copy, or any artifact that is long, structured, high-stakes, or dense with AI tells.

Audit the output internally, write the final version, then run a final internal pass before responding. Return only the final corrected artifact. Do not show section labels, change bullets, review notes, or pass/fail commentary.

## What To Fix

Prioritize the edits that most affect whether the text sounds generated:

- Chatbot artifacts: "Certainly", "Great question", "I hope this helps", "feel free to reach out", "let me know if you need anything else".

- Meta narration: "Let's dive in", "Let's explore", "in this article we will", "to answer your question", "breaking this down".

- Inflated claims: "pivotal moment", "game-changer", "the future looks bright", "only time will tell", "poised to revolutionize".

- Promotional filler: "vibrant", "thriving", "nestled", "robust", "seamless", "cutting-edge", "world-class", "best-in-class".

- Vague attribution: "experts believe", "studies show", "industry leaders agree" without a named source.

- Hollow confidence cues: "it is important to note", "notably", "interestingly", "surprisingly", "undoubtedly", "without a doubt".

- Padding: "in order to", "due to the fact that", "when it comes to", "at the end of the day", "the reality is that".

- Copula avoidance: "serves as", "features", "boasts", "presents" when "is" or "has" is clearer.

- Thesaurus cycling: forced variation like "developers", "engineers", "practitioners", and "builders" when one clear word should repeat.

- Formula openings and closings: broad setup before the point, generic summary paragraphs, and conclusions that do not add a specific thought.

- Over-structured output: too many headers, numbered lists padded to a count, bold label bullets, symmetrical bullet lists, and repetitive paragraph sizes.

- Rhythm problems: same-length sentences, same sentence starts, uniform paragraph length, too-clean grammar, and no personal stance where a stance is expected.

- Placeholder leaks: visible bracket placeholders, `2025-XX-XX`, todo comments, internal citation tokens, or AI-tool URL tracking parameters.

## Word Choices

Use the plain alternative when the flagged word is acting as filler. Keep the original word when it is precise in context, especially in technical docs.

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

## Artifact Bias

For non-Slack artifacts:

- Lead with the point, not the setup.

- Use structure only when it helps the reader move faster.

- Keep headings specific, not generic.

- Avoid decorative formatting that makes a note, email, post, or doc feel machine-made.

- Preserve the expected shape of the artifact: emails should read like emails, posts like posts, docs like docs, and website copy like website copy.

- Do not add facts, metrics, names, links, promises, dates, or claims the user did not provide.

## Public Or High-Stakes Bias

For customer, investor, hiring, legal, policy, public, or leadership-facing text:

- Tighten promotional language harder.

- Remove unsupported certainty and vague attribution.

- Keep claims falsifiable and sourced when the original provides sources.

- Replace broad value claims with the concrete mechanism or consequence.

- Preserve necessary caveats, but remove double hedges.

## Self-Reference

If the artifact is about AI writing patterns, examples inside quotes, code blocks, or clearly marked examples are allowed to contain bad phrasing. Rewrite the author's prose, not the illustrative bad examples.

## Output Defaults

- Return only the finished artifact for light, standard, and full passes.

- Do not include change notes, issue lists, final-pass notes, section labels, or explanations.

- If the output already sounds natural, make the smallest useful edit. If no edit is needed, return the original text only.

- If the user asks for options, make the options meaningfully different rather than mechanically varied.

- If the user asks for a draft from scratch, write the draft directly instead of saying you rewrote it.
