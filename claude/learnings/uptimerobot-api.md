# UptimeRobot through its API

Driving UptimeRobot (v2 API) to watch a set of hostnames for the right content, not only for a 200.

## Key and plan

- Monitors can only be created with the **Main API key** (Integrations & API → API). Read-only and
  per-monitor keys cannot write.
- The free plan is 50 monitors at a 5-minute interval, keyword monitors included, and UptimeRobot's own
  help page says it allows commercial use. Third-party comparison posts claim it is non-commercial only;
  the vendor's page is the one to believe.
- Validate the key with `getAccountDetails`; it also reports `monitor_limit` and `monitor_interval`.

## Creating a keyword monitor

Every call is a form-encoded `POST https://api.uptimerobot.com/v2/<method>` with `api_key` and
`format=json`. A monitor that fails when the page lacks a marker:

```
newMonitor  type=2  url=…  keyword_type=2  keyword_value=<marker>  interval=300  alert_contacts=<id>_0_0
```

- `type=2` is a keyword monitor; `type=1` is plain HTTP, which stays green whatever app answers.
- `keyword_type=2` means **alert when the keyword does NOT exist**. `1` is the opposite, alerting when it
  appears, and is the easy wrong choice.
- `alert_contacts` is `<contact id>_<threshold>_<recurrence>`; read the id from `getAlertContacts`. The
  sign-up address is created as a contact automatically.
- Encode the values (`curl --data-urlencode`, or `urllib.parse.urlencode`). A marker such as
  `What&#x27;s next` carries `&` and `#`, which an unencoded `-d` splits or truncates.

`getMonitors` reports `status`: `2` up, `9` down, `1` not checked yet, `0` paused. A new monitor runs its
first check within about a minute.

## Proving the alarm without breaking anything

Switch one monitor's `keyword_value` (`editMonitor`) to a string the app never emits. It goes `9` at its
next check and the DOWN mail follows; restore the value and the UP mail arrives one interval later. That
exercises monitor → contact → inbox end to end while production stays untouched.

## Things it will not do for you

Nothing keeps the monitors in step with the system they watch. Where a repo already records each
hostname's identity marker, the monitors are a hand-made copy of that list, and a new or renamed hostname
needs its monitor changed in the same piece of work.
