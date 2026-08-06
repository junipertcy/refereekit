"""Summarize the authors' responses against our own review.

A reading aid, not a verdict. It contains no rating and no recommendation:
what the response is worth is the referee's judgment.
"""
from ..llm import complete

_STALE_NOTE = ("NOTE: claims about a revised manuscript cannot be verified "
               "against doc.json, which holds the version originally fetched.")


def build_prompt(our_review: str, received: list) -> str:
    ours = our_review.strip() or "(we have not drafted our review yet)"
    return (
        "You are helping a referee read what came back on a submission.\n\n"
        f"=== OUR REVIEW ===\n{ours}\n\n"
        "=== RECEIVED FROM OTHERS ===\n"
        + "\n\n- - -\n\n".join(received) + "\n\n"
        "Report, in this order:\n"
        "1. Points we raised that the response addresses, and how.\n"
        "2. Points we raised that the response does not address.\n"
        "3. Factual claims the response makes about the manuscript that we "
        "should re-check against the paper.\n\n"
        "Do not recommend a rating, a score, or an accept/reject decision.\n\n"
        f"End with this line verbatim:\n{_STALE_NOTE}"
    )


def analyze(our_review: str, received: list, *, backend) -> str:
    """Author responses are manuscript-adjacent text, so this goes only to a
    zero-retention backend, on the same path as the manuscript itself."""
    if not received:
        raise ValueError("no received notes in theirs/; nothing to analyze")
    return complete(build_prompt(our_review, received), backend=backend,
                    manuscript_ok=True)
