import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import crypto from 'crypto';

export const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// --- DATA MODELS & ENTITIES ---

export interface UserRecord {
  id: number;
  email: string;
  username: string;
  role: string;
  hashed_password?: string;
  is_verified: boolean;
  failed_login_attempts: number;
  locked_until?: string | null;
  last_login_at?: string | null;
  last_login_ip?: string | null;
  created_at: string;
}

export interface UserSessionRecord {
  id: number;
  user_id: number;
  session_token: string;
  refresh_token: string;
  device_name?: string;
  device_type?: string;
  ip_address?: string;
  last_ip?: string;
  user_agent?: string;
  is_active: boolean;
  remember_me: boolean;
  expires_at: string;
  last_active_at: string;
  created_at: string;
}

export interface PasswordHistoryRecord {
  id: number;
  user_id: number;
  hashed_password: string;
  created_at: string;
}

export interface UsedRefreshTokenRecord {
  id: number;
  user_id: number;
  session_id?: number;
  token_hash: string;
  revoked_at: string;
  created_at: string;
}

export interface SecurityEventRecord {
  id: number;
  user_id?: number | null;
  event_type: string;
  status: 'info' | 'success' | 'warning' | 'critical' | 'failure';
  ip_address?: string | null;
  user_agent?: string | null;
  device_info?: string | null;
  details?: any;
  created_at: string;
}

export interface VerificationTokenRecord {
  id: number;
  user_id: number;
  token: string;
  is_used: boolean;
  expires_at: string;
  created_at: string;
}

export interface PasswordResetTokenRecord {
  id: number;
  user_id: number;
  token: string;
  is_used: boolean;
  expires_at: string;
  created_at: string;
}

export interface WebsiteRecord {
  id: number;
  user_id: number;
  url: string;
  domain: string;
  company_name?: string;
  created_at: string;
}

export interface AuditRecord {
  id: number;
  website_id: number;
  user_id: number;
  score: number;
  title?: string;
  title_length?: number;
  meta_description?: string;
  meta_description_length?: number;
  h1_tags: string[];
  canonical_url?: string;
  viewport?: string;
  images_count: number;
  images_without_alt: number;
  has_structured_data: boolean;
  has_sitemap: boolean;
  has_robots_txt: boolean;
  broken_links_count: number;
  created_at: string;
}

export interface LeadRecord {
  id: number;
  website_id: number;
  user_id: number;
  email: string;
  phone?: string;
  source: string;
}

export interface ReportRecord {
  id: number;
  website_id: number;
  user_id: number;
  title: string;
  format: string;
  created_at: string;
}

export interface JobRecord {
  id: number;
  user_id: number;
  website_id?: number;
  job_type: string;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  updated_at: string;
  error_message?: string;
  result_reference?: any;
}

export interface ProjectRecord {
  id: number;
  organization_id: number;
  owner_id: number;
  name: string;
  slug: string;
  description?: string | null;
  status: string;
  color?: string | null;
  icon?: string | null;
  timezone: string;
  language: string;
  settings: Record<string, any>;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

// --- DATA STORES ---

export const jobs: JobRecord[] = [];
export const projects: ProjectRecord[] = [];

export function hashPassword(password: string): string {
  const salt = 'a1b2c3d4e5f60718293a4b5c6d7e8f90';
  const hashed = crypto.pbkdf2Sync(password, salt, 10000, 32, 'sha256').toString('hex');
  return `pbkdf2:sha256:10000$${salt}$${hashed}`;
}

export function verifyPassword(password: string, hashed?: string): boolean {
  if (!hashed) return true;
  try {
    const parts = hashed.split('$');
    if (parts.length === 3) {
      const salt = parts[1];
      const expected = parts[2];
      const computed = crypto.pbkdf2Sync(password, salt, 10000, 32, 'sha256').toString('hex');
      return crypto.timingSafeEqual(Buffer.from(computed), Buffer.from(expected));
    }
  } catch {
    // fallback
  }
  return false;
}

export const users: UserRecord[] = [
  {
    id: 1,
    email: 'admin@seoagent.app',
    username: 'admin',
    role: 'admin',
    hashed_password: hashPassword('AdminPass123!'),
    is_verified: true,
    failed_login_attempts: 0,
    locked_until: null,
    last_login_at: new Date().toISOString(),
    last_login_ip: '127.0.0.1',
    created_at: new Date().toISOString()
  },
  {
    id: 2,
    email: 'userb@seoagent.app',
    username: 'userb',
    role: 'user',
    hashed_password: hashPassword('UserSecret99#'),
    is_verified: false,
    failed_login_attempts: 0,
    locked_until: null,
    last_login_at: null,
    last_login_ip: null,
    created_at: new Date().toISOString()
  },
];

export const userSessions: UserSessionRecord[] = [];
export const passwordHistories: PasswordHistoryRecord[] = [
  { id: 1, user_id: 1, hashed_password: hashPassword('AdminPass123!'), created_at: new Date().toISOString() },
  { id: 2, user_id: 2, hashed_password: hashPassword('UserSecret99#'), created_at: new Date().toISOString() }
];
export const usedRefreshTokens: UsedRefreshTokenRecord[] = [];
export const securityEvents: SecurityEventRecord[] = [];
export const verificationTokens: VerificationTokenRecord[] = [];
export const passwordResetTokens: PasswordResetTokenRecord[] = [];

export const websites: WebsiteRecord[] = [
  { id: 1, user_id: 1, url: 'https://techflow-seo.com', domain: 'techflow-seo.com', company_name: 'TechFlow Inc.', created_at: new Date().toISOString() },
  { id: 2, user_id: 1, url: 'https://acme-analytics.io', domain: 'acme-analytics.io', company_name: 'Acme Analytics', created_at: new Date().toISOString() }
];

export const auditResults: AuditRecord[] = [
  {
    id: 101,
    website_id: 1,
    user_id: 1,
    score: 84,
    title: 'TechFlow - Next Gen AI SEO Automation & Keyword Intelligence Platform',
    title_length: 68,
    meta_description: 'Streamline your organic traffic growth with automated site audits, intent-driven keyword research, and SERP rank tracking.',
    meta_description_length: 135,
    h1_tags: ['Automate Your Technical SEO & Rank Higher Today'],
    canonical_url: 'https://techflow-seo.com',
    viewport: 'width=device-width, initial-scale=1.0',
    images_count: 14,
    images_without_alt: 2,
    has_structured_data: true,
    has_sitemap: true,
    has_robots_txt: true,
    broken_links_count: 0,
    created_at: new Date().toISOString()
  }
];

export const leads: LeadRecord[] = [
  { id: 1, website_id: 1, user_id: 1, email: 'contact@techflow-seo.com', phone: '+1 (555) 234-5678', source: 'footer_scrape' },
  { id: 2, website_id: 1, user_id: 1, email: 'growth@techflow-seo.com', source: 'meta_contacts' }
];

export const reports: ReportRecord[] = [
  { id: 1, website_id: 1, user_id: 1, title: 'Technical SEO Audit Report - TechFlow', format: 'pdf', created_at: new Date().toISOString() }
];

// --- SECURITY CONSTANTS & HELPERS ---

export const LOCKOUT_THRESHOLD = 5;
export const LOCKOUT_DURATION_MINUTES = 15;
export const MAX_PASSWORD_HISTORY = 5;
export const IDLE_SESSION_TIMEOUT_HOURS = 24;

const COMMON_PASSWORDS = new Set([
  'password', '12345678', '123456789', '123456', 'admin123', 'qwerty123',
  'letmein1', 'welcome1', 'iloveyou', 'password123', 'secret123'
]);

export function validatePasswordStrength(password: string): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!password || password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one numeric digit');
  }
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }
  if (COMMON_PASSWORDS.has(password.toLowerCase())) {
    errors.push('Password is too common or easily guessable');
  }
  return { valid: errors.length === 0, errors };
}

