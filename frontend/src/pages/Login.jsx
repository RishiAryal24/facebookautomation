import React, { useState } from 'react';
import api from '../api';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const response = await api.post(
        '/auth/login',
        { email, password },
        { timeout: 15000 },
      );
      onLogin(response.data.access_token);
    } catch (loginError) {
      setError(
        ['ECONNABORTED', 'ETIMEDOUT'].includes(loginError.code)
          ? 'The server is taking too long to respond. Please try again.'
          : loginError.message,
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f4f5f9] flex items-center justify-center p-4">
      <section className="w-full max-w-md rounded-2xl border border-[#e4e7ef] bg-white p-8 shadow-sm">
        <div className="mb-6">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-[10px] bg-[#1b2140] text-white font-bold text-base shadow-xs">
            PL
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">Sign in</h1>
          <p className="mt-1 text-sm text-[#5b6475]">PyLoom Facebook Automation</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="mb-1 block text-xs font-semibold text-[#5b6475]">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-[10px] border border-[#d5d9e6] px-3 py-2.5 text-sm bg-white text-[#141a2e] focus:border-[#1b2140] focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="login-password" className="mb-1 block text-xs font-semibold text-[#5b6475]">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-[10px] border border-[#d5d9e6] px-3 py-2.5 text-sm bg-white text-[#141a2e] focus:border-[#1b2140] focus:outline-none"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-xl border border-[#e9b8b8] bg-[#fde4e4] px-3 py-2 text-xs font-medium text-[#a31f1f]">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-[#1b2140] hover:bg-[#28315c] px-4 py-2.5 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer shadow-xs"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}
