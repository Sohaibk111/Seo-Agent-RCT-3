import {
  app,
  users,
  userSessions,
  passwordHistories,
  usedRefreshTokens,
  securityEvents,
  validatePasswordStrength,
  calculateProgressiveDelay,
  parseDeviceInfo,
  checkAccountLockout,
  recordLoginFailure,
  recordLoginSuccess,
  checkPasswordHistory,
  hashPassword,
  verifyPassword
} from '../server';
import http from 'http';
import assert from 'assert';

let server: http.Server;
let baseUrl: string;

async function startTestServer(): Promise<string> {
  return new Promise((resolve) => {
    process.env.NODE_ENV = 'test';
    server = app.listen(0, '127.0.0.1', () => {
      const address = server.address() as any;
      const url = `http://127.0.0.1:${address.port}`;
      resolve(url);
    });
  });
}

function stopTestServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => resolve());
    } else {
      resolve();
    }
  });
}

async function runTests() {
  console.log('🔒 Starting Authentication Security Hardening Test Suite...\n');
  baseUrl = await startTestServer();
  let passedCount = 0;
  let failedCount = 0;

  async function test(name: string, fn: () => Promise<void>) {
    try {
      await fn();
      console.log(`  ✓ PASSED: ${name}`);
      passedCount++;
    } catch (err: any) {
      console.error(`  ✗ FAILED: ${name}`);
      console.error(`    Error: ${err.message}`);
      failedCount++;
    }
  }

  // --- UNIT TESTS ---
  console.log('\n--- 1. Password Strength Validation Tests ---');
  await test('Rejects password shorter than 8 chars', async () => {
    const res = validatePasswordStrength('Short1!');
    assert.strictEqual(res.valid, false);
    assert(res.errors.some(e => e.includes('at least 8 characters')));
  });

  await test('Rejects password missing uppercase', async () => {
    const res = validatePasswordStrength('nouppercase123!');
    assert.strictEqual(res.valid, false);
    assert(res.errors.some(e => e.includes('uppercase')));
  });

  await test('Rejects password missing lowercase', async () => {
    const res = validatePasswordStrength('NOLOWERCASE123!');
    assert.strictEqual(res.valid, false);
    assert(res.errors.some(e => e.includes('lowercase')));
  });

  await test('Rejects password missing digits', async () => {
    const res = validatePasswordStrength('NoDigitsInThisPass!');
    assert.strictEqual(res.valid, false);
    assert(res.errors.some(e => e.includes('numeric digit')));
  });

  await test('Rejects password missing special chars', async () => {
    const res = validatePasswordStrength('NoSpecialChars123');
    assert.strictEqual(res.valid, false);
    assert(res.errors.some(e => e.includes('special character')));
  });

  await test('Rejects common dictionary passwords', async () => {
    const res = validatePasswordStrength('password');
    assert.strictEqual(res.valid, false);
  });

  await test('Accepts strong password meeting all criteria', async () => {
    const res = validatePasswordStrength('SecureEnterprise#2026!');
    assert.strictEqual(res.valid, true);
    assert.strictEqual(res.errors.length, 0);
  });

  console.log('\n--- 2. Progressive Login Delay & Device Parser Tests ---');
  await test('Calculates progressive delay backoff correctly', async () => {
    assert.strictEqual(calculateProgressiveDelay(0), 0);
    assert.strictEqual(calculateProgressiveDelay(1), 0);
    assert.strictEqual(calculateProgressiveDelay(2), 200);
    assert.strictEqual(calculateProgressiveDelay(3), 500);
    assert.strictEqual(calculateProgressiveDelay(4), 1000);
    assert.strictEqual(calculateProgressiveDelay(5), 2000);
  });

  await test('Parses device information accurately from user agents', async () => {
    const iphone = parseDeviceInfo('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1');
    assert.strictEqual(iphone.deviceType, 'mobile');
    assert(iphone.deviceName.includes('Safari'));

    const chromeMac = parseDeviceInfo('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36');
    assert.strictEqual(chromeMac.deviceType, 'desktop');
    assert(chromeMac.deviceName.includes('Chrome'));

    const curl = parseDeviceInfo('curl/8.1.2');
    assert.strictEqual(curl.deviceType, 'api');
  });

  // --- INTEGRATION TESTS ---
  console.log('\n--- 3. Registration, Email Verification & Sensitive Action Enforcement ---');
  let newUserId: number;
  let userAccessToken: string;
  let userRefreshToken: string;
  let userVerToken: string;

  await test('Registration enforces password complexity', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        username: 'sec_analyst',
        password: 'weak'
      })
    });
    assert.strictEqual(res.status, 400);
    const body = await res.json();
    assert(body.detail.includes('at least 8 characters'));
  });

  await test('Registration succeeds with strong credentials and issues verification token', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0'
      },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        username: 'sec_analyst',
        password: 'StrictPassword2026!#',
        remember_me: true
      })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.is_verified, false);
    assert(body.access_token);
    assert(body.refresh_token);
    assert(body.verification_token);

    newUserId = body.id;
    userAccessToken = body.access_token;
    userRefreshToken = body.refresh_token;
    userVerToken = body.verification_token;
  });

  await test('Unverified user is forbidden from creating API keys (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/api-keys`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userAccessToken}`
      },
      body: JSON.stringify({ name: 'Prod API Key' })
    });
    assert.strictEqual(res.status, 403);
    const body = await res.json();
    assert(body.detail.includes('Email verification is required'));
  });

  await test('Email verification confirm activates account', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/verify-email/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: userVerToken })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.is_verified, true);
  });

  await test('Verified user can now create API keys', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/api-keys`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userAccessToken}`
      },
      body: JSON.stringify({ name: 'Prod API Key' })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.api_key.startsWith('sk_live_'));
  });

  console.log('\n--- 4. Refresh Token Rotation & Reuse Detection (Breach Containment) ---');
  let rotatedRefreshToken: string;
  let rotatedAccessToken: string;

  await test('Refresh endpoint rotates token and invalidates previous refresh token', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: userRefreshToken })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.access_token);
    assert(body.refresh_token);
    assert.notStrictEqual(body.refresh_token, userRefreshToken);

    rotatedAccessToken = body.access_token;
    rotatedRefreshToken = body.refresh_token;
  });

  await test('Attempting to replay used refresh token triggers reuse detection & revokes all sessions', async () => {
    // Attacker or replay of the old token
    const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: userRefreshToken })
    });
    assert.strictEqual(res.status, 401);
    const body = await res.json();
    assert(body.detail.includes('Suspicious token activity detected'));

    // Check that active sessions for this user were revoked
    const activeSessions = userSessions.filter(s => s.user_id === newUserId && s.is_active);
    assert.strictEqual(activeSessions.length, 0);
  });

  console.log('\n--- 5. Password History Enforcement & Change Password ---');
  let newLoginToken: string;

  await test('User logs in again after session revocation', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
      },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        password: 'StrictPassword2026!#'
      })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.access_token);
    assert.strictEqual(body.is_verified, true);
    assert(body.last_login_at);
    newLoginToken = body.access_token;
  });

  await test('Cannot change password to previous password (history rejection)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/change-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${newLoginToken}`
      },
      body: JSON.stringify({
        current_password: 'StrictPassword2026!#',
        new_password: 'StrictPassword2026!#'
      })
    });
    assert.strictEqual(res.status, 400);
    const body = await res.json();
    assert(body.detail.includes('Cannot reuse any of your last 5 passwords'));
  });

  await test('Changing password to a new distinct strong password succeeds', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/change-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${newLoginToken}`
      },
      body: JSON.stringify({
        current_password: 'StrictPassword2026!#',
        new_password: 'BrandNewSecPass2026$!'
      })
    });
    assert.strictEqual(res.status, 200);
  });

  console.log('\n--- 6. Account Lockout & Brute-force Protection ---');
  await test('Consecutive failed login attempts track remaining attempts and lock account on 5th failure', async () => {
    // 4 failed attempts
    for (let i = 1; i <= 4; i++) {
      const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'security.analyst@example.com',
          password: 'IncorrectPassword123!'
        })
      });
      assert.strictEqual(res.status, 401);
      const body = await res.json();
      assert(body.detail.includes('attempts remaining before lockout'));
    }

    // 5th failed attempt triggers HTTP 423 Locked
    const lockRes = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        password: 'IncorrectPassword123!'
      })
    });
    assert.strictEqual(lockRes.status, 423);
    const lockBody = await lockRes.json();
    assert(lockBody.detail.includes('Account is now locked'));

    // Even with the correct new password, locked account remains inaccessible until lockout expires
    const correctLockedRes = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        password: 'BrandNewSecPass2026$!'
      })
    });
    assert.strictEqual(correctLockedRes.status, 423);
    const correctBody = await correctLockedRes.json();
    assert(correctBody.detail.includes('temporarily locked'));
  });

  console.log('\n--- 7. Device Tracking & Session Management ---');
  // Unlock user for session tests
  const secUser = users.find(u => u.id === newUserId);
  if (secUser) {
    secUser.locked_until = null;
    secUser.failed_login_attempts = 0;
  }

  let sessionAccessToken: string;
  await test('Login from desktop creates session with device metadata', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
      },
      body: JSON.stringify({
        email: 'security.analyst@example.com',
        password: 'BrandNewSecPass2026$!'
      })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    sessionAccessToken = body.access_token;
  });

  let activeSessionId: number;
  await test('User can inspect active sessions with device and IP tracking', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/sessions`, {
      headers: { Authorization: `Bearer ${sessionAccessToken}` }
    });
    assert.strictEqual(res.status, 200);
    const sessions = await res.json();
    assert(Array.isArray(sessions));
    assert(sessions.length >= 1);
    const curr = sessions[0];
    assert(curr.device_name);
    assert(curr.device_type);
    assert(curr.last_ip);
    activeSessionId = curr.id;
  });

  await test('User can revoke a specific session', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/sessions/${activeSessionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${sessionAccessToken}` }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.message.includes('successfully revoked'));
  });

  await test('User can revoke all sessions at once', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/sessions/revoke-all`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${sessionAccessToken}` }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.message.includes('Revoked'));
  });

  console.log('\n--- 8. Security Events Audit Logging & CSRF Protection ---');
  await test('Security events endpoint returns auditable security log entries', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/security-events`, {
      headers: { Authorization: `Bearer ${sessionAccessToken}` }
    });
    assert.strictEqual(res.status, 200);
    const events = await res.json();
    assert(Array.isArray(events));
    assert(events.length >= 1);
    assert(events.some((e: any) => e.event_type.includes('auth.')));
  });

  await test('CSRF token endpoint returns valid CSRF protection token and header config', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/csrf-token`);
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert(body.csrf_token);
    assert.strictEqual(body.header_name, 'X-CSRF-Token');
  });

  await stopTestServer();
  console.log(`\n==================================================`);
  console.log(` Security Hardening Test Suite Summary:`);
  console.log(` Total Tests: ${passedCount + failedCount}`);
  console.log(` Passed:      ${passedCount}`);
  console.log(` Failed:      ${failedCount}`);
  console.log(`==================================================\n`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
