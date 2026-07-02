from pydantic import BaseModel


class CalendarSubscriptionRead(BaseModel):
    """The caller's personal iCal subscription state.

    The raw token is **shown once**: only the hash is stored server-side (GH-114), so
    ``token`` / ``feed_path`` are populated only in the response that minted or rotated
    the token. On subsequent calls ``active`` is true and both are null — the client
    must have saved the URL, or rotate to get a new one.

    ``feed_path`` is relative; clients prepend the API origin (and may swap the
    scheme to ``webcal://``) to subscribe in Apple/Google Calendar.
    """

    active: bool
    token: str | None = None
    feed_path: str | None = None
