import uuid
from typing import List

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from hknweb.events.google_calendar_utils import SHARE_LINK_TEMPLATE, get_calendar_link
from hknweb.events.models import Event, EventType, GCalAccessLevelMapping, ICalView
from hknweb.events.models.constants import ACCESS_LEVELS
from hknweb.events.utils import get_events
from hknweb.models import Profile
from hknweb.utils import allow_public_access, get_access_level


@allow_public_access
def index(request):
    event_type_types = request.GET.get("event_types", None)
    if event_type_types:
        event_type_types = event_type_types.split(",")

    rsvpd_display = request.GET.get("rsvpd", "show") != "hide"
    not_rsvpd_display = request.GET.get("not_rsvpd", "show") != "hide"

    return calendar_helper(
        request,
        "Events",
        event_type_types=event_type_types,
        rsvpd_display=rsvpd_display,
        not_rsvpd_display=not_rsvpd_display,
        show_sidebar=True,
    )


@allow_public_access
def ical(request, *, id: uuid.UUID):
    ical_view = get_object_or_404(ICalView, pk=id)
    return HttpResponse(ical_view.to_ical_obj().to_ical(), content_type="text/calendar")


def calendar_helper(
    request,
    title,
    event_type_types: List[str] = None,
    rsvpd_display=True,
    not_rsvpd_display=True,
    show_sidebar=False,
):
    user_access_level = get_access_level(request.user)
    events = get_events(request.user, rsvpd_display, not_rsvpd_display)

    all_event_types = event_types = EventType.objects.order_by("type")
    if event_type_types:
        events = events.filter(event_type__type__in=event_type_types)
        event_types = all_event_types.filter(type__in=event_type_types)

    context = {
        "events": events,
        "title": title,
        "event_types": event_types,
        "all_event_types": all_event_types,
        "calendars": get_calendars(request, user_access_level),
        "show_sidebar": show_sidebar and request.user.is_authenticated,
    }
    return render(request, "events/index.html", context)


def get_calendars(request, user_access_level: int):
    calendars = []
    for access_level, name in ACCESS_LEVELS:
        if user_access_level > access_level:
            continue

        calendar_id = GCalAccessLevelMapping.get_calendar_id(access_level)  # Link
        if not calendar_id:
            continue

        calendars.append(
            {
                "name": name,
                "link": get_calendar_link(calendar_id=calendar_id),
            }
        )

    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()
        if profile.google_calendar_id:
            calendars.append(
                {
                    "name": "personal (gcal)",
                    "link": get_calendar_link(calendar_id=profile.google_calendar_id),
                }
            )

        ical_view, _ = ICalView.objects.get_or_create(user=request.user)
        ical_url = request.build_absolute_uri(ical_view.url)
        ical_url = ical_url.replace("https://", "webcal://")
        calendars.append(
            {
                "name": "personal (ics)",
                "link": SHARE_LINK_TEMPLATE.format(cid=ical_url),
            }
        )

    for calendar in calendars[:-1]:
        calendar["separator"] = "/"
    if len(calendars) > 0:
        calendars[-1]["separator"] = ""

    return calendars
