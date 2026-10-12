---
title: "feat: message delivery tests and opt-in Web Push"
type: plan
date: 2026-10-12
status: approved
confidence: medium
---

# Message delivery tests and opt-in Web Push

Add regression coverage for Drover's existing group-message flows, then add Web Push as an explicit, per-device opt-in channel for new group messages and replies. Keep SMS and email behavior separate; Web Push is progressive enhancement, not a replacement or a promise of support in every mobile browser.

## Problem Statement

`groups/tests.py` covers RSVP and event editing, but no tests exercise group-message creation, inbox/conversation visibility, email invitations, or outbound SMS. `send_message`, `message_details`, and `conversation_details` call Twilio from request handlers; `add_group_member` sends email. Tests for those paths must isolate the provider boundaries.

There is no web app manifest, service worker, push-subscription model or Web Push sender. The browser UI is Django templates with static JavaScript. A signup template displays a Twilio-consent checkbox, but `SignUpForm` does not include it and `User` has no SMS-consent field; message delivery does not check consent. Do not write tests that endorse the current SMS recipient policy until that policy is confirmed.

## Target End State

- Tests prove message persistence, role-based delivery targeting, reply threading, inbox visibility and invitation-email behavior without real provider calls.
- SMS recipient eligibility has an explicit, persisted consent rule before tests pin its audience.
- Users can enable and revoke Web Push per browser/device; unsupported or unconfigured clients continue using the existing app without errors.
- New group messages and replies can notify eligible push subscribers with a generic, privacy-preserving notification and a same-origin link.
- iOS support is accurately described as Home Screen web apps on iOS/iPadOS 16.4 or later; Android support is limited to browsers implementing Push API and Service Workers.

## Scope and Non-Goals

**In scope**
- Behavioral tests for the existing group-message, reply, inbox, conversation, invitation-email, and SMS integration boundaries.
- Explicit Web Push opt-in, per-user/per-device subscription storage, send handling for new group messages and replies, unsubscribe, and stale-subscription cleanup.
- Browser-level smoke checks on an HTTPS deployment and supported iOS/Android devices.

**Out of scope**
- Native iOS/Android apps, scheduled event reminders, RSVP notifications, a general offline-first PWA, replacing SMS/email, silent pushes, or notification-history UI.
- A new task queue or guaranteed/retried delivery system unless fan-out measurements show synchronous delivery is unsuitable.
- Expanding or changing SMS consent policy without resolving the consent gap in Phase 0.

## Proposed Solution

### Existing messaging test slice

Use Django integration tests against the real routes and database. Mock the Twilio client or `groups.views.send_text_message`; use Django's locmem email backend for invitation paths. Cover observable outcomes:

- An authorized admin's group message is stored as `AM`; an authorized member's is stored as `MA`.
- Replies retain the parent message, group, sender and intended receiver; the HTTP flow redirects to the expected conversation.
- Inbox/conversation queries expose the appropriate broadcast and participant messages to admins and members, not another member's private messages.
- Active membership is required to compose or read messages; deleted/non-members do not gain access.
- Invitation mail has the expected recipient, subject, invitation link or membership wording. No test reaches SendGrid or Twilio.
- Test SMS body/link formatting and credential-selection branches with a fake Twilio client. Test recipient selection only after the consent contract is decided.

Do not test Django model basics, URL reversal, mock echoes, provider implementation details, or the current `GroupMessage.status` as a delivery receipt: the view currently leaves it pending after sending.

### Web Push slice

Use the standards-based Web Push API rather than a native push SDK. The page feature-detects Service Workers and `PushManager`; a user-initiated button requests permission and registers the subscription with an authenticated, CSRF-protected Django endpoint. Serve a root-scoped service worker so it can handle events across the site, and add a web manifest to the shared base template.

Store the opaque subscription endpoint and its encryption keys against the authenticated user, unique by endpoint, allowing multiple devices per user. Keep the VAPID private key in environment configuration; expose only the public key to the browser. Treat endpoints and keys as secrets: never place them in logs or client-visible pages. The service worker must display a notification for every push and open only a same-origin Drover URL when clicked. Use generic notification copy; do not put message text, phone numbers, or private conversation content on the lock screen.

On new group messages, target active members according to the existing admin/member direction; on replies, target the other conversation participant. Never notify the sender. Keep provider failures from rolling back an already-saved message, delete subscriptions rejected as expired/gone (for example, HTTP 404/410), and use bounded delivery timeouts. Start with synchronous, best-effort delivery only if Phase 0 confirms expected group sizes are small; otherwise add a durable asynchronous delivery mechanism as a separate design decision rather than allowing request time to grow with unbounded fan-out.

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
- SMS opt-in is not currently persisted. Treat any assumption that all group members may receive SMS as unverified and do not expand SMS delivery until consent behavior is agreed and enforced.

## Assumptions

