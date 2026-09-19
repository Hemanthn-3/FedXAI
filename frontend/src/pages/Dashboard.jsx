import { useEffect, useState } from 'react';
import { Activity, Server, ShieldCheck, Database, CheckCircle2, Radio } from 'lucide-react';
import { metricsApi } from '../api';
import './Dashboard.css';

const STATUS_BADGE = (status) =>
  status === 'completed' ? 'badge-success'
  : status === 'failed'  ? 'badge-danger'
  : 'badge-warning';

export const Dashboard = () => {
  const [health, setHealth]   = useState(null);
  const [stats, setStats]     = useState(null);
  const [rounds, setRounds]   = useState([]);
  const [loading, setLoading] = useState(true);
  const fetchData = async () => {
    try {
      const [healthRes, statsRes, roundsRes] = await Promise.all([
        metricsApi.getSystemHealth(),
        metricsApi.getPredictionStats(),
        metricsApi.getTrainingRounds(),
      ]);
      setHealth(healthRes.data);
      setStats(statsRes.data);
      setRounds(roundsRes.data.rounds || []);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 6000);
    return () => clearInterval(timer);
  }, []);

  if (loading) return <div className="loading-state"><Radio className="animate-spin" size={22} />&nbsp;Loading dashboard…</div>;

  return (
    <div className="dashboard-container">
      <div className="page-header">
        <h1>System Overview</h1>
        <p>Live metrics and prediction statistics across federated nodes.</p>
      </div>

      {/* Stat cards */}
      <div className="stats-grid">
        <div className="glass-card stat-card">
          <div className="stat-icon bg-primary">
            <Activity size={24} />
          </div>
          <div className="stat-info">
            <h3>Total Predictions</h3>
            <p className="stat-value">{stats?.total_predictions || 0}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon bg-warning">
            <ShieldCheck size={24} />
          </div>
          <div className="stat-info">
            <h3>High Risk Detected</h3>
            <p className="stat-value text-warning">{stats?.by_risk_level?.high || 0}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon bg-success">
            <Database size={24} />
          </div>
          <div className="stat-info">
            <h3>XAI Reports</h3>
            <p className="stat-value">{stats?.with_xai_report || 0}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon bg-info">
            <Database size={24} />
          </div>
          <div className="stat-info">
            <h3>Training Rounds</h3>
            <p className="stat-value">{rounds.length}</p>
          </div>
        </div>
      </div>

      <div className="dashboard-row">
        {/* System Health panel */}
        <div className="glass-panel system-health-panel">
          <h3><Server size={20} /> System Health</h3>
          <div className="health-details">
            <div className="health-item">
              <span>Database Status</span>
              <span className={`badge ${health?.database === 'up' ? 'badge-success' : 'badge-danger'}`}>
                {health?.database || 'Unknown'}
              </span>
            </div>
            <div className="health-item">
              <span>Redis Cache</span>
              <span className={`badge ${health?.redis === 'up' ? 'badge-success' : 'badge-danger'}`}>
                {health?.redis || 'Unknown'}
              </span>
            </div>
            <div className="health-item">
              <span>Overall Status</span>
              <span className={`badge ${health?.status === 'ok' ? 'badge-success' : 'badge-warning'}`}>
                {health?.status === 'ok' ? <><CheckCircle2 size={14}/> Operational</> : 'Degraded'}
              </span>
            </div>
          </div>
        </div>

        {/* Recent Training Activity panel (replaces placeholder) */}
        <div className="glass-panel activity-panel">
          <h3>Recent Training Activity</h3>
          {rounds.length === 0 ? (
            <p className="text-muted" style={{ padding: '24px', textAlign: 'center' }}>
              No training rounds recorded yet.
            </p>
          ) : (
            <div className="activity-list">
              {rounds.slice(0, 5).map(r => (
                <div className="activity-item" key={r.id}>
                  <div className="activity-dot" />
                  <div className="activity-body">
                    <div className="flex-between">
                      <span className="activity-title">
                        Round {r.round_number} &mdash;&nbsp;
                        <span style={{ textTransform: 'capitalize' }}>
                          {r.dataset_type.replace('_', ' ')}
                        </span>
                      </span>
                      <span className={`badge ${STATUS_BADGE(r.status)}`}>
                        {r.status}
                      </span>
                    </div>
                    <span className="activity-meta text-muted">
                      Accuracy: {r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : '—'}
                      &nbsp;·&nbsp;
                      Loss: {r.loss != null ? r.loss.toFixed(4) : '—'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