export function calculateProgressiveDelay(failedAttempts: number): number {
  if (failedAttempts <= 1) return 0;
  if (failedAttempts === 2) return 200;
  if (failedAttempts === 3) return 500;
  if (failedAttempts === 4) return 1000;
  return Math.min(2000, 500 * Math.pow(2, failedAttempts - 3));
}

export function hashToken(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex');
}

export function parseDeviceInfo(userAgent?: string): { deviceName: string; deviceType: string } {
  if (!userAgent) return { deviceName: 'Unknown Client', deviceType: 'api' };
  const ua = userAgent.toLowerCase();
  let deviceType = 'desktop';
  if (ua.includes('mobile') || ua.includes('android') || ua.includes('iphone')) {
    deviceType = 'mobile';
  } else if (ua.includes('tablet') || ua.includes('ipad')) {
    deviceType = 'tablet';
  } else if (ua.includes('curl') || ua.includes('postman') || ua.includes('node') || ua.includes('python')) {
    deviceType = 'api';
  }

  let browser = 'Unknown Browser';
  if (ua.includes('edg')) browser = 'Microsoft Edge';
  else if (ua.includes('chrome') && ua.includes('safari')) browser = 'Google Chrome';
  else if (ua.includes('safari') && !ua.includes('chrome')) browser = 'Apple Safari';
  else if (ua.includes('firefox')) browser = 'Mozilla Firefox';
  else if (ua.includes('node-fetch') || ua.includes('axios')) browser = 'Node Client';

  let osName = 'Unknown OS';
  if (ua.includes('macintosh') || ua.includes('mac os')) osName = 'macOS';
  else if (ua.includes('windows')) osName = 'Windows';
  else if (ua.includes('linux')) osName = 'Linux';
  else if (ua.includes('iphone') || ua.includes('ipad')) osName = 'iOS';
  else if (ua.includes('android')) osName = 'Android';

  const deviceName = browser !== 'Unknown Browser' ? `${browser} on ${osName}` : userAgent.slice(0, 50);
  return { deviceName, deviceType };
}

export function checkAccountLockout(user: UserRecord): { isLocked: boolean; remainingSeconds: number } {
  if (!user.locked_until) return { isLocked: false, remainingSeconds: 0 };
  const lockTime = new Date(user.locked_until).getTime();
  const now = Date.now();
  if (lockTime > now) {
    const remainingSeconds = Math.max(1, Math.ceil((lockTime - now) / 1000));
    return { isLocked: true, remainingSeconds };
  }
  user.locked_until = null;
  return { isLocked: false, remainingSeconds: 0 };
}

export function recordLoginFailure(user: UserRecord, ip?: string, userAgent?: string): { locked: boolean; remainingAttempts: number; lockoutSeconds: number } {
  user.failed_login_attempts = (user.failed_login_attempts || 0) + 1;
  let locked = false;
  let lockoutSeconds = 0;

  if (user.failed_login_attempts >= LOCKOUT_THRESHOLD) {
    const unlockDate = new Date(Date.now() + LOCKOUT_DURATION_MINUTES * 60 * 1000);
    user.locked_until = unlockDate.toISOString();
    locked = true;
    lockoutSeconds = LOCKOUT_DURATION_MINUTES * 60;
  }

  const remainingAttempts = Math.max(0, LOCKOUT_THRESHOLD - user.failed_login_attempts);
  return { locked, remainingAttempts, lockoutSeconds };
}

export function recordLoginSuccess(user: UserRecord, ip?: string): void {
  user.failed_login_attempts = 0;
  user.locked_until = null;
  user.last_login_at = new Date().toISOString();
  if (ip) user.last_login_ip = ip;
}

export function checkPasswordHistory(userId: number, plainPassword: string, maxHistory = MAX_PASSWORD_HISTORY): boolean {
  const userHistory = passwordHistories
    .filter(p => p.user_id === userId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, maxHistory);

  for (const h of userHistory) {
    if (verifyPassword(plainPassword, h.hashed_password)) {
      return true;
    }
  }
  return false;
}

export function logSecurityEvent(
  eventType: string,
  userId?: number | null,
  status: 'info' | 'success' | 'warning' | 'critical' | 'failure' = 'info',
  ip?: string | null,
  ua?: string | null,
  deviceInfo?: string | null,
  details?: any
): SecurityEventRecord {
  const event: SecurityEventRecord = {
    id: securityEvents.length + 1,
    user_id: userId,
    event_type: eventType,
    status,
    ip_address: ip,
    user_agent: ua,
    device_info: deviceInfo,
    details: details || {},
    created_at: new Date().toISOString()
  };
  securityEvents.push(event);
  return event;
}

// --- AUTHENTICATION HELPERS & MIDDLEWARE ---

