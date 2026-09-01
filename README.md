<p align="center">
  <img src="assets/logo.png" width="140" alt="LINQ Connect Menus logo">
</p>

# LINQ Connect Menus for Home Assistant

School breakfast/lunch menus from [LINQ Connect](https://linqconnect.com)
as native Home Assistant calendars and sensors. No account required — uses
the same public API as your district's shared menu link.

## What you get

- One **calendar** per school: an all-day event per school day, entrées in
  the title, the full categorized menu in the description.
- One **sensor** per school per serving session (default: Lunch) with
  today's entrées as its state and the full menu as attributes — handy for
  dashboards and TTS ("what's for lunch today?").
- A **"Next" sensor** per school per serving session that always shows the
  next upcoming menu: today's until a rollover time (default 1:00 PM,
  configurable via **Configure**), then the next school day's — so Friday
  afternoon and all weekend it shows Monday. Attributes include the date
  and a friendly `day` label (`Today` / `Tomorrow` / weekday name).

## Installation

1. Add this repository to HACS as a custom repository (type: Integration),
   then install **LINQ Connect Menus** and restart Home Assistant.
2. Settings → Devices & Services → Add Integration → **LINQ Connect Menus**.
3. Enter the share code from your district's public menu link
   (`https://linqconnect.com/public/menu/<CODE>`) — or search by district
   name — then pick your schools and serving sessions.

Each district is one config entry; add the integration again for a second
district. Change schools/sessions later via the entry's **Configure** button.

## Notes

- Menus refresh every 6 hours, fetching Monday of the current week through
  six weeks out. Days without a published menu produce no events.
- Not affiliated with LINQ. The API is undocumented and could change.
