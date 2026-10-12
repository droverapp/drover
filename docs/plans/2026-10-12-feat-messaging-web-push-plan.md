---
title: "feat: message delivery tests and opt-in Web Push"
type: plan
date: 2026-10-12
status: in_progress
confidence: medium
---

# Message delivery tests and opt-in Web Push

Add regression coverage for Drover's existing group-message flows, then add Web Push as an explicit, per-device opt-in channel for new group messages and replies. Keep SMS and email behavior separate; Web Push is progressive enhancement, not a replacement or a promise of support in every mobile browser.

## Problem Statement

`groups/tests.py` covers RSVP and event editing, but no tests exercise group-message creation, inbox/conversation visibility, email invitations, or outbound SMS. `send_message`, `message_details`, and `conversation_details` call Twilio from request handlers; `add_group_member` sends email. Tests for those paths must isolate the provider boundaries.

There is no web app manifest, service worker, push-subscription model or Web Push sender. The browser UI is Django templates with static JavaScript. The signup flow includes SMS consent; per user direction, this plan leaves that registration step unchanged and does not block message tests on a separate consent model.

## Target End State

- Tests prove message persistence, role-based delivery targeting, reply threading, event edits, inbox visibility and invitation-email behavior without real provider calls.
- Test coverage proceeds in order: group messages, invitations, then event changes and group-message replies.
- The user-confirmed registration SMS-consent flow remains unchanged; no separate consent model blocks this work.
- Users can enable and revoke Web Push per browser/device; unsupported or unconfigured clients continue using the existing app without errors.
- New group messages and replies can notify eligible push subscribers with a generic, privacy-preserving notification and a same-origin link.
- iOS support is accurately described as Home Screen web apps on iOS/iPadOS 16.4 or later; Android support is limited to browsers implementing Push API and Service Workers.

## Scope and Non-Goals

**In scope**
- Behavioral tests for group messages, invitations, event edits, group-message replies, inbox/conversation visibility, and the SMS/email integration boundaries.
- Explicit Web Push opt-in, per-user/per-device subscription storage, send handling for new group messages and replies, unsubscribe, and stale-subscription cleanup.
- Browser-level smoke checks on an HTTPS deployment and supported iOS/Android devices.

**Out of scope**
- Native iOS/Android apps, scheduled event reminders, RSVP notifications, a general offline-first PWA, replacing SMS/email, silent pushes, or notification-history UI.
- A new task queue or guaranteed/retried delivery system unless fan-out measurements show synchronous delivery is unsuitable.
- Changing the existing registration SMS-consent flow.


## Proposed Solution

### Existing messaging test slice

Use Django integration tests against the real routes and database. Mock the Twilio client or `groups.views.send_text_message`; use Django's locmem email backend for invitation paths. Execute the test work in this order: group messages, invitations, then event changes and group-message replies.

- An authorized admin's group message is stored as `AM`; an authorized member's is stored as `MA`; tests cover the active-member recipient matrix.
- Inbox/conversation queries expose the appropriate broadcast and participant messages to admins and members, not another member's private messages.
- Active membership is required to compose or read messages; deleted/non-members do not gain access.
- Invitation mail has the expected recipient, subject, invitation link or membership wording. No test reaches SendGrid or Twilio.
- Event edits persist the submitted event changes within their group; replies retain parent, sender and receiver and are visible only to conversation participants.
- Test SMS body/link formatting and credential-selection branches with a fake Twilio client. The existing registration consent flow is unchanged.

Do not test Django model basics, URL reversal, mock echoes, provider implementation details, or the current `GroupMessage.status` as a delivery receipt: the view currently leaves it pending after sending.


### Web Push slice

Use the standards-based Web Push API rather than a native push SDK. The page feature-detects Service Workers and `PushManager`; a user-initiated button requests permission and registers the subscription with an authenticated, CSRF-protected Django endpoint. Serve a root-scoped service worker so it can handle events across the site, and add a web manifest to the shared base template.

Store the opaque subscription endpoint and its encryption keys against the authenticated user, unique by endpoint, allowing multiple devices per user. Keep the VAPID private key in environment configuration; expose only the public key to the browser. Treat endpoints and keys as secrets: never place them in logs or client-visible pages. The service worker must display a notification for every push and open only a same-origin Drover URL when clicked. Use generic notification copy; do not put message text, phone numbers, or private conversation content on the lock screen.

On new group messages, target active members according to the existing admin/member direction; on replies, target the other conversation participant. Never notify the sender. Keep provider failures from rolling back an already-saved message, delete subscriptions rejected as expired/gone (for example, HTTP 404/410), and use bounded delivery timeouts. Use synchronous, best-effort delivery with bounded timeouts; Phase 0 checks group sizes and sends this work back to planning if that bound is not acceptable.

## Decision Rationale