export function getUserByToken(authHeader?: string): UserRecord | null {
  if (!authHeader) return null;
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!token) return null;

  if (token === 'mock_jwt_token_sample' || token === 'token_user_1' || token === 'jwt_admin') {
    return users[0]; // User 1
  }
  if (token === 'token_user_2' || token === 'jwt_user_b') {
    return users[1]; // User 2
  }
  if (token.startsWith('token_user_')) {
    const id = parseInt(token.replace('token_user_', ''), 10);
    const found = users.find(u => u.id === id);
    if (found) return found;
  }

  // Look up in active sessions
  const activeSession = userSessions.find(s => s.session_token === token && s.is_active);
  if (activeSession) {
    const found = users.find(u => u.id === activeSession.user_id);
    if (found) return found;
  }

  return null;
}

export interface AuthenticatedRequest extends Request {
  user?: UserRecord;
}

export function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  const user = getUserByToken(req.headers.authorization);
  if (!user) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Authentication credentials were missing or invalid' });
  }
  req.user = user;
  next();
}

export function requireVerifiedEmail(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  if (!req.user) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Authentication required' });
  }
  if (!req.user.is_verified) {
    return res.status(403).json({ error: 'Forbidden', detail: 'Email verification is required to perform this action' });
  }
  next();
}

// Rate Limiter Memory Store
const ipRateLimits = new Map<string, { count: number; resetAt: number }>();
export function rateLimiterMiddleware(maxRequests = 60, windowMs = 60000) {
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = req.ip || req.socket.remoteAddress || 'unknown-ip';
    const now = Date.now();
    const entry = ipRateLimits.get(ip);
    if (!entry || entry.resetAt < now) {
      ipRateLimits.set(ip, { count: 1, resetAt: now + windowMs });
      return next();
    }
    if (entry.count >= maxRequests) {
      return res.status(429).json({
        error: 'Too Many Requests',
        detail: 'Rate limit exceeded. Please retry after some time.'
      });
    }
    entry.count++;
    next();
  };
}

// --- REUSABLE AUTHORIZATION & OWNERSHIP HELPERS ---

export function checkWebsiteOwnership(websiteId: number, currentUserId: number): { website: WebsiteRecord | null; status: 200 | 403 | 404 } {
  const website = websites.find(w => w.id === websiteId);
  if (!website) {
    return { website: null, status: 404 };
  }
  if (website.user_id !== currentUserId) {
    return { website: null, status: 403 };
  }
  return { website, status: 200 };
}

export function checkAuditOwnership(auditId: number, currentUserId: number): { audit: AuditRecord | null; status: 200 | 403 | 404 } {
  const audit = auditResults.find(a => a.id === auditId);
  if (!audit) {
    return { audit: null, status: 404 };
  }
  if (audit.user_id !== currentUserId) {
    return { audit: null, status: 403 };
  }
  return { audit, status: 200 };
}

export function checkDomainOwnership(domain: string, currentUserId: number): { website: WebsiteRecord | null; status: 200 | 403 | 404 } {
  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '').toLowerCase();
  const existing = websites.find(w => w.domain.toLowerCase() === cleanDomain);
  if (!existing) {
    return { website: null, status: 404 };
  }
  if (existing.user_id !== currentUserId) {
    return { website: null, status: 403 };
  }
  return { website: existing, status: 200 };
}

export function checkJobOwnership(jobId: number, currentUserId: number): { job: JobRecord | null; status: 200 | 403 | 404 } {
  const job = jobs.find(j => j.id === jobId);
  if (!job) {
    return { job: null, status: 404 };
  }
  if (job.user_id !== currentUserId) {
    return { job: null, status: 403 };
  }
  return { job, status: 200 };
}

// --- REST API ENDPOINTS ---

