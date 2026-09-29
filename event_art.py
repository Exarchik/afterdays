"""Compatibility art lookup derived from the shared event catalog."""
from event_catalog import EVENTS
EVENT_ART={event['id']:event['art'] for event in EVENTS}
