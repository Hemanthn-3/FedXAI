import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleAuth = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setStatusMessage('Authenticating Cryptographic Handshake...');

    try {
      await login(email, password);
      setStatusMessage('Node Synchronized!');
      setTimeout(() => {
        navigate('/');
      }, 300);
    } catch {
      setError('Invalid email or password');
      setLoading(false);
    }
  };


  return (
    <div className="min-h-screen w-full flex items-center justify-center p-space-lg bg-surface font-body-md text-body-md text-on-surface antialiased relative overflow-hidden select-none">
      {/* Dynamic Luminous Atmospheric Drops */}
      <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-gradient-to-tr from-primary-fixed to-secondary-fixed opacity-40 blur-3xl pointer-events-none"></div>
      <div className="absolute top-1/2 -right-32 w-80 h-80 rounded-full bg-gradient-to-bl from-tertiary-fixed via-primary-fixed-dim to-secondary-fixed opacity-30 blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-24 left-1/3 w-96 h-96 rounded-full bg-gradient-to-r from-surface-variant via-primary-fixed to-surface-container-highest opacity-50 blur-3xl pointer-events-none"></div>

      {/* Main Authentication Central Card Container */}
      <div className="flex flex-col w-full items-center justify-center relative py-space-xl px-space-md z-10">
        <div className="relative w-full max-w-[480px]">
          {/* Radiant Soft Ambient Rim Layer */}
          <div className="absolute -inset-1.5 rounded-[2.5rem] bg-gradient-to-br from-primary via-secondary to-tertiary-fixed opacity-25 blur-lg transform transition-all duration-700"></div>

          <div className="relative bg-surface-container-lowest rounded-[2rem] shadow-xl overflow-hidden border border-surface-container-high/60">
            {/* Animated Heartbeat/ECG Visual Header Wave */}
            <div className="relative h-16 w-full bg-gradient-to-r from-surface-container-low via-surface-container-lowest to-surface-container-low overflow-hidden flex items-center">
              <svg className="w-[200%] h-12 text-primary" fill="none" preserveAspectRatio="none" viewBox="0 0 1000 60">
                <defs>
                  <linearGradient id="ecgGrad" x1="0%" x2="100%" y1="0%" y2="0%">
                    <stop offset="0%" stopColor="#0058be" stopOpacity="0.1"></stop>
                    <stop offset="25%" stopColor="#0058be" stopOpacity="0.8"></stop>
                    <stop offset="50%" stopColor="#8455ef" stopOpacity="1"></stop>
                    <stop offset="75%" stopColor="#008378" stopOpacity="0.8"></stop>
                    <stop offset="100%" stopColor="#0058be" stopOpacity="0.1"></stop>
                  </linearGradient>
                  <filter id="ecgGlow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="2" result="blur"></feGaussianBlur>
                    <feComposite in="SourceGraphic" in2="blur" operator="over"></feComposite>
                  </filter>
                </defs>
                <path
                  className="transition-transform duration-1000"
                  d="M 0 30 L 220 30 L 235 20 L 245 40 L 255 10 L 268 52 L 280 25 L 290 34 L 300 30 L 720 30 L 735 20 L 745 40 L 755 10 L 768 52 L 780 25 L 790 34 L 800 30 L 1000 30"
                  filter="url(#ecgGlow)"
                  stroke="url(#ecgGrad)"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                >
                  <animateTransform
                    attributeName="transform"
                    type="translate"
                    from="0 0"
                    to="-500 0"
                    dur="4s"
                    repeatCount="indefinite"
                  ></animateTransform>
                </path>
              </svg>

              {/* Live Status Pill in ECG Ribbon */}
              <div className="absolute right-4 top-3.5 flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container/70 backdrop-blur-sm border border-surface-container-high/60">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary-container opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary-container"></span>
                </span>
                <span className="font-code-telemetry text-code-telemetry text-tertiary uppercase tracking-wider text-[10px] font-bold">
                  Mesh Online
                </span>
              </div>
            </div>

            {/* Card Inner Content Area */}
            <div className="px-space-lg pb-space-lg pt-space-xs flex flex-col">
              {/* Brand Signature Mark & Identity */}
              <div className="flex flex-col items-center text-center mb-space-md">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-primary to-secondary p-0.5 shadow-md flex items-center justify-center mb-space-sm group transition-transform duration-300 hover:scale-105">
                  <div className="w-full h-full bg-surface-container-lowest rounded-[14px] flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                      vital_signs
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="font-headline-sm text-headline-sm text-on-surface tracking-tight">FedPedia</span>
                  <span className="font-headline-sm text-headline-sm bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent tracking-tight">
                    XAI
                  </span>
                  <span className="bg-secondary-fixed text-on-secondary-fixed text-[10px] font-label-sm px-1.5 py-0.5 rounded ml-1 font-bold">
                    v4.2
                  </span>
                </div>
                <h1 className="font-title-md text-title-md text-on-surface mt-2 mb-1">
                  Secure Clinical Intelligence Portal
                </h1>
                <p className="font-body-sm text-body-sm text-on-surface-variant max-w-[340px]">
                  Federated Healthcare Privacy-Preserving Diagnostic Suite
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-xl bg-error-container/60 border border-error/30 text-error flex items-center gap-2 text-body-sm animate-fade-in">
                  <span className="material-symbols-outlined text-title-sm">error</span>
                  <span>{error}</span>
                </div>
              )}

              {/* Auth Form */}
              <form className="flex flex-col gap-4" onSubmit={handleAuth}>
                {/* Email Field */}
                <div className="flex flex-col gap-1.5 text-left">
                  <label htmlFor="user-email" className="font-label-md text-label-md text-on-surface flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm text-primary">mail</span>
                    Email
                  </label>
                  <div className="relative flex items-center bg-surface-container-low rounded-xl transition-all focus-within:bg-surface-container-lowest focus-within:ring-2 focus-within:ring-primary/20">
                    <input
                      id="user-email"
                      className="w-full h-11 px-3.5 bg-transparent font-body-md text-body-md text-on-surface outline-none placeholder:text-outline"
                      placeholder="Email Address"
                      aria-label="Email Address"
                      required
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                {/* Password Field */}
                <div className="flex flex-col gap-1.5 text-left">
                  <label htmlFor="user-password" className="font-label-md text-label-md text-on-surface flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm text-primary">lock</span>
                    Password
                  </label>
                  <div className="relative flex items-center bg-surface-container-low rounded-xl transition-all focus-within:bg-surface-container-lowest focus-within:ring-2 focus-within:ring-primary/20">
                    <input
                      id="user-password"
                      className="w-full h-11 pl-3.5 pr-10 bg-transparent font-body-md text-body-md text-on-surface outline-none tracking-widest placeholder:tracking-normal placeholder:text-outline"
                      placeholder="Password"
                      aria-label="Password"
                      required
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      aria-label="Toggle token visibility"
                      className="absolute right-2 p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface transition-colors focus:outline-none cursor-pointer"
                      onClick={() => setShowPassword(!showPassword)}
                      type="button"
                    >
                      <span className="material-symbols-outlined text-lg">
                        {showPassword ? 'visibility_off' : 'visibility'}
                      </span>
                    </button>
                  </div>
                </div>

                {/* Institutional Trust Status Micro-Bar */}
                <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-surface-container-low/70 border border-surface-container-high/40">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-tertiary-container text-base">security</span>
                    <span className="font-body-sm text-[12px] text-on-surface-variant">Attestation Protocol</span>
                  </div>
                  <span className="font-code-telemetry text-[11px] font-semibold text-tertiary bg-tertiary-fixed/30 px-2 py-0.5 rounded-full">
                    SGX Enclave Active
                  </span>
                </div>

                {/* Primary Submit Button */}
                <button
                  aria-label="Sign In"
                  className="relative mt-2 w-full h-12 rounded-xl bg-gradient-to-r from-primary to-secondary text-on-primary font-title-sm text-title-sm flex items-center justify-center gap-2 shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-[1.01] active:scale-[0.99] overflow-hidden group cursor-pointer disabled:opacity-80"
                  disabled={loading}
                  type="submit"
                >
                  <span className="absolute inset-0 bg-surface-container-lowest opacity-0 group-hover:opacity-10 transition-opacity"></span>
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin"></span>
                      <span>{statusMessage}</span>
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <span>Authorize &amp; Enter Node</span>
                      <span className="material-symbols-outlined text-lg transition-transform group-hover:translate-x-1">
                        arrow_forward
                      </span>
                    </span>
                  )}
                </button>
              </form>

              {/* Secondary Operational Actions */}
              <div className="flex items-center justify-between mt-space-md pt-space-sm border-t-0 text-center">
                <a
                  className="font-label-md text-label-md text-primary hover:text-on-primary-fixed-variant transition-colors flex items-center gap-1"
                  href="#"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="material-symbols-outlined text-sm">vpn_key</span>
                  Request Node Credentials
                </a>
                <span className="text-outline-variant font-label-md">•</span>
                <a
                  className="font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors flex items-center gap-1"
                  href="#"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="material-symbols-outlined text-sm">policy</span>
                  HIPAA &amp; GDPR Protocol
                </a>
              </div>
            </div>

            {/* Trust Assurance Bottom Banner */}
            <div className="bg-surface-container py-3 px-space-md flex items-center justify-center gap-2 text-center border-t border-surface-container-high/60">
              <span className="material-symbols-outlined text-tertiary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                lock
              </span>
              <p className="font-label-sm text-[11px] text-on-surface-variant tracking-normal font-medium">
                256-bit Homomorphic Encryption Active • Zero Raw EHR Data Leaves Your Institution
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