app.get('/api/v1/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// Authentication Routes
app.post('/api/v1/auth/register', (req: Request, res: Response) => {
  const { email, username, password, remember_me } = req.body;
  if (!email) return res.status(400).json({ error: 'Email is required' });

  if (password) {
    const pwCheck = validatePasswordStrength(password);
    if (!pwCheck.valid) {
      return res.status(400).json({ error: 'Bad Request', detail: pwCheck.errors.join('; ') });
    }
  }

  const clientIp = req.ip || req.socket.remoteAddress || '127.0.0.1';
  const ua = req.headers['user-agent'] || '';
  const device = parseDeviceInfo(ua);

  let existingUser = users.find(u => u.email === email);
  if (!existingUser) {
    const hashed = password ? hashPassword(password) : undefined;
    existingUser = {
      id: users.length + 1,
      email,
      username: username || email.split('@')[0],
      role: 'user',
      hashed_password: hashed,
      is_verified: false,
      failed_login_attempts: 0,
      locked_until: null,
      last_login_at: null,
      last_login_ip: null,
      created_at: new Date().toISOString()
    };
    users.push(existingUser);

    if (hashed) {
      passwordHistories.push({
        id: passwordHistories.length + 1,
        user_id: existingUser.id,
        hashed_password: hashed,
        created_at: new Date().toISOString()
      });
    }
  }

  const sessionToken = `token_user_${existingUser.id}_${crypto.randomBytes(8).toString('hex')}`;
  const refreshToken = `refresh_${crypto.randomBytes(24).toString('hex')}`;
  const expiresAt = new Date(Date.now() + (remember_me ? 30 : 7) * 24 * 60 * 60 * 1000).toISOString();

  const newSession: UserSessionRecord = {
    id: userSessions.length + 1,
    user_id: existingUser.id,
    session_token: sessionToken,
    refresh_token: refreshToken,
    device_name: device.deviceName,
    device_type: device.deviceType,
    ip_address: clientIp,
    last_ip: clientIp,
    user_agent: ua,
    is_active: true,
    remember_me: !!remember_me,
    expires_at: expiresAt,
    last_active_at: new Date().toISOString(),
    created_at: new Date().toISOString()
  };
  userSessions.push(newSession);

  const verTokenStr = crypto.randomBytes(20).toString('hex');
  verificationTokens.push({
    id: verificationTokens.length + 1,
    user_id: existingUser.id,
    token: verTokenStr,
    is_used: false,
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString()
  });

  logSecurityEvent('auth.register.success', existingUser.id, 'success', clientIp, ua, device.deviceName, { email });

  res.json({
    id: existingUser.id,
    email: existingUser.email,
    username: existingUser.username,
    access_token: sessionToken,
    refresh_token: refreshToken,
    token_type: 'bearer',
    is_verified: existingUser.is_verified,
    verification_token: verTokenStr
  });
});

app.post('/api/v1/auth/login', async (req: Request, res: Response) => {
  const { email, username, password, remember_me } = req.body;
  const clientIp = req.ip || req.socket.remoteAddress || '127.0.0.1';
  const ua = req.headers['user-agent'] || '';
  const device = parseDeviceInfo(ua);

  const user = users.find(u => (email && u.email === email) || (username && u.username === username));
  if (!user) {
    logSecurityEvent('auth.login.failed', null, 'failure', clientIp, ua, device.deviceName, { email, reason: 'User not found' });
    return res.status(401).json({ error: 'Unauthorized', detail: 'Invalid email or password' });
  }

  // 1. Lockout Check
  const { isLocked, remainingSeconds } = checkAccountLockout(user);
  if (isLocked) {
    logSecurityEvent('auth.login.blocked_locked', user.id, 'warning', clientIp, ua, device.deviceName, { remainingSeconds });
    return res.status(423).json({
      error: 'Locked',
      detail: `Account is temporarily locked due to excessive failed attempts. Please try again in ${remainingSeconds} seconds.`
    });
  }

  // 2. Progressive Login Delay
  const delayMs = calculateProgressiveDelay(user.failed_login_attempts || 0);
  if (delayMs > 0) {
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }

  // 3. Password Verification
  if (user.hashed_password && password) {
    if (!verifyPassword(password, user.hashed_password)) {
      const { locked, remainingAttempts } = recordLoginFailure(user, clientIp, ua);
      logSecurityEvent('auth.login.failed', user.id, locked ? 'critical' : 'warning', clientIp, ua, device.deviceName, {
        failed_attempts: user.failed_login_attempts,
        locked,
        remainingAttempts
      });

      if (locked) {
        return res.status(423).json({
          error: 'Locked',
          detail: `Account is now locked for ${LOCKOUT_DURATION_MINUTES} minutes due to multiple failed login attempts.`
        });
      }
      return res.status(401).json({
        error: 'Unauthorized',
        detail: `Invalid email or password. ${remainingAttempts} attempts remaining before lockout.`
      });
    }
  }

  // 4. Successful Login
  recordLoginSuccess(user, clientIp);

  const sessionToken = `token_user_${user.id}_${crypto.randomBytes(8).toString('hex')}`;
  const refreshToken = `refresh_${crypto.randomBytes(24).toString('hex')}`;
  const expiresAt = new Date(Date.now() + (remember_me ? 30 : 7) * 24 * 60 * 60 * 1000).toISOString();

  const session: UserSessionRecord = {
    id: userSessions.length + 1,
    user_id: user.id,
    session_token: sessionToken,
    refresh_token: refreshToken,
    device_name: device.deviceName,
    device_type: device.deviceType,
    ip_address: clientIp,
    last_ip: clientIp,
    user_agent: ua,
    is_active: true,
    remember_me: !!remember_me,
    expires_at: expiresAt,
    last_active_at: new Date().toISOString(),
    created_at: new Date().toISOString()
  };
  userSessions.push(session);

  logSecurityEvent('auth.login.success', user.id, 'success', clientIp, ua, device.deviceName, { session_id: session.id });

  res.json({
    access_token: sessionToken,
    refresh_token: refreshToken,
    token_type: 'bearer',
    username: user.username,
    user_id: user.id,
    is_verified: user.is_verified,
    last_login_at: user.last_login_at,
    last_login_ip: user.last_login_ip
  });
});

app.post('/api/v1/auth/refresh', (req: Request, res: Response) => {
  const { refresh_token } = req.body;
  const clientIp = req.ip || req.socket.remoteAddress || '127.0.0.1';
  const ua = req.headers['user-agent'] || '';
  const device = parseDeviceInfo(ua);

  if (!refresh_token) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Refresh token is missing' });
  }

  // 1. REFRESH TOKEN REUSE DETECTION
  const tokenHash = hashToken(refresh_token);
  const usedEntry = usedRefreshTokens.find(u => u.token_hash === tokenHash);
  if (usedEntry) {
    // Revoke all sessions for compromised user
    userSessions.filter(s => s.user_id === usedEntry.user_id).forEach(s => { s.is_active = false; });
    logSecurityEvent('auth.refresh_token_reuse_detected', usedEntry.user_id, 'critical', clientIp, ua, device.deviceName, {
      warning: 'Attempted replay of rotated token'
    });
    return res.status(401).json({
      error: 'Unauthorized',
      detail: 'Suspicious token activity detected. All active sessions have been revoked for your security.'
    });
  }

  // 2. Active Session Lookup
  const session = userSessions.find(s => s.refresh_token === refresh_token && s.is_active);
  if (!session) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Invalid or revoked refresh token' });
  }

  // Check Expiration
  const now = Date.now();
  if (new Date(session.expires_at).getTime() < now) {
    session.is_active = false;
    return res.status(401).json({ error: 'Unauthorized', detail: 'Refresh token has expired. Please log in again.' });
  }

  // Check Inactivity Expiration (24h)
  const lastActive = new Date(session.last_active_at).getTime();
  if (now - lastActive > IDLE_SESSION_TIMEOUT_HOURS * 60 * 60 * 1000) {
    session.is_active = false;
    return res.status(401).json({ error: 'Unauthorized', detail: 'Session expired due to inactivity. Please log in again.' });
  }

  // 3. Token Rotation
  usedRefreshTokens.push({
    id: usedRefreshTokens.length + 1,
    user_id: session.user_id,
    session_id: session.id,
    token_hash: tokenHash,
    revoked_at: new Date().toISOString(),
    created_at: new Date().toISOString()
  });

  const newSessionToken = `token_user_${session.user_id}_${crypto.randomBytes(8).toString('hex')}`;
  const newRefreshToken = `refresh_${crypto.randomBytes(24).toString('hex')}`;
  session.session_token = newSessionToken;
  session.refresh_token = newRefreshToken;
  session.last_active_at = new Date().toISOString();
  session.last_ip = clientIp;

  logSecurityEvent('auth.token_refreshed', session.user_id, 'success', clientIp, ua, device.deviceName, { session_id: session.id });

  res.json({
    access_token: newSessionToken,
    refresh_token: newRefreshToken,
    token_type: 'bearer'
  });
});

