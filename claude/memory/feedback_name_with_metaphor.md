---
name: feedback_name_with_metaphor
description: When naming something that enters a shared namespace, offer evocative candidates alongside descriptive ones — a metaphor is the safer choice, not the indulgent one
metadata:
  type: feedback
---

Asked to name a new repository, I offered four role-descriptive candidates — `ingress`, `edge-ingress`,
`hostkit`, `frontdoor` — and was told to be more creative. The name chosen came from a building metaphor:
`landlord`, for a repo that maintains the common parts and holds the tenancy agreements.

**Why:** a vivid name is the *safer* choice, not the indulgent one, whenever the name enters a namespace
shared with software nobody controls — a `/opt` directory, a Docker network, a compose project prefix, a
package name. The failure mode there is two parties independently reaching for the same obvious category
word, and category words are exactly what everyone reaches for: `ingress` is also the name Docker Swarm
gives its own routing network, and `/opt` already contains `containerd` put there by a package. Nobody
accidentally picks a metaphor. The metaphor also keeps paying out as the design grows — tenants, common
parts, tenancy agreements, the doorman who checks the board rather than the visitor's word for who they are.

**How to apply:** when naming something destined for a shared namespace, offer evocative candidates
alongside the descriptive ones rather than only a list of role words, and check each candidate against what
the platform, a package, or a well-known project might already claim. Rule out a name that collides with an
adjacent tool even when the collision is only conceptual — a certificate manager sharing its name with a
repo that manages certificates would be confusing forever.

Related: [[feedback_codify_conventions_as_single_rules]].
