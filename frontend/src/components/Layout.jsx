import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { patientsApi, metricsApi } from '../api';

export const Layout = () => {
  const auth = useAuth() || {};
  const { user, logout, activeNode } = auth;
  const navigate = useNavigate();
  const location = useLocation();
  const [patientCount, setPatientCount] = useState(0);
  const [currentRound, setCurrentRound] = useState(0);

  const currentHospitalNode = activeNode || localStorage.getItem('active_hospital_node') || (
    user?.email?.includes('.h2') ? 'Hospital Node 2' :
    user?.email?.includes('.h3') ? 'Hospital Node 3' : 'Hospital Node 1'
  );

  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const [patientsRes, roundsRes] = await Promise.all([
          patientsApi.list().catch(() => ({ data: { total: 0, items: [] } })),
          metricsApi.getTrainingRounds().catch(() => ({ data: { rounds: [] } }))
        ]);
        if (patientsRes?.data?.total !== undefined) {
          setPatientCount(patientsRes.data.total);
        } else if (patientsRes?.data?.items?.length !== undefined) {
          setPatientCount(patientsRes.data.items.length);
        }
        if (roundsRes?.data?.rounds?.length) {
          const maxRound = Math.max(...roundsRes.data.rounds.map(r => r.round_number || 0));
          if (maxRound > 0) setCurrentRound(maxRound);
        }
      } catch (e) {
        console.warn('Telemetry sync error:', e);
      }
    };
    fetchCounts();
  }, [activeNode]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const currentDateStr = new Date().toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });

  return (
    <div className="min-h-screen bg-surface text-on-surface flex flex-col antialiased">
      {/* Fixed Left Navigation Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-72 bg-surface-container-lowest/95 backdrop-blur-xl z-50 flex flex-col justify-between shadow-[0_1px_12px_rgba(0,0,0,0.03)] border-r border-surface-container-high/60">
        <div className="flex flex-col">
          {/* Logo Header */}
          <div className="h-16 px-space-lg flex items-center gap-space-sm border-b border-surface-container-low/80">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-primary to-secondary p-0.5 shadow-sm flex items-center justify-center flex-shrink-0">
              <div className="w-full h-full bg-surface-container-lowest rounded-[10px] flex items-center justify-center text-primary">
                <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>vital_signs</span>
              </div>
            </div>
            <div className="flex flex-col">
              <span className="font-title-md text-title-md text-on-surface tracking-tight leading-none">
                FedPedia<span className="text-primary">-XAI</span>
              </span>
              <span className="font-label-sm text-label-sm text-tertiary-container uppercase tracking-wider mt-0.5">
                Precision Cardiology
              </span>
            </div>
          </div>

          {/* Navigation Items */}
          <div className="px-space-md mt-space-md">
            <div className="px-space-sm pb-space-xs font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">
              Clinical Workspace
            </div>
            <nav className="flex flex-col gap-1.5 mt-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center justify-between px-space-md py-space-sm rounded-xl transition-all bg-gradient-to-r from-primary to-secondary text-on-primary font-title-sm shadow-[0_4px_14px_rgba(0,88,190,0.25)]"
                    : "flex items-center justify-between px-space-md py-space-sm rounded-xl font-title-sm text-title-sm text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all"
                }
              >
                <div className="flex items-center gap-space-sm">
                  <span className="material-symbols-outlined text-title-md">vital_signs</span>
                  <span>Dashboard</span>
                </div>
              </NavLink>

              <NavLink
                to="/patients"
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center justify-between px-space-md py-space-sm rounded-xl transition-all bg-gradient-to-r from-primary to-secondary text-on-primary font-title-sm shadow-[0_4px_14px_rgba(0,88,190,0.25)]"
                    : "flex items-center justify-between px-space-md py-space-sm rounded-xl font-title-sm text-title-sm text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all"
                }
              >
                <div className="flex items-center gap-space-sm">
                  <span className="material-symbols-outlined text-title-md">clinical_notes</span>
                  <span>Patients</span>
                </div>
                <span className="px-2 py-0.5 rounded-full font-label-sm text-label-sm bg-surface-container-highest text-primary font-bold">
                  {patientCount}
                </span>
              </NavLink>

              <NavLink
                to="/predictions"
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center justify-between px-space-md py-space-sm rounded-xl transition-all bg-gradient-to-r from-primary to-secondary text-on-primary font-title-sm shadow-[0_4px_14px_rgba(0,88,190,0.25)]"
                    : "flex items-center justify-between px-space-md py-space-sm rounded-xl font-title-sm text-title-sm text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all"
                }
              >
                <div className="flex items-center gap-space-sm">
                  <span className="material-symbols-outlined text-title-md">psychology_alt</span>
                  <span>Predictions &amp; XAI</span>
                </div>
                <span className="h-2 w-2 rounded-full bg-secondary-container animate-pulse"></span>
              </NavLink>

              <NavLink
                to="/analytics"
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center justify-between px-space-md py-space-sm rounded-xl transition-all bg-gradient-to-r from-primary to-secondary text-on-primary font-title-sm shadow-[0_4px_14px_rgba(0,88,190,0.25)]"
                    : "flex items-center justify-between px-space-md py-space-sm rounded-xl font-title-sm text-title-sm text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all"
                }
              >
                <div className="flex items-center gap-space-sm">
                  <span className="material-symbols-outlined text-title-md">hub</span>
                  <span>Federated Analytics</span>
                </div>
                <span className="material-symbols-outlined text-body-sm text-tertiary">sync</span>
              </NavLink>
            </nav>
          </div>

          {/* Node Status Info Tile */}
          <div className="px-space-md mt-space-lg">
            <div className="p-space-md rounded-xl bg-surface-container-low shadow-[0_2px_8px_rgba(0,0,0,0.02)] border border-surface-container-high/60">
              <div className="flex items-center gap-space-xs font-label-sm text-label-sm text-tertiary mb-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary-fixed-dim opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary"></span>
                </span>
                <span className="font-semibold uppercase tracking-wider">{currentHospitalNode} Online</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Global round #{currentRound} completed. Differential privacy budget: ε=0.45.
              </p>
            </div>
          </div>
        </div>

        {/* User Profile Footer */}
        <div className="p-space-md border-t border-surface-container-high/60">
          <div className="p-space-sm rounded-xl bg-surface-container-low flex items-center justify-between">
            <div className="flex items-center gap-space-sm min-w-0">
              <img
                alt="Profile"
                className="w-8 h-8 rounded-full object-cover flex-shrink-0 ring-1 ring-primary/20"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBSkCcFrE8v-Sg9-vKz4hp-YEhkGpatr_9yZ5B3WXEoZvghZFEJbePmO9Ydihzj0J_ig_foMEZ7qE3qYiVS0Du_BQenbqno_TyMPddgYau87pgZScQOyOiGXb_2yjjR4Xh6JwM9gLiwDqPE8v4wsfqQUifujQQWLGyCnYXdq-QVnKYi19rN8qKqLkDBDMGEe6V6GWSRJIsVo0nAmkEKVGr3Dq9Iqb3X5uWzfroo1bxdLieL3xiHQXqo"
              />
              <div className="min-w-0">
                <div className="font-title-sm text-title-sm text-on-surface truncate">
                  {user?.name || 'Dr. Elena Vance, MD'}
                </div>
                <div className="font-body-sm text-[11px] text-on-surface-variant truncate">
                  {user?.role === 'system_admin' ? 'Chief Medical Director' : 'Chief Cardiologist'}
                </div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-outline hover:text-error hover:bg-error-container/40 transition-colors flex items-center justify-center cursor-pointer"
              title="Sign Out"
              type="button"
            >
              <span className="material-symbols-outlined text-title-sm">logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Area with Pl-72 padding */}
      <div className="pl-72 flex-1 flex flex-col min-h-screen">
        {/* Top Header */}
        <header className="fixed top-0 left-72 right-0 h-16 bg-surface-container-lowest/85 backdrop-blur-xl z-40 shadow-[0_1px_8px_rgba(0,0,0,0.03)] border-b border-surface-container-high/60">
          <div className="h-16 w-full px-space-lg flex items-center justify-between">
            <div className="flex items-center gap-space-md">
              <div className="flex items-center gap-space-xs px-space-md py-1.5 rounded-full bg-surface-container-low border border-surface-container-high/50">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary"></span>
                </span>
                <span className="font-title-sm text-title-sm text-on-surface">
                  {currentHospitalNode}
                </span>
                <span className="font-body-sm text-body-sm text-tertiary font-semibold">
                  (Connected &amp; Synchronized)
                </span>
              </div>
            </div>

            <div className="flex items-center gap-space-md">
              <div className="hidden md:flex items-center gap-1.5 text-on-surface-variant font-code-telemetry text-code-telemetry px-space-sm py-1 rounded bg-surface-container">
                <span className="material-symbols-outlined text-body-md text-primary">calendar_today</span>
                <span>Today, {currentDateStr}</span>
              </div>
              <div className="h-4 w-[1px] bg-outline-variant/40"></div>
              <div className="flex items-center gap-space-xs">
                <button
                  className="p-2 rounded-xl text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors cursor-pointer"
                  type="button"
                  title="Notifications"
                >
                  <span className="material-symbols-outlined text-headline-sm">notifications</span>
                </button>
                <button
                  className="p-2 rounded-xl text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors cursor-pointer"
                  type="button"
                  title="Node Settings"
                >
                  <span className="material-symbols-outlined text-headline-sm">settings</span>
                </button>
              </div>
              <img
                alt="Profile"
                className="w-8 h-8 rounded-full object-cover ring-2 ring-primary/20"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBSkCcFrE8v-Sg9-vKz4hp-YEhkGpatr_9yZ5B3WXEoZvghZFEJbePmO9Ydihzj0J_ig_foMEZ7qE3qYiVS0Du_BQenbqno_TyMPddgYau87pgZScQOyOiGXb_2yjjR4Xh6JwM9gLiwDqPE8v4wsfqQUifujQQWLGyCnYXdq-QVnKYi19rN8qKqLkDBDMGEe6V6GWSRJIsVo0nAmkEKVGr3Dq9Iqb3X5uWzfroo1bxdLieL3xiHQXqo"
              />
            </div>
          </div>
        </header>

        {/* Content Outlet */}
        <main className="relative pt-16 bg-surface min-h-screen flex-1 flex flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