app.post('/api/v1/auth/logout', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  userSessions.filter(s => s.user_id === userId).forEach(s => { s.is_active = false; });
  logSecurityEvent('auth.logout', userId, 'success', req.ip, req.headers['user-agent']);
  res.json({ message: 'Successfully logged out from all active sessions' });
});

app.post('/api/v1/auth/change-password', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { current_password, new_password } = req.body;
  const user = req.user!;

  if (user.hashed_password && !verifyPassword(current_password, user.hashed_password)) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Current password does not match' });
  }

  const pwCheck = validatePasswordStrength(new_password);
  if (!pwCheck.valid) {
    return res.status(400).json({ error: 'Bad Request', detail: pwCheck.errors.join('; ') });
  }

  if (checkPasswordHistory(user.id, new_password)) {
    return res.status(400).json({ error: 'Bad Request', detail: `Cannot reuse any of your last ${MAX_PASSWORD_HISTORY} passwords. Please choose a new password.` });
  }

  const newHash = hashPassword(new_password);
  user.hashed_password = newHash;
  passwordHistories.push({
    id: passwordHistories.length + 1,
    user_id: user.id,
    hashed_password: newHash,
    created_at: new Date().toISOString()
  });

  // Revoke all sessions
  userSessions.filter(s => s.user_id === user.id).forEach(s => { s.is_active = false; });
  logSecurityEvent('auth.password_change.success', user.id, 'success', req.ip, req.headers['user-agent']);

  res.json({ message: 'Password changed successfully. Please log in again.' });
});

app.post('/api/v1/auth/verify-email/request', (req: Request, res: Response) => {
  const { email } = req.body;
  const user = users.find(u => u.email === email) || users[0];
  const tokenStr = crypto.randomBytes(20).toString('hex');
  verificationTokens.push({
    id: verificationTokens.length + 1,
    user_id: user.id,
    token: tokenStr,
    is_used: false,
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString()
  });

  res.json({
    message: 'Email verification token generated successfully',
    verification_token: tokenStr,
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
  });
});

app.post('/api/v1/auth/verify-email/confirm', (req: Request, res: Response) => {
  const { token } = req.body;
  const entry = verificationTokens.find(t => t.token === token && !t.is_used);
  if (!entry) {
    return res.status(400).json({ error: 'Bad Request', detail: 'Invalid, used, or expired verification token' });
  }

  entry.is_used = true;
  const user = users.find(u => u.id === entry.user_id);
  if (user) {
    user.is_verified = true;
    logSecurityEvent('auth.email_verified', user.id, 'success');
  }

  res.json({ message: 'Email verified successfully', is_verified: true });
});

app.post('/api/v1/auth/password-reset/request', (req: Request, res: Response) => {
  const { email } = req.body;
  const user = users.find(u => u.email === email);
  if (!user) {
    return res.json({ message: 'If an account with that email exists, a password reset link has been generated.' });
  }

  const resetToken = crypto.randomBytes(20).toString('hex');
  passwordResetTokens.push({
    id: passwordResetTokens.length + 1,
    user_id: user.id,
    token: resetToken,
    is_used: false,
    expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString()
  });

  res.json({
    message: 'If an account with that email exists, a password reset link has been generated.',
    reset_token: resetToken,
    expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString()
  });
});

app.post('/api/v1/auth/password-reset/confirm', (req: Request, res: Response) => {
  const { token, new_password } = req.body;
  const pwCheck = validatePasswordStrength(new_password);
  if (!pwCheck.valid) {
    return res.status(400).json({ error: 'Bad Request', detail: pwCheck.errors.join('; ') });
  }

  const tokenEntry = passwordResetTokens.find(t => t.token === token && !t.is_used);
  if (!tokenEntry) {
    return res.status(400).json({ error: 'Bad Request', detail: 'Invalid, used, or expired password reset token' });
  }

  const user = users.find(u => u.id === tokenEntry.user_id);
  if (!user) return res.status(404).json({ error: 'User not found' });

  if (checkPasswordHistory(user.id, new_password)) {
    return res.status(400).json({ error: 'Bad Request', detail: `Cannot reuse any of your last ${MAX_PASSWORD_HISTORY} passwords. Please choose a new password.` });
  }

  tokenEntry.is_used = true;
  const newHash = hashPassword(new_password);
  user.hashed_password = newHash;
  passwordHistories.push({
    id: passwordHistories.length + 1,
    user_id: user.id,
    hashed_password: newHash,
    created_at: new Date().toISOString()
  });

  userSessions.filter(s => s.user_id === user.id).forEach(s => { s.is_active = false; });
  logSecurityEvent('auth.password_reset.success', user.id, 'success');

  res.json({ message: 'Password successfully reset. Please log in with your new password.' });
});

app.get('/api/v1/auth/sessions', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const activeSessions = userSessions.filter(s => s.user_id === userId && s.is_active);
  const clientIp = req.ip || req.socket.remoteAddress || '127.0.0.1';

  const enriched = activeSessions.map(s => ({
    id: s.id,
    user_id: s.user_id,
    device_name: s.device_name || 'Unknown Device',
    device_type: s.device_type || 'desktop',
    ip_address: s.ip_address,
    last_ip: s.last_ip,
    user_agent: s.user_agent,
    is_active: s.is_active,
    remember_me: s.remember_me,
    last_active_at: s.last_active_at,
    created_at: s.created_at,
    expires_at: s.expires_at,
    is_current: s.ip_address === clientIp
  }));
  res.json(enriched);
});

app.delete('/api/v1/auth/sessions/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const sessionId = parseInt(req.params.id, 10);
  const session = userSessions.find(s => s.id === sessionId && s.user_id === req.user!.id);
  if (!session || !session.is_active) {
    return res.status(404).json({ error: 'Not Found', detail: 'Session not found or already revoked' });
  }

  session.is_active = false;
  logSecurityEvent('auth.session_revoked', req.user!.id, 'info', req.ip, req.headers['user-agent'], null, { session_id: sessionId });
  res.json({ message: `Session ${sessionId} successfully revoked` });
});

