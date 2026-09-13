# HTTPS login session fix

The deployment pins Web commit `4e87efd9ad0c97ff590effb806475939fcf3f2ab`.

The credentials callback previously succeeded, but middleware checked only
`next-auth.session-token`. NextAuth uses a secure cookie name under HTTPS, so
Dashboard requests immediately redirected back to login. Middleware now uses
NextAuth's `getToken()` to validate the session and handle secure and chunked
cookies.

Validation:

- `npm run test:auth`: all 10 tests passed, using the real middleware and
  NextAuth implementation. The old implementation fails the regression cases.
- `npm run build`: passed, including TypeScript and lint checks. Existing
  React hook and image lint warnings remain outside this change.
- Isolated application test: registration, wrong-password rejection, successful
  credentials sign-in, session lookup, Dashboard and authenticated API passed.
- HTTPS release checks: valid and chunked sessions access Dashboard;
  missing, forged and expired sessions redirect to login.

The release preserved the existing application assets, authentication
configuration and database schema. No production user was created or modified
by verification. Future full builds from the pinned source include the fix.

Detailed operational evidence and recovery information are retained with the
release artifacts and are not included in this repository.
