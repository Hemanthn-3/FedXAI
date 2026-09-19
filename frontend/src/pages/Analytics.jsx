import { useEffect, useState } from 'react';
import { BarChart2, TrendingUp, RefreshCw, AlertTriangle } from 'lucide-react';
import { analyticsApi, metricsApi } from '../api';
import './TablePages.css';
import './Analytics.css';

export const Analytics = () => {
  const [flReport, setFlReport] = useState(null);
  const [rounds, setRounds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fairnessLoading, setFairnessLoading] = useState(false);
  const [fairnessResult, setFairnessResult] = useState(null);

  const fetchData = async () => {
    try {
      const [reportRes, roundsRes] = await Promise.all([
        analyticsApi.getFLReport(),
        metricsApi.getTrainingRounds()
      ]);
      setFlReport(reportRes.data);
      setRounds(roundsRes.data.rounds || []);
    } catch (err) {
      console.error('Failed to fetch analytics', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 6000);
    return () => clearInterval(timer);
  }, []);

  const runFairnessCheck = async () => {
    setFairnessLoading(true);
    try {
      const { data } = await analyticsApi.checkFairness({
        feature_name: 'sex',
        privileged_group: 'male',
        groups: {
          male: {
            labels: [0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1],
            predictions: [0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1],
            positive_rate: 0.60
          },
          female: {
            labels: [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
            predictions: [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
            positive_rate: 0.33
          },
        },
        federated_ranking: [
          { feature: 'oldpeak', abs_contribution: 0.235 },
          { feature: 'exang', abs_contribution: 0.185 },
          { feature: 'thalach', abs_contribution: 0.138 },
        ],
        centralized_ranking: [
          { feature: 'oldpeak', abs_contribution: 0.240 },
          { feature: 'exang', abs_contribution: 0.190 },
          { feature: 'thalach', abs_contribution: 0.142 },
        ],
      });
      setFairnessResult(data);
    } catch (err) {
      console.error('Fairness check error:', err);
    } finally {
      setFairnessLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header flex-between" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1><BarChart2 size={24} style={{ display: 'inline', marginRight: 10, verticalAlign: 'text-bottom' }} /> FL Analytics</h1>
          <p>Federated learning performance and model fairness.</p>
        </div>
        <button className="btn btn-primary" onClick={runFairnessCheck} disabled={fairnessLoading}>
          <RefreshCw size={18} className={fairnessLoading ? 'animate-spin' : ''} />
          {fairnessLoading ? 'Analyzing Bias...' : 'Run Fairness Check'}
        </button>
      </div>

      {fairnessResult && (
        <div className={`glass-card animate-fade-in ${fairnessResult.overall_bias_detected ? 'border-danger' : 'border-success'}`}>
          <div className="flex-between" style={{ marginBottom: 16 }}>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              {fairnessResult.overall_bias_detected ? <AlertTriangle className="text-warning" /> : <TrendingUp className="text-success" />}
              Fairness Report
            </h3>
            <span className={`badge ${fairnessResult.overall_bias_detected ? 'badge-danger' : 'badge-success'}`}>
              {fairnessResult.overall_bias_detected ? 'Bias Detected' : 'Fair Model'}
            </span>
          </div>
          <p className="text-muted" style={{ marginBottom: 16 }}>{fairnessResult.recommendation}</p>
          <div className="table-responsive">
            <table className="data-table" style={{ background: 'rgba(0,0,0,0.2)' }}>
              <thead><tr><th>Feature</th><th>Group</th><th>Accuracy</th><th>Disparate Impact</th></tr></thead>
              <tbody>
                {fairnessResult.group_analyses?.map((analysis, i) => (
                  Object.keys(analysis.group_metrics).map(group => (
                    <tr key={`${i}-${group}`}>
                      <td>{analysis.feature_name}</td>
                      <td>{group}</td>
                      <td>{(analysis.group_metrics[group].accuracy * 100).toFixed(1)}%</td>
                      <td>{analysis.disparate_impact[group]?.toFixed(3) || 'N/A'}</td>
                    </tr>
                  ))
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="dashboard-row">
        <div className="glass-card stat-card">
          <div className="stat-info" style={{ width: '100%' }}>
            <h3>Global Model Accuracy</h3>
            <div className="flex-between" style={{ marginTop: 8 }}>
              <p className="stat-value text-gradient">{(flReport?.summary?.accuracy?.final * 100 || 0).toFixed(1)}%</p>
              <TrendingUp className="text-success" size={28} />
            </div>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-info" style={{ width: '100%' }}>
            <h3>Global Loss</h3>
            <div className="flex-between" style={{ marginTop: 8 }}>
              <p className="stat-value text-warning">{(flReport?.summary?.loss?.final || 0).toFixed(4)}</p>
              <TrendingUp className="text-warning" size={28} style={{ transform: 'scaleY(-1)' }} />
            </div>
          </div>
        </div>
      </div>

      <div className="glass-panel content-panel">
        <div className="panel-toolbar">
          <h3>Training Rounds</h3>
        </div>
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Round</th>
                <th>Dataset</th>
                <th>Status</th>
                <th>Accuracy</th>
                <th>Loss</th>
                <th>Participation</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="6" className="text-center">Loading rounds...</td></tr>
              ) : rounds.length === 0 ? (
                <tr><td colSpan="6" className="text-center text-muted">No rounds found.</td></tr>
              ) : (
                rounds.map(r => (
                  <tr key={r.id}>
                    <td>Round {r.round_number}</td>
                    <td><span className="badge badge-neutral">{r.dataset_type.replace('_', ' ')}</span></td>
                    <td>
                      <span className={`badge ${r.status === 'completed' ? 'badge-success' : 'badge-warning'}`}>
                        {r.status.toUpperCase()}
                      </span>
                    </td>
                    <td>{r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : '—'}</td>
                    <td>{r.loss != null ? r.loss.toFixed(4) : '—'}</td>
                    <td>{r.participating_clients} / {r.total_clients}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