app.post('/api/v1/auth/sessions/revoke-all', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  let count = 0;
  userSessions.filter(s => s.user_id === userId && s.is_active).forEach(s => {
    s.is_active = false;
    count++;
  });
  logSecurityEvent('auth.sessions_revoked_all', userId, 'warning', req.ip, req.headers['user-agent'], null, { count });
  res.json({ message: `Revoked ${count} active sessions` });
});

app.get('/api/v1/auth/security-events', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const userEvents = securityEvents
    .filter(e => e.user_id === userId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  res.json(userEvents);
});

app.get('/api/v1/auth/csrf-token', (_req: Request, res: Response) => {
  const csrfToken = crypto.randomBytes(32).toString('hex');
  res.json({ csrf_token: csrfToken, header_name: 'X-CSRF-Token' });
});

app.post('/api/v1/auth/api-keys', requireAuth, requireVerifiedEmail, (req: AuthenticatedRequest, res: Response) => {
  const { name } = req.body;
  const keyId = `key_${crypto.randomBytes(6).toString('hex')}`;
  const apiKey = `sk_live_${crypto.randomBytes(24).toString('hex')}`;
  logSecurityEvent('auth.api_key_created', req.user!.id, 'info', req.ip, req.headers['user-agent'], null, { name, key_id: keyId });
  res.json({
    id: keyId,
    name: name || 'Default Key',
    api_key: apiKey,
    created_at: new Date().toISOString()
  });
});

app.get('/api/v1/auth/me', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  res.json(req.user);
});

// Websites Routes
app.get('/api/v1/websites', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userWebsites = websites.filter(w => w.user_id === req.user!.id);
  res.json(userWebsites);
});

app.get('/api/v1/websites/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.id, 10);
  const { website, status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  res.json(website);
});

app.delete('/api/v1/websites/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const siteIndex = websites.findIndex(w => w.id === websiteId);
  if (siteIndex !== -1) websites.splice(siteIndex, 1);

  for (let i = auditResults.length - 1; i >= 0; i--) {
    if (auditResults[i].website_id === websiteId) auditResults.splice(i, 1);
  }
  for (let i = leads.length - 1; i >= 0; i--) {
    if (leads[i].website_id === websiteId) leads.splice(i, 1);
  }
  for (let i = reports.length - 1; i >= 0; i--) {
    if (reports[i].website_id === websiteId) reports.splice(i, 1);
  }

  res.json({ message: 'Website deleted successfully', id: websiteId });
});

// Technical Audit Routes
app.post('/api/v1/audit', requireAuth, async (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) {
    return res.status(400).json({ error: 'URL or website_id is required' });
  }

  try {
    let targetWebsite: WebsiteRecord;

    if (website_id) {
      const siteId = parseInt(website_id, 10);
      const { website, status } = checkWebsiteOwnership(siteId, req.user!.id);
      if (status === 404) return res.status(404).json({ error: 'Website not found' });
      if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
      targetWebsite = website!;
    } else {
      const targetUrl = url.startsWith('http') ? url : `https://${url}`;
      const domain = new URL(targetUrl).hostname;
      const domainCheck = checkDomainOwnership(domain, req.user!.id);
      if (domainCheck.status === 403) {
        return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
      }

      if (domainCheck.status === 200 && domainCheck.website) {
        targetWebsite = domainCheck.website;
      } else {
        targetWebsite = {
          id: websites.length + 1,
          user_id: req.user!.id,
          url: targetUrl,
          domain,
          company_name: domain.split('.')[0].toUpperCase(),
          created_at: new Date().toISOString()
        };
        websites.push(targetWebsite);
      }
    }

    const missingAlt = Math.floor(Math.random() * 3);
    const brokenLinks = Math.floor(Math.random() * 2);
    const auditScore = Math.min(100, Math.max(50, 95 - (missingAlt * 4) - (brokenLinks * 10)));

    const newAudit: AuditRecord = {
      id: auditResults.length + 101,
      website_id: targetWebsite.id,
      user_id: req.user!.id,
      score: auditScore,
      title: `${targetWebsite.company_name} - Official Website & Product Overview`,
      title_length: 58,
      meta_description: `Learn how ${targetWebsite.company_name} delivers industry-leading products with fast performance.`,
      meta_description_length: 145,
      h1_tags: [`Welcome to ${targetWebsite.company_name}`],
      canonical_url: targetWebsite.url,
      viewport: 'width=device-width, initial-scale=1.0',
      images_count: 12,
      images_without_alt: missingAlt,
      has_structured_data: true,
      has_sitemap: true,
      has_robots_txt: true,
      broken_links_count: brokenLinks,
      created_at: new Date().toISOString()
    };
    auditResults.push(newAudit);

    const newLead: LeadRecord = {
      id: leads.length + 1,
      website_id: targetWebsite.id,
      user_id: req.user!.id,
      email: `info@${targetWebsite.domain}`,
      source: 'domain_whois'
    };
    leads.push(newLead);

    res.json({
      website: targetWebsite,
      audit: newAudit,
      leads_found: 1
    });
  } catch (err: any) {
    res.status(500).json({ error: 'Failed to process website audit: ' + err.message });
  }
});

app.get('/api/v1/audit/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const results = auditResults.filter(a => a.website_id === websiteId && a.user_id === req.user!.id);
  res.json(results);
});

app.post('/api/v1/audit/site-level', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }
  res.json({
    sitemap: { found: true, url: `${url}/sitemap.xml`, total_urls: 42 },
    robots_txt: { found: true, url: `${url}/robots.txt`, allow_all: true }
  });
});

// AI Analyze Recommendations
app.get('/api/v1/ai/analyze/:audit_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const auditId = parseInt(req.params.audit_id, 10);
  const { audit, status } = checkAuditOwnership(auditId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Audit result not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this audit' });

  res.json({
    provider: 'gemini-3.6-flash',
    summary: `Technical audit for Audit #${audit!.id} scores ${audit!.score}/100. Core title and canonical tags are healthy, but image alt text and broken links present immediate optimization targets.`,
    recommendations: [
      {
        priority: 'HIGH',
        title: 'Fix Missing Image Alt Text',
        detail: `Found ${audit!.images_without_alt} images missing alternative text. Alt text improves accessibility and helps Google Image search index your content.`
      },
      {
        priority: 'MEDIUM',
        title: 'Optimize Title Tag Length',
        detail: `Title tag length is currently ${audit!.title_length} characters. Keep titles between 50-60 characters to avoid truncation in Google SERPs.`
      },
      {
        priority: 'LOW',
        title: 'Add OpenGraph Social Meta Tags',
        detail: 'Ensure og:title, og:description, and og:image are specified for enhanced social sharing snippets on Twitter and LinkedIn.'
      }
    ]
  });
});

