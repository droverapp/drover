![the word 'drover' in pink letters. The o is a circle with an arrow extending to the top right](static/img/drover_full.png)
# Drover - Group communication for all the ways we get together
A project of [Kathleen Burnett](mailto:kathleen@droverapp.org)

Drover is an open source messaging and planning tool for groups of all kinds. The premise is simple. Group chats suck. Enterprise tools are too expensive. Drover is meant to help people get together in real life at events, meetings, clubs, trips, whatever, and put their phones away, knowing the information they need will be easy to find.

More information and newsletter signup is available at [www.droverapp.org](https://droverapp.org/)

[A hosted version can be seen here.](https://drover-c2b7334ee3ef.herokuapp.com/)

## Installation (to run locally)

- Ensure you have [uv](https://astral.sh/uv).
- Run `uv sync`
- Run `uv run python3 manage.py migrate`
- RUN `uv run python3 manage.py collectstatic`
- Run `uv run python3 manage.py runserver`
- Open http://localhost:8000

## Web Push notifications

Web Push is optional and remains disabled unless both VAPID keys are configured. The public key is used by the browser; the private key must stay in a secure environment setting. Generate one pair on a trusted machine and keep it stable across deployments so existing browser subscriptions remain valid:

```python
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02, b64urlencode

vapid = Vapid02()
vapid.generate_keys()
private_der = vapid.private_key.private_bytes(
    serialization.Encoding.DER,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
public_raw = vapid.public_key.public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint,
)
print("WEBPUSH_VAPID_PUBLIC_KEY=" + b64urlencode(public_raw))
print("WEBPUSH_VAPID_PRIVATE_KEY=" + b64urlencode(private_der))
```

Set both values in the deployment secret store or local `.env` (see `.env.example`); set `WEBPUSH_VAPID_SUBJECT` to a monitored `mailto:` address. The generator prints the private value—never commit it, log it, or share it. Keep the pair stable; replacing keys requires users to subscribe again. Push is sent for new group messages and replies, using only FCM and Apple Web Push endpoints.

On iOS/iPadOS, users must install Drover on the Home Screen and use version 16.4 or later; ordinary Safari tabs cannot receive Web Push. The [Apple Web Push guide](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers) and [pywebpush documentation](https://pypi.org/project/pywebpush/) describe the platform and server protocol details.

## Deploying

This release deletes and regenerates the entire migration history, so an
existing database cannot be upgraded in place. `manage.py migrate` runs in
Heroku's release phase (see `heroku.yml`) before a new release serves
traffic: against a pre-cutover database it aborts with a schema error,
Postgres rolls the failed migration back, and the previous release keeps
running with the old schema untouched. Plan the cutover explicitly — dump
anything you need (`heroku pg:dump`), then `heroku pg:reset DATABASE_URL`
and redeploy. Local databases created before the cutover need the same
treatment: `make db-reset`.

## Want to contribute?

Yes, please! I'm in the process of putting together a proper roadmap and issues tracker and the like, but help is definitely appreciated. Even if you can't contribute code but have ideas for features you'd like to see or problems you'd like solved, I'm all ears.

Have a bug or other problem you'd like me to take a look at? [You can share it here.](https://form.jotform.com/260016845821050)

For code contributions, quick bug fixes are fine via PR here. If you're interested in contributing more, such as adding a feature or helping to get this set up as a mobile app, please [reach out via email](mailto:kathleen@anywhere-league.com) to let me know what you'd like to do.

## Licences

Drover is under the GNU AGPLv3 license. 

If you like what we're doing and want to make it better, please help make it better for everyone.
