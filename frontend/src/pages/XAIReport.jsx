import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Brain, Download, RefreshCw, ArrowLeft, CheckCircle2,
  AlertTriangle, Loader, BarChart2, Zap
} from 'lucide-react';
import { predictionsApi, xaiApi } from '../api';
import './XAIReport.css';

const RISK_BADGE = {
  high:     'badge-danger',
  moderate: 'badge-warning',
  low:      'badge-success',
};

// Human-readable display names for model feature codes
const FEATURE_LABELS = {
  age:        'Age',
  sex:        'Sex',
  cp:         'Chest Pain Type',
  trestbps:   'Resting Blood Pressure',
  chol:       'Cholesterol',
  fbs:        'Fasting Blood Sugar',
  thalach:    'Maximum Heart Rate',
  exang:      'Exercise-Induced Angina',
  oldpeak:    'ST Depression (Oldpeak)',
  // legacy aliases
  bp:         'Resting Blood Pressure',
  cholesterol:'Cholesterol',
  heart_rate: 'Maximum Heart Rate',
};

const featureLabel = (name) =>
  FEATURE_LABELS[String(name).toLowerCase()] || name;

const formatLimeDescription = (desc, feature) => {
  if (!desc) return featureLabel(feature);
  let formatted = desc;
  Object.keys(FEATURE_LABELS).forEach((key) => {
    const regex = new RegExp(`\\b${key}\\b`, 'gi');
    formatted = formatted.replace(regex, FEATURE_LABELS[key]);
  });
  return formatted;
};