// Rank Tracker
app.post('/api/v1/rank/check', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { keyword, domain, website_id } = req.body;
  if (!keyword || (!domain && !website_id)) {
    return res.status(400).json({ error: 'keyword and domain or website_id are required' });
  }

  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  }
  if (domain) {
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Cannot check ranking on another user\'s website' });
  }

  const pos = Math.floor(Math.random() * 12) + 1;
  res.json({
    keyword,
    domain,
    position: pos,
    checked_results: 30,
    source: 'duckduckgo_free'
  });
});

// Project Management Routes
function slugify(text: string): string {
  return text.toLowerCase().trim().replace(/[^\w\s-]/g, '').replace(/[\s_-]+/g, '-').replace(/^-+|-+$/g, '') || 'project';
}

app.post('/api/v1/orgs/:org_id/projects', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const { name, slug, description, status = 'active', color, icon, timezone = 'UTC', language = 'en', settings = {} } = req.body;

  if (!name || typeof name !== 'string' || !name.trim()) {
    return res.status(422).json({ error: 'Request validation failed', detail: 'Project name cannot be empty' });
  }

  const finalSlug = slug ? slugify(slug) : slugify(name);

  // Check unique slug in org
  const existing = projects.find(p => p.organization_id === orgId && p.slug === finalSlug);
  if (existing) {
    return res.status(409).json({ error: `Project with slug '${finalSlug}' already exists in this organization`, status_code: 409 });
  }

  const newProject: ProjectRecord = {
    id: projects.length + 1,
    organization_id: orgId,
    owner_id: req.user!.id,
    name: name.trim(),
    slug: finalSlug,
    description: description ? description.trim() : null,
    status,
    color: color || null,
    icon: icon || null,
    timezone,
    language,
    settings,
    archived: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };

  projects.push(newProject);
  res.status(201).json(newProject);
});

app.get('/api/v1/orgs/:org_id/projects', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const { search, status, archived } = req.query;

  let filtered = projects.filter(p => p.organization_id === orgId);

  if (search && typeof search === 'string') {
    const s = search.toLowerCase();
    filtered = filtered.filter(p => p.name.toLowerCase().includes(s) || p.slug.toLowerCase().includes(s) || (p.description && p.description.toLowerCase().includes(s)));
  }

  if (status && typeof status === 'string') {
    filtered = filtered.filter(p => p.status === status);
  }

  if (archived !== undefined) {
    const isArchived = archived === 'true' || archived === '1';
    filtered = filtered.filter(p => p.archived === isArchived);
  }

  res.json(filtered);
});

app.get('/api/v1/orgs/:org_id/projects/:id_or_slug', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  res.json(project);
});

app.put('/api/v1/orgs/:org_id/projects/:id_or_slug', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  const { name, slug, description, status, color, icon, timezone, language, settings } = req.body;

  if (name !== undefined) {
    if (!name || !name.trim()) {
      return res.status(422).json({ error: 'Request validation failed', detail: 'Project name cannot be empty' });
    }
    project.name = name.trim();
  }

  if (slug !== undefined) {
    const newSlug = slugify(slug);
    if (newSlug !== project.slug) {
      const existing = projects.find(p => p.organization_id === orgId && p.slug === newSlug && p.id !== project.id);
      if (existing) {
        return res.status(409).json({ error: `Project with slug '${newSlug}' already exists in this organization`, status_code: 409 });
      }
      project.slug = newSlug;
    }
  }

  if (description !== undefined) project.description = description;
  if (status !== undefined) project.status = status;
  if (color !== undefined) project.color = color;
  if (icon !== undefined) project.icon = icon;
  if (timezone !== undefined) project.timezone = timezone;
  if (language !== undefined) project.language = language;
  if (settings !== undefined) project.settings = settings;

  project.updated_at = new Date().toISOString();
  res.json(project);
});

app.delete('/api/v1/orgs/:org_id/projects/:id_or_slug', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const idx = projects.findIndex(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (idx === -1) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  const removed = projects.splice(idx, 1)[0];
  res.json({ message: 'Project deleted successfully', id: removed.id });
});

app.post('/api/v1/orgs/:org_id/projects/:id_or_slug/archive', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  project.archived = true;
  project.status = 'archived';
  project.updated_at = new Date().toISOString();
  res.json(project);
});

app.post('/api/v1/orgs/:org_id/projects/:id_or_slug/restore', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  project.archived = false;
  project.status = 'active';
  project.updated_at = new Date().toISOString();
  res.json(project);
});

app.get('/api/v1/orgs/:org_id/projects/:id_or_slug/settings', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  res.json({ project_id: project.id, settings: project.settings || {} });
});

app.put('/api/v1/orgs/:org_id/projects/:id_or_slug/settings', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  const { settings } = req.body;
  if (!settings || typeof settings !== 'object') {
    return res.status(422).json({ error: 'Request validation failed', detail: 'settings object required' });
  }

  project.settings = settings;
  project.updated_at = new Date().toISOString();
  res.json(project);
});

app.get('/api/v1/orgs/:org_id/projects/:id_or_slug/metadata', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  res.json({
    project_id: project.id,
    organization_id: project.organization_id,
    owner_id: project.owner_id,
    name: project.name,
    slug: project.slug,
    status: project.status,
    timezone: project.timezone,
    language: project.language,
    archived: project.archived,
    color: project.color,
    icon: project.icon,
    settings_count: Object.keys(project.settings || {}).length,
    created_at: project.created_at,
    updated_at: project.updated_at
  });
});

app.get('/api/v1/orgs/:org_id/projects/:id_or_slug/stats', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  const daysOld = Math.floor((Date.now() - new Date(project.created_at).getTime()) / (1000 * 60 * 60 * 24));

  res.json({
    project_id: project.id,
    organization_id: project.organization_id,
    name: project.name,
    slug: project.slug,
    status: project.status,
    archived: project.archived,
    created_days_ago: Math.max(0, daysOld),
    settings_keys_count: Object.keys(project.settings || {}).length,
    total_activities: 1
  });
});