| Assumption | Status | Evidence |
|---|---|---|
| Web Push is additive to SMS/email and only for new group messages/replies initially. | Unverified; conservative plan choice | No product policy for push triggers exists in the repo. Confirm before implementation. |
| Push opt-in is separate from SMS consent. | Verified platform boundary | Browser push requires its own permission/subscription flow; the SMS checkbox is not stored in the user model or signup form. |
| iOS support means installed Home Screen web apps on iOS/iPadOS 16.4+. | Verified | [Apple Web Push documentation](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers). |
| Android support means a browser with Push API and Service Worker support, initially Android Chrome. | Verified for standards path; exact support matrix needs device QA | [Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), [web.dev subscription guide](https://web.dev/articles/push-notifications-subscribing-a-user). |
| Current small-group traffic can tolerate synchronous push fan-out. | Unverified | No group-size or provider-latency data found. Confirm before selecting this delivery path. |
| A maintained Python Web Push library is available for the project's Python/Django versions. | Unverified; implementation task | Select and verify a maintained library before adding a dependency; avoid hand-writing encryption/protocol code. |

## Risk Analysis

| Risk | Mitigation |
|---|---|
| SMS consent UI is not persisted or enforced; recipient tests could legitimize non-consensual delivery. | Resolve consent policy and storage/enforcement before adding assertions about SMS eligibility. Keep SMS and Web Push consent separate. |
| iOS users expect notifications from an ordinary Safari tab. | Explain Home Screen installation and OS minimum in the opt-in UI; make unsupported states explicit and keep the site functional. |
| Permission prompts are denied if shown unexpectedly. | Do not prompt on page load; request permission only after a clear user action explaining the benefit. |
| Subscription endpoints or VAPID keys leak. | Store endpoint/keys server-side, protect registration/unsubscribe with login and CSRF, never log subscription secrets, and keep VAPID private key in environment secrets. |
| Notification leaks private message content on a locked device. | Send generic text plus a same-origin target; fetch message content only after the user opens Drover. |
| Push send failure turns a successful message into a failed request, or one dead subscription blocks all recipients. | Make push best-effort after message persistence; isolate per-subscription failures and remove expired endpoints. Use bounded timeouts. |
| Synchronous fan-out increases request latency for large groups. | Verify group sizes in Phase 0; if synchronous delivery is not bounded, plan a durable queue/outbox separately before rollout. |
| User has multiple devices and receives duplicates. | Store one subscription per endpoint, support per-device unsubscribe, and test distinct endpoints; do not collapse all devices to one row per user. |

## Phased Implementation

### Phase 0 — Confirm delivery contracts
- [ ] Confirm message/reply notification triggers and whether push supplements existing channels.
- [ ] Decide the SMS consent policy. If SMS requires consent, add persisted opt-in and enforce it at recipient selection before writing tests that treat a recipient as eligible.
- [ ] Check representative group sizes and choose bounded synchronous delivery or a separately scoped durable queue.
- **Exit:** recipient rules, consent boundaries and the latency approach are explicit.

### Phase 1 — Cover existing messaging behavior
- [ ] Add route-level tests for authorized admin/member message creation and persisted message direction/content.
- [ ] Add reply tests for parent/receiver association and conversation visibility.
- [ ] Add inbox/conversation audience tests for admins, members, and non-members.
- [ ] Add invitation email tests with the locmem backend and SMS helper tests with a fake Twilio client.
- [ ] After Phase 0, add recipient-matrix tests for active members and persisted SMS consent.
- **Exit:** all external calls are mocked; the suite proves user-visible message/thread/access behavior and the decided notification audience.

### Phase 2 — Add Web Push subscription lifecycle
- [ ] Select a maintained Python Web Push library; verify Python compatibility, VAPID support, timeout/error behavior, and dependency maintenance.
- [ ] Add environment-backed VAPID keys and deployment documentation; never commit private keys.
- [ ] Add a root-scoped service worker, web manifest, feature detection, and an explicit enable/disable control.
- [ ] Add authenticated, CSRF-protected registration and revocation endpoints and a per-endpoint subscription model.
- [ ] Add tests for registration ownership, multiple devices, revoke behavior, and unsupported/denied permission states where browser automation permits.
- **Exit:** a logged-in user can subscribe and revoke a device without changing SMS settings; unconfigured clients still use Drover normally.

### Phase 3 — Deliver and verify message pushes
- [ ] Add a push sender service with minimal payload, same-origin click targets, bounded network calls, per-endpoint failure handling, and stale-subscription cleanup.
- [ ] Integrate it with the Phase 0-approved message and reply recipient rules; exclude the sender.
- [ ] Add tests for target selection, no send without a subscription, expired endpoints, provider failure isolation, and successful message persistence independent of push success.
- [ ] Manually verify permission/subscription, background display, unsubscribe, and click-through on Android Chrome and an iOS/iPadOS 16.4+ Home Screen web app over HTTPS.
- **Exit:** Android Chrome and supported iOS Home Screen flows pass; unsupported or denied clients retain normal message/email/SMS behavior.

## Acceptance Criteria

- The existing messaging tests cover create/reply/visibility/invitation paths without making real Twilio or SendGrid requests.
- Tests for notification recipients assert the Phase 0-approved rules; no test treats an unpersisted signup checkbox as consent.
- An authenticated user can store and revoke multiple device subscriptions; an unauthenticated user cannot register or revoke another user's subscription.
- A push is sent only to approved recipients with active subscriptions, excludes the sender, and contains no private message body or phone number.
- An expired subscription is removed; a transient push failure does not delete the already-saved group message or block delivery attempts to other subscriptions.
- Push permission is requested only after explicit user action; an unsupported browser, denied permission, missing VAPID configuration, or no subscription does not break the regular app.
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