- **Web Push, not a native push SDK:** Apple documents Web Push for Home Screen web apps on iOS/iPadOS 16.4+ and says no Apple Developer Program membership is required. The standard is shared across supporting browsers; it fits Drover's server-rendered web app without requiring an App Store release.
- **Progressive enhancement:** permission can be denied or unsupported, and iOS requires an installed Home Screen web app. Existing email/SMS and the web app must remain usable without push.
- **Per-device subscriptions:** Push subscriptions belong to a service-worker registration/device, not just an account. Users need a way to revoke one device without deleting their account.
- **Stage tests before delivery:** tests first reveal current routing/visibility behavior and isolate external effects; push delivery then reuses a verified recipient contract.
- **No silent or content-rich lock-screen pushes:** Apple requires visible notifications after receiving pushes; generic content also limits disclosure on shared/locked devices.

## Constraints and Boundaries

- Service Workers require a secure context (HTTPS in production; localhost is acceptable for development).
- Request notification permission only from a user gesture. iOS/iPadOS Web Push requires the user to add the web app to the Home Screen and run iOS/iPadOS 16.4 or later.
- Apple's Web Push guidance requires VAPID identification, encrypted payloads and a visible notification; the Push API subscription endpoint is a capability URL and must be kept secret.
- Existing notifications run synchronously in request handlers; there is no Celery/RQ-style background worker in the repository. Do not add a queue without evidence that the group fan-out or latency requires it.
- The UI remains server-rendered Django templates with static JavaScript; no frontend build/test harness was found.
- Keep the user-confirmed SMS-consent step in registration unchanged; no separate SMS consent change is in this scope.


## Assumptions