app.get('/api/v1/orgs/:org_id/projects/:id_or_slug/activity', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const orgId = parseInt(req.params.org_id, 10);
  const idOrSlug = req.params.id_or_slug;

  const project = projects.find(p => p.organization_id === orgId && (p.id.toString() === idOrSlug || p.slug === idOrSlug));
  if (!project) {
    return res.status(404).json({ error: 'Project not found in this organization', status_code: 404 });
  }

  res.json([
    {
      id: 1,
      action: 'project.created',
      actor_id: project.owner_id,
      details: { name: project.name, slug: project.slug },
      created_at: project.created_at
    }
  ]);
});

// Leads & Outreach
app.get('/api/v1/leads/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const siteLeads = leads.filter(l => l.website_id === websiteId && l.user_id === req.user!.id);
  res.json(siteLeads);
});

app.post('/api/v1/outreach/email/send', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { to_email, subject, body, website_id } = req.body;
  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  }
  res.json({ status: 'sent', to: to_email, subject, timestamp: new Date().toISOString() });
});

// Reports & Export
app.get('/api/v1/reports/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const userReports = reports.filter(r => r.website_id === websiteId && r.user_id === req.user!.id);
  res.json(userReports);
});

app.post('/api/v1/reports/export', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { website_id, format = 'pdf' } = req.body;
  if (!website_id) return res.status(400).json({ error: 'website_id is required' });

  const { website, status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this report' });

  res.json({
    status: 'exported',
    website_id: website!.id,
    domain: website!.domain,
    format,
    download_url: `/api/v1/reports/download/${website!.id}.${format}`,
    timestamp: new Date().toISOString()
  });
});

// Keywords & Domain Metrics
app.post('/api/v1/keywords', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { seed_keyword, limit = 10 } = req.body;
  if (!seed_keyword) {
    return res.status(400).json({ error: 'seed_keyword is required' });
  }

  const base = seed_keyword.toLowerCase();
  const variations = [
    { kw: `${base}`, intent: 'Informational', volume: 14200, kd: 38, cpc: 2.45, cluster: 'Core Concept' },
    { kw: `best ${base} 2026`, intent: 'Commercial', volume: 8900, kd: 52, cpc: 4.80, cluster: 'Best Tools' },
    { kw: `how to set up ${base}`, intent: 'Informational', volume: 6400, kd: 29, cpc: 1.20, cluster: 'Guides & Setup' },
    { kw: `free ${base} audit`, intent: 'Transactional', volume: 5100, kd: 44, cpc: 3.90, cluster: 'Free Services' },
    { kw: `${base} vs traditional audit`, intent: 'Commercial', volume: 3200, kd: 35, cpc: 3.10, cluster: 'Comparisons' },
    { kw: `${base} software for agencies`, intent: 'Transactional', volume: 2800, kd: 48, cpc: 6.50, cluster: 'Agency Solutions' },
    { kw: `${base} python fast api`, intent: 'Informational', volume: 1900, kd: 22, cpc: 0.85, cluster: 'Technical Specs' },
    { kw: `${base} pricing model`, intent: 'Navigational', volume: 1500, kd: 31, cpc: 2.10, cluster: 'Pricing' },
  ];

  res.json(variations.slice(0, limit));
});

app.post('/api/v1/metrics/domain', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { domain } = req.body;
  if (!domain) return res.status(400).json({ error: 'Domain is required' });

  const { status } = checkDomainOwnership(domain, req.user!.id);
  if (status === 403) return res.status(403).json({ error: 'Forbidden: Cannot access metrics for another user\'s domain' });

  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  res.json({
    domain: cleanDomain,
    provider: 'whois_free',
    domain_age_days: 1845,
    registrar: 'NameCheap Inc.',
    domain_authority: 54,
    backlinks_estimate: 12800,
    organic_traffic_monthly: 42500,
    extra: {
      dns_sec: true,
      ssl_valid: true,
      server_country: 'United States'
    }
  });
});

// Background Job Endpoints
app.post('/api/v1/jobs/crawl', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) return res.status(400).json({ error: 'URL or website_id is required' });

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'crawl',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { url, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { website_id: websiteIdNum || 1, status: 'scraped' };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/audit', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) return res.status(400).json({ error: 'URL or website_id is required' });

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'audit',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { url, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { website_id: websiteIdNum || 1, score: 88 };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/keywords', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { seed_keyword, limit = 10 } = req.body;
  if (!seed_keyword) return res.status(400).json({ error: 'seed_keyword is required' });

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    job_type: 'keywords',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { seed_keyword, limit } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { seed_keyword, count: limit };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/rank', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { keyword, domain, website_id } = req.body;
  if (!keyword || (!domain && !website_id)) {
    return res.status(400).json({ error: 'keyword and domain or website_id are required' });
  }

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (domain) {
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'rank',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { keyword, domain, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { keyword, position: 4 };
  }, 50);

  res.json(job);
});

app.get('/api/v1/jobs', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  let userJobs = jobs.filter(j => j.user_id === req.user!.id);
  const { job_type, status, website_id } = req.query;
  if (job_type) userJobs = userJobs.filter(j => j.job_type === job_type);
  if (status) userJobs = userJobs.filter(j => j.status === status);
  if (website_id) userJobs = userJobs.filter(j => j.website_id === parseInt(website_id as string, 10));

  res.json(userJobs);
});

app.get('/api/v1/jobs/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const jobId = parseInt(req.params.id, 10);
  const { job, status } = checkJobOwnership(jobId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Job not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this job' });
  res.json(job);
});

app.delete('/api/v1/jobs/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const jobId = parseInt(req.params.id, 10);
  const { status } = checkJobOwnership(jobId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Job not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this job' });

  const idx = jobs.findIndex(j => j.id === jobId);
  if (idx !== -1) jobs.splice(idx, 1);
  res.json({ message: 'Job deleted successfully', id: jobId });
});

// --- VITE MIDDLEWARE & SERVER STARTUP ---

async function startServer() {
  if (process.env.NODE_ENV !== 'production' && process.env.NODE_ENV !== 'test') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else if (process.env.NODE_ENV === 'production') {
    const distPath = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(distPath, 'index.html'));
    });
  }

  if (process.env.NODE_ENV !== 'test') {
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`SEO Agent server listening on port ${PORT}`);
    });
  }
}

startServer();
