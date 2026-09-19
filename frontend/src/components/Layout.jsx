import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Activity, Users, FileText, BarChart2, LogOut, Settings } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

export const Layout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout-container">
      {/* Sidebar */}
      <aside className="glass-panel sidebar">
        <div className="sidebar-header">
          <div className="logo-icon text-gradient">
            <Activity size={28} />
          </div>
          <h2>FedPedia<span className="text-gradient">-XAI</span></h2>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Activity size={20} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/patients" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Users size={20} />
            <span>Patients</span>
          </NavLink>
          <NavLink to="/predictions" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <FileText size={20} />
            <span>Predictions</span>
          </NavLink>
          <NavLink to="/analytics" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <BarChart2 size={20} />
            <span>Analytics</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div className="user-info">
              <span className="user-name">{user?.name}</span>
              <span className="user-role badge badge-neutral">{user?.role?.replace('_', ' ')}</span>
            </div>
          </div>
          <button className="btn btn-secondary logout-btn" onClick={handleLogout}>
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="topbar">
          <div className="topbar-glass glass-panel">
            <div className="topbar-left">
              <span className="date-display">{new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
            </div>
            <div className="topbar-right">
              {user?.role === 'system_admin' && (
                <button className="icon-btn">
                  <Settings size={20} />
                </button>
              )}
            </div>
          </div>
        </header>

        <div className="page-content animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
