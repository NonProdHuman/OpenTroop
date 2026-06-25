from pydantic import BaseModel


class CalendarSubscriptionRead(BaseModel):
    """The caller's personal iCal subscription token and feed path.

    ``feed_path`` is relative; clients prepend the API origin (and may swap the
    scheme to ``webcal://``) to subscribe in Apple/Google Calendar.
    """

    token: str
    feed_path: str
