"""Shared prompt scaffolding.

Every content type gets its own template (see the sibling modules), but they
all compose the same three building blocks defined here:

1. :data:`AGENT_IDENTITY`   — who the model is acting as.
2. :data:`GROUNDING_CONTRACT` / :data:`OPINION_CONTRACT` — how it may use evidence.
3. The retrieved context block and the "already used" block.

Keeping these separate is what makes the type templates short and auditable:
a template only describes the *shape* of its content type, never the rules.
"""

from __future__ import annotations

from app.schemas.common import Difficulty, Sport

AGENT_IDENTITY = """\
You are the content engine behind a sports social-media studio. You write \
interactive Instagram content that makes fans stop scrolling and tap.

House style:
- Punchy and conversational. No emoji unless it earns its place.
- No preamble, no meta-commentary, no "did you know" filler.
- Sound like a knowledgeable fan, not a textbook."""


GROUNDING_CONTRACT = """\
EVIDENCE RULES (these override everything else):
- Every factual claim must be supported by the CONTEXT block below.
- Cite the handle(s) you relied on in `cited_refs` (e.g. ["W2"] or ["K1","K4"]).
  Use only handles that literally appear in the CONTEXT block. Never invent one.
- If the context does not firmly establish a fact, do not use that fact. Pick a
  different angle that the context does support.
- Distractor options must be plausible but definitively wrong. Never write a
  distractor that could also be argued correct.
- Prefer facts that are settled and checkable over ones that are contested.
- Set `confidence` to "high" only when the context states the fact outright;
  "medium" when it requires light inference; "low" otherwise. Never guess a
  number, date, or name that is absent from the context."""


OPINION_CONTRACT = """\
OPINION RULES:
- This format is deliberately opinion-based. There is NO correct answer and
  nothing here is fact-checked.
- Never imply one side is objectively right, and never include a verdict.
- Aim for a genuine 50/50 split: both options must have real support among fans.
  A lopsided matchup makes a dead poll.
- You may use the CONTEXT block for topical hooks (a recent result, a current
  form debate), but you are not making factual claims."""


DIFFICULTY_GUIDE: dict[Difficulty, str] = {
    Difficulty.EASY: (
        "EASY — a casual fan who watches finals should get this right immediately. "
        "Household names, headline achievements, iconic moments. No deep statistics."
    ),
    Difficulty.MEDIUM: (
        "MEDIUM — an engaged fan who follows the sport regularly gets this right; "
        "a casual viewer has to think. Specific finals, notable records, "
        "well-known career milestones."
    ),
    Difficulty.HARD: (
        "HARD — only a devoted follower or statistics buff gets this. Exact figures, "
        "less-celebrated records, precise dates, second-order details. Still fully "
        "verifiable from the context — hard, never obscure trivia for its own sake."
    ),
}


#: Instagram truncates sticker text. Asking for concise copy up front produces
#: far more usable output than trimming it afterwards.
LENGTH_GUIDANCE = """\
LENGTH (Instagram stickers truncate — respect these):
- Question / statement / prompt: aim for under 90 characters.
- Each answer option: aim for under 22 characters. Bare names and numbers,
  not sentences. "Sachin Tendulkar" not "It was Sachin Tendulkar".
- Explanation: one or two tight sentences, under 200 characters."""


def build_system_prompt(type_rules: str, *, factual: bool) -> str:
    """Compose a full system prompt for one content type."""
    contract = GROUNDING_CONTRACT if factual else OPINION_CONTRACT
    return "\n\n".join([AGENT_IDENTITY, contract, LENGTH_GUIDANCE, type_rules])


def render_context_block(context_text: str) -> str:
    """Wrap the retrieved evidence, or state plainly that there is none."""
    if not context_text.strip():
        return (
            "CONTEXT: (empty — no evidence was retrieved)\n"
            "Because there is no context, restrict yourself to bedrock facts about "
            "this sport that are beyond dispute, and set confidence to \"low\"."
        )
    return f"CONTEXT (your only permitted source of facts):\n{context_text.strip()}"


def render_avoid_block(recent: list[str]) -> str:
    """Tell the model what has already been used, to force fresh angles."""
    if not recent:
        return ""
    bullets = "\n".join(f"- {line}" for line in recent)
    return (
        "ALREADY USED — do not repeat these facts, answers, or near-paraphrases. "
        "Choose different subjects, records, and years:\n" + bullets
    )


def render_task_header(
    *,
    sport: Sport,
    difficulty: Difficulty | None,
    count: int,
    topic: str,
) -> str:
    """The per-request framing shared by every type template."""
    lines = [f"SPORT: {sport.value}"]
    if difficulty is not None:
        lines.append(f"DIFFICULTY: {DIFFICULTY_GUIDE[difficulty]}")
    if topic.strip():
        lines.append(f"FOCUS: center the content on {topic.strip()}.")
    noun = "item" if count == 1 else "items"
    lines.append(f"COUNT: produce exactly {count} {noun}.")
    lines.append(
        "VARIETY: each item must cover a different subject — different player, "
        "team, era, or record. Do not cluster around one storyline."
    )
    return "\n".join(lines)
