# Smoke Queries

Run these after deploying schemas and prompt overrides.

## People / org

- Who owns onboarding?
- Who does Jane report to?
- What team is Jane on?
- Show the org chart from available people and team memories.
- Who is responsible for enterprise pricing?

## Teams

- What does the Growth team own?
- Who leads Engineering?
- Which team owns lifecycle emails?

## Decisions

- What did we decide about the flexible memory area name?
- Why did we choose pages instead of cards?
- What active decisions mention OpenViking?
- Which decisions are proposed, accepted, or superseded?

## Projects

- What are active projects?
- What is blocked?
- Who owns the Loisa company brain project?

## Pages

- What does the onboarding process say?
- What is the Hermes/OpenViking memory boundary?
- What risks are recorded around memory pollution?
- What glossary entry explains Loisa?

## Expected behavior

- Retrieval should prioritize `viking://user/company/memories/people` and `teams` for org questions.
- Retrieval should prioritize `decisions` for decision/history questions.
- Retrieval should use `pages` for flexible topics like SOPs, glossary, risks, customers, and engineering notes.
- Answers should not use OpenViking for user preferences/tool memories.
- When evidence is absent, answers should not pretend exact citations exist.
