# Changelog

## [Unreleased]

### Messaging regression tests
- Added group-message integration tests verifying admin/member direction, active-member recipient targeting, inbox/conversation visibility, and non-member access denial with mocked Twilio delivery (`groups/tests.py`).
- Added invitation-email tests for existing-user membership and new-user invitation links using Django's locmem email backend.
- Added event-change and group-message reply tests covering field persistence, parent/receiver association, redirect targets, and participant-only conversation visibility.
- Removed tests that only exercised Django model basics and URL-reversal plumbing.

### Web Push notifications (opt-in)
- Added per-device Web Push subscriptions (`users.WebPushSubscription`) with authenticated, CSRF-protected register/revoke endpoints restricted to allowlisted push-service hosts (FCM for Android Chrome, Apple Push for iOS/iPadOS Home Screen apps).
- Added a root-scoped service worker (`static/service-worker.js`), web app manifest (`static/manifest.webmanifest`), and PWA icons, plus a dashboard control gated behind VAPID configuration.
- Added best-effort, bounded delivery to new group messages and replies via `users/push.py`, excluding the sender and removing expired subscriptions.
- Documented single-maintainer risk for `pywebpush` and the iOS/iPadOS 16.4+ Home Screen requirement.
- Manual Android/iOS device verification is pending hardware access; the feature is opt-in and disabled by default until VAPID keys are configured.