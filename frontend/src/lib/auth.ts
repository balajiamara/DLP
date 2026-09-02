// Note: Storing JWT tokens in localStorage is acceptable for portfolio/demo applications,
// but has known XSS security trade-offs compared to httpOnly cookies for production applications.

import type { AuthTokens } from '../types/auth';

const ACCESS_TOKEN_KEY = 'dlp_access_token';
const REFRESH_TOKEN_KEY = 'dlp_refresh_token';

export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

export const setTokens = (tokens: AuthTokens): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
};

export const setAccessToken = (access: string): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
};

export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};