export const XAIReport = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [prediction, setPrediction] = useState(null);
  const [report, setReport]         = useState(null);
  const [loadingPred, setLoadingPred] = useState(true);
  const [loadingXAI, setLoadingXAI]   = useState(true);
  const [generating, setGenerating]   = useState(false);
  const [error, setError]             = useState('');

  useEffect(() => {
    const fetchPrediction = async () => {
      try {
        const { data } = await predictionsApi.get(id);
        setPrediction(data);
      } catch {
        setError('Prediction not found.');
      } finally {
        setLoadingPred(false);
      }
    };
    fetchPrediction();
  }, [id]);

  useEffect(() => {
    let active = true;
    const fetchXAIReport = async () => {
      setLoadingXAI(true);
      try {
        const { data } = await xaiApi.getByPrediction(id);
        if (active) setReport(data);
      } catch {
        if (active) setReport(null);
      } finally {
        if (active) setLoadingXAI(false);
      }
    };
    fetchXAIReport();
    return () => { active = false; };
  }, [id]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const { data } = await xaiApi.generate(id);
      setReport(data);
    } catch {
      setError('Failed to generate XAI report. Ensure the model artifact is available.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const response = await xaiApi.downloadPdfBlob(id);
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `clinical_report_${id.substring(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download PDF report', err);
      alert('Failed to download PDF report. Ensure the report has been generated.');
    }
  };

  if (loadingPred) {
    return <div className="loading-state"><Loader className="animate-spin" size={24} />&nbsp;Loading prediction…</div>;
  }

  if (error && !prediction) {
    return <div className="loading-state text-warning">{error}</div>;
  }

  return (
    <div className="page-container xai-page">
      {/* Page header */}
      <div className="page-header flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="icon-btn" onClick={() => navigate(-1)} title="Back">
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1>
              <Brain size={22} style={{ display: 'inline', marginRight: 10, verticalAlign: 'text-bottom' }} />
              XAI Explanation
            </h1>
            <p>SHAP &amp; LIME explainability for prediction&nbsp;
              <span className="text-monospace">{id.substring(0, 8)}…</span>
            </p>
          </div>
        </div>
        <div className="action-buttons">
          {report && (
            <button className="btn btn-secondary" onClick={handleDownloadPDF}>
              <Download size={16} /> Download PDF
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating
              ? <><Loader size={16} className="animate-spin" /> Generating…</>
              : <><RefreshCw size={16} /> {report ? 'Re-generate' : 'Generate Report'}</>
            }
          </button>
        </div>
      </div>

      {error && (
        <div className="xai-error-banner animate-fade-in">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Prediction summary card */}
      {prediction && (
        <div className="glass-card xai-summary animate-fade-in">
          <h3 style={{ marginBottom: 16 }}>Prediction Summary</h3>
          <div className="xai-summary-grid">
            <div className="xai-summary-item">
              <span className="xai-label">Dataset</span>
              <span className="badge badge-neutral">
                {prediction.dataset_type?.replace('_', ' ')}
              </span>
            </div>
            <div className="xai-summary-item">
              <span className="xai-label">Risk Level</span>
              <span className={`badge ${RISK_BADGE[prediction.risk_level] || 'badge-neutral'}`}>
                {prediction.risk_level?.toUpperCase()}
              </span>
            </div>
            <div className="xai-summary-item">
              <span className="xai-label">Probability</span>
              <span className="xai-value text-gradient">
                {prediction.probability != null
                  ? `${(prediction.probability * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </div>
            <div className="xai-summary-item">
              <span className="xai-label">Outcome</span>
              <span className="xai-value">
                {prediction.prediction ? 'Positive (Disease)' : 'Negative (No Disease)'}
              </span>
            </div>
            <div className="xai-summary-item">
              <span className="xai-label">Date</span>
              <span className="xai-value">
                {prediction.created_at
                  ? new Date(prediction.created_at).toLocaleString()
                  : '—'}
              </span>
            </div>
            {prediction.doctor_notes && (
              <div className="xai-summary-item xai-notes">
                <span className="xai-label">Doctor Notes</span>
                <span className="xai-value">{prediction.doctor_notes}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* XAI Report content */}
      {loadingXAI ? (
        <div className="loading-state"><Loader className="animate-spin" size={20} />&nbsp;Loading report…</div>
      ) : !report ? (
        <div className="glass-card xai-empty animate-fade-in">
          <Brain size={48} className="xai-empty-icon" />
          <h3>No XAI Report Yet</h3>
          <p>Click <strong>Generate Report</strong> to run SHAP and LIME analysis for this prediction.</p>
        </div>
      ) : (
        <div className="xai-results animate-fade-in">
          {/* Status banner */}
          <div className={`xai-status-banner ${report.status === 'completed' ? 'xai-status-ok' : 'xai-status-fail'}`}>
            {report.status === 'completed'
              ? <><CheckCircle2 size={16} /> Report completed successfully.</>
              : <><AlertTriangle size={16} /> Report status: {report.status}</>
            }
          </div>

          <div className="xai-panels">
            {/* SHAP panel — global feature importance */}
            <div className="glass-panel xai-panel">
              <h3><BarChart2 size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'text-bottom' }} />SHAP — Global Feature Importance</h3>
              <p className="text-muted" style={{ marginBottom: 16 }}>Top features driving overall model predictions.</p>
              {report.top_shap_features?.length > 0 ? (
                <table className="data-table">
                  <thead><tr><th>#</th><th>Feature</th></tr></thead>
                  <tbody>
                    {report.top_shap_features.map((feat, i) => (
                      <tr key={i}>
                        <td className="text-muted">{i + 1}</td>
                        <td><span className="badge badge-neutral">{featureLabel(feat)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-muted text-center">No SHAP features available.</p>
              )}
            </div>

            {/* LIME panel — local explanation with conditions */}
            <div className="glass-panel xai-panel">
              <h3><Zap size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'text-bottom' }} />LIME — Local Feature Conditions</h3>
              <p className="text-muted" style={{ marginBottom: 16 }}>
                Rule conditions for this prediction.{' '}
                <span style={{ color: 'var(--color-danger,#ef4444)', fontWeight: 600 }}>+ Toward Positive</span>{' '}|{' '}
                <span style={{ color: 'var(--color-success,#22c55e)', fontWeight: 600 }}>− Toward Negative</span>
              </p>
              {report.local_contributions?.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr><th>#</th><th>Feature Condition</th><th>Dir</th><th>Impact</th></tr>
                  </thead>
                  <tbody>
                    {report.local_contributions.slice(0, 9).map((item, i) => {
                      const signed = Number(item.contribution ?? 0);
                      const abs    = Number(item.abs_contribution ?? 0);
                      const isPos  = signed >= 0;
                      const pct    = Math.min(100, abs * 400).toFixed(1);
                      return (
                        <tr key={i}>
                          <td className="text-muted">{i + 1}</td>
                          <td style={{ fontSize: '0.82rem', fontWeight: 500 }}>
                            {formatLimeDescription(item.description, item.feature)}
                          </td>
                          <td>
                            <span style={{
                              fontWeight: 700,
                              color: isPos ? 'var(--color-danger,#ef4444)' : 'var(--color-success,#22c55e)',
                              fontSize: '0.85rem',
                            }}>
                              {isPos ? '+ Toward Positive' : '− Toward Negative'}
                            </span>
                          </td>
                          <td>
                            <div className="xai-bar-track">
                              <div className="xai-bar-fill" style={{
                                width: `${pct}%`,
                                background: isPos
                                  ? 'linear-gradient(90deg,#f97316,#ef4444)'
                                  : 'linear-gradient(90deg,#22c55e,#16a34a)',
                              }} />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="text-muted text-center">No LIME features available.</p>
              )}
            </div>
          </div>

          {/* Full SHAP Feature Ranking — signed contributions with direction */}
          {report.feature_ranking?.length > 0 && (
            <div className="glass-panel xai-ranking-panel">
              <h3>Full SHAP Feature Ranking — Signed Contributions</h3>
              <p className="text-muted" style={{ marginBottom: 12, fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--color-danger,#ef4444)', fontWeight: 600 }}>Toward Positive (+)</span>{' '}
                — increases risk estimate.{' '}
                <span style={{ color: 'var(--color-success,#22c55e)', fontWeight: 600 }}>Toward Negative (−)</span>{' '}
                — decreases risk estimate.
              </p>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Feature</th>
                      <th>Patient Value</th>
                      <th>SHAP Contribution</th>
                      <th>Direction</th>
                      <th>Impact Bar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.feature_ranking.map((item, i) => {
                      const signed = Number(item.contribution ?? 0);
                      const abs    = Number(item.abs_contribution ?? 0);
                      const isPos  = signed >= 0;
                      const pct    = Math.min(100, abs * 400).toFixed(1);
                      return (
                        <tr key={i}>
                          <td className="text-muted">{i + 1}</td>
                          <td><strong>{featureLabel(item.feature)}</strong></td>
                          <td><span className="badge badge-neutral">{item.value != null ? String(item.value) : '—'}</span></td>
                          <td style={{
                            fontFamily: 'monospace',
                            fontWeight: 600,
                            color: isPos ? 'var(--color-danger,#ef4444)' : 'var(--color-success,#22c55e)',
                          }}>
                            {isPos ? '+' : ''}{signed.toFixed(4)}
                          </td>
                          <td>
                            <span className={`badge ${isPos ? 'badge-danger' : 'badge-success'}`} style={{ fontSize: '0.75rem' }}>
                              {isPos ? 'Toward Positive (+)' : 'Toward Negative (−)'}
                            </span>
                          </td>
                          <td>
                            <div className="xai-bar-track">
                              <div className="xai-bar-fill" style={{
                                width: `${pct}%`,
                                background: isPos
                                  ? 'linear-gradient(90deg,#f97316,#ef4444)'
                                  : 'linear-gradient(90deg,#22c55e,#16a34a)',
                              }} />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
