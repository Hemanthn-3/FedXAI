import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Lock, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      navigate('/');
    } catch {
      setError('Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-glass glass-panel">
        <div className="login-header">
          <div className="login-logo text-gradient">
            <Activity size={48} strokeWidth={1.5} />
          </div>
          <h1>FedPedia<span className="text-gradient">-XAI</span></h1>
          <p>Secure Federated Healthcare Analytics</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="login-error animate-fade-in">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <div className="input-group">
            <div className="input-icon">
              <Mail size={18} />
            </div>
            <input
              type="email"
              className="input-field with-icon"
              placeholder="Email Address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <div className="input-icon">
              <Lock size={18} />
            </div>
            <input
              type="password"
              className="input-field with-icon"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button 
            type="submit" 
            className="btn btn-primary login-btn"
            disabled={loading}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div className="login-footer">
          <p>Authorized Clinical Personnel Only</p>
        </div>
      </div>
    </div>
  );
};