| Assumption | Status | Evidence |
|---|---|---|
| Existing SMS consent is handled during registration and remains unchanged. | Confirmed by user | User direction for this plan; this work does not add a separate consent model or gate tests on it. |
| Initial Web Push triggers are new group messages and replies; invitations and event changes are test-only in this plan. | Confirmed in this exchange | User selected messages/replies as the first push scope; later requested the test sequence for invitations and event changes. |
| iOS support means installed Home Screen web apps on iOS/iPadOS 16.4+. | Verified | [Apple Web Push documentation](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers). |
| Android support means a browser with Push API and Service Worker support, initially Android Chrome. | Verified for standards path; exact support matrix needs device QA | [Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), [web.dev subscription guide](https://web.dev/articles/push-notifications-subscribing-a-user). |
| Current small-group traffic can tolerate synchronous push fan-out. | Unverified | No group-size or provider-latency data found. Confirm before selecting this delivery path. |
| A maintained Python Web Push library is available for the project's Python/Django versions. | Unverified; implementation task | Select and verify a maintained library before adding a dependency; avoid hand-writing encryption/protocol code. |


## Risk Analysis

| Risk | Mitigation |
|---|---|
| iOS users expect notifications from an ordinary Safari tab. | Explain Home Screen installation and OS minimum in the opt-in UI; make unsupported states explicit and keep the site functional. |
| Permission prompts are denied if shown unexpectedly. | Do not prompt on page load; request permission only after a clear user action explaining the benefit. |
| Subscription endpoints or VAPID keys leak. | Store endpoint/keys server-side, protect registration/unsubscribe with login and CSRF, never log subscription secrets, and keep VAPID private key in environment secrets. |
| Notification leaks private message content on a locked device. | Send generic text plus a same-origin target; fetch message content only after the user opens Drover. |
| Push send failure turns a successful message into a failed request, or one dead subscription blocks all recipients. | Make push best-effort after message persistence; isolate per-subscription failures and remove expired endpoints. Use bounded timeouts. |
| Synchronous fan-out increases request latency for large groups. | Verify group sizes in Phase 0; if synchronous delivery is not bounded, plan a durable queue/outbox separately before rollout. |
| User has multiple devices and receives duplicates. | Store one subscription per endpoint, support per-device unsubscribe, and test distinct endpoints; do not collapse all devices to one row per user. |


## Phased Implementation

### Phase 0 — Confirm push delivery constraints
- [ ] Confirm representative group sizes and verify bounded synchronous delivery is appropriate; add a separate queue/outbox design only if it is not.
- [ ] Keep the user-confirmed registration SMS-consent flow unchanged; it is not a blocker or a consent-model work item in this plan.
- **Exit:** initial Web Push triggers are group messages and replies; provider calls are bounded and best-effort.

### Phase 1 — Group-message tests
- [x] Add route-level tests for authorized admin/member message creation, persisted direction/content, and role-based recipient selection.
- [x] Add inbox/conversation audience tests for admins, members, and non-members.
- [x] Test SMS body/link formatting and credential-selection branches with a fake Twilio client.
- **Exit:** group-message creation and visibility behavior pass without live Twilio requests.

### Phase 2 — Invitation tests
- [ ] Add admin-only invitation tests for existing users and new users, including resulting membership and invitation-link email content.
- [ ] Use Django's locmem email backend; no test reaches SendGrid.
- **Exit:** both invitation outcomes and their access boundary are covered.

### Phase 3 — Event changes and group-message replies
- [ ] Add event create/update behavior tests for changed fields and events scoped to their owning group.
- [ ] Add reply tests for parent/receiver association, redirect target, and participant-only conversation visibility.
- **Exit:** event edits and threaded replies have behavioral coverage; neither adds a Web Push trigger in this initial delivery scope.

### Phase 4 — Add Web Push subscription lifecycle
- [ ] Select a maintained Python Web Push library; verify Python compatibility, VAPID support, timeout/error behavior, and dependency maintenance.
- [ ] Add environment-backed VAPID keys and deployment documentation; never commit private keys.
- [ ] Add a root-scoped service worker, web manifest, feature detection, and an explicit enable/disable control.
- [ ] Add authenticated, CSRF-protected registration and revocation endpoints and a per-endpoint subscription model.
- [ ] Add tests for registration ownership, multiple devices, revoke behavior, and unsupported/denied permission states where browser automation permits.
- **Exit:** a logged-in user can subscribe and revoke a device; unconfigured clients still use Drover normally.

### Phase 5 — Deliver and verify message pushes
- [ ] Add a push sender service with minimal payload, same-origin click targets, bounded network calls, per-endpoint failure handling, and stale-subscription cleanup.
- [ ] Integrate it with group-message and reply recipient rules; exclude the sender.
- [ ] Test target selection, no send without a subscription, expired endpoints, provider failure isolation, and message persistence independent of push success.
- [ ] Manually verify permission/subscription, background display, unsubscribe, and click-through on Android Chrome and an iOS/iPadOS 16.4+ Home Screen web app over HTTPS.
- **Exit:** Android Chrome and supported iOS Home Screen flows pass; unsupported or denied clients retain normal message/email/SMS behavior.


## Acceptance Criteria

- Group-message tests land first and use fake Twilio delivery; they verify message persistence and admin/member audience rules without network calls.
- Invitation tests follow, use Django's locmem email backend, and cover existing-user membership mail and new-user invitation links.
- Event-edit tests and group-message reply tests follow invitations; they verify persisted event changes, reply parent/receiver association, and conversation visibility.
- Tests do not call Twilio or SendGrid, and do not treat `GroupMessage.status` as a delivery receipt.
- Web Push is opt-in per device; registration/revocation is user-owned, and push targets only approved message/reply recipients with active subscriptions, excluding the sender.
- Push payloads contain no private message body or phone number; click-through is same-origin.
- Expired subscriptions are removed; an individual transient push failure neither rolls back the saved message nor stops attempts to other subscriptions.
- Permission is requested only after explicit user action; unsupported browsers, denied permission, missing VAPID configuration, or no subscription do not break normal Drover flows.
- Manual device verification documents Android Chrome and iOS/iPadOS Home Screen support limits; the UI does not claim support for ordinary iOS Safari tabs.


## Subjective Contract and Preview Gate

- **Target outcome:** a user understands why push is offered, what will appear on their lock screen, how iOS installation affects support, and how to turn it off.
- **Anti-goals:** surprise permission prompts, silent pushes, message content on lock screens, duplicate registration rows for one device, or implying push is guaranteed delivery.
- **References:** native opt-in control should follow Drover's existing account/group forms; platform restrictions must follow the linked Apple and web.dev guidance.
- **Anti-references:** automatic first-visit prompts and sensitive content in notification banners.
- **Tone/taste:** short, plain-language consent copy; state unsupported iOS installation requirements before showing the system prompt.
- **Representative proof slice:** one group message to one opted-in Android Chrome subscription, with mocked sender tests and a visible user-controlled subscribe/revoke setting.
- **Preview artifact:** before implementing subscription UI, provide a static/template preview of the enable, enabled, disabled, and iOS Home Screen-required states for review.
- **Rollout rule:** enable only when VAPID configuration exists; keep the feature opt-in and preserve all existing flows when disabled.
- **Rejection criteria:** permission prompt on page load, silent push, private message text in payload, or push errors blocking message creation.

## References

- Repository: `groups/views.py` (`send_message`, `message_details`, `conversation_details`, `inbox`, `conversations`); `groups/models.py` (`GroupMessage`, `GroupMessageImage`); `groups/sms.py`; `groups/emails.py`; `users/forms.py`; `users/models.py`; `users/templates/signup.html`; `drover/settings.py`.
- [Apple: Sending web push notifications in web apps and browsers](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [MDN: Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [web.dev: Subscribe a user to push notifications](https://web.dev/articles/push-notifications-subscribing-a-user)
- [RFC 8030: Generic Event Delivery Using HTTP Push](https://datatracker.ietf.org/doc/html/rfc8030)
