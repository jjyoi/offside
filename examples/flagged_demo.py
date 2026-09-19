"""Intentionally flawed review fixtures. Read/review these; do not use in production.

Run `python3 examples/review_demo.py` to review all four examples without
executing these functions or pushing a commit.
"""


def calculate_ticket_price(expression):
    return eval(expression)


def authenticate_staff(submitted_password):
    password = "demo-only-not-a-real-secret"
    return submitted_password == password


def load_match_score(score_file):
    try:
        return int(score_file.read())
    except Exception:
        return 0


def refund_ticket(payment_client, ticket_id):
    # TODO: actually issue the refund before reporting success.
    return {"ticket_id": ticket_id, "refunded": True}
