import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Eye, Download, Trash2 } from 'lucide-react';
import { predictionsApi, xaiApi } from '../api';
import './TablePages.css';

export const Predictions = () => {
  const navigate = useNavigate();
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        const { data } = await predictionsApi.list();
        setPredictions(data.items || []);
      } catch (err) {
        console.error('Failed to fetch predictions', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPredictions();
  }, []);

  const downloadReport = (id) => {
    window.open(xaiApi.downloadPdfUrl(id), '_blank');
  };

  const deletePrediction = async (id) => {
    const confirmed = window.confirm('Delete this saved prediction?');
    if (!confirmed) {
      return;
    }
    setDeletingId(id);
    setError('');
    try {
      await predictionsApi.delete(id);
      setPredictions(prev => prev.filter(prediction => prediction.id !== id));
    } catch (err) {
      setError(
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to delete prediction.'
      );
    } finally {
      setDeletingId('');
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1><FileText size={24} style={{ display: 'inline', marginRight: 10, verticalAlign: 'text-bottom' }} /> Predictions</h1>
        <p>Prediction history across all datasets.</p>
      </div>

      {error && (
        <div className="inline-error animate-fade-in">{error}</div>
      )}

      <div className="glass-panel content-panel">
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Patient</th>
                <th>Dataset</th>
                <th>Outcome</th>
                <th>Risk Level</th>
                <th>Probability</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="7" className="text-center">Loading predictions...</td></tr>
              ) : predictions.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center text-muted">
                    No predictions found. Open Patients and click Predict to run disease detection.
                  </td>
                </tr>
              ) : (
                predictions.map(p => (
                  <tr key={p.id}>
                    <td>{new Date(p.created_at).toLocaleString()}</td>
                    <td><span className="text-monospace text-muted">{p.patient_id.substring(0, 8)}...</span></td>
                    <td><span className="badge badge-neutral">{p.dataset_type.replace('_', ' ')}</span></td>
                    <td>{p.prediction === 1 ? 'Disease detected' : 'No disease detected'}</td>
                    <td>
                      <span className={`badge ${p.risk_level === 'high' ? 'badge-danger' : p.risk_level === 'moderate' ? 'badge-warning' : 'badge-success'}`}>
                        {p.risk_level.toUpperCase()}
                      </span>
                    </td>
                    <td>{(p.probability * 100).toFixed(1)}%</td>
                    <td>
                      <div className="action-buttons">
                        <button className="icon-btn" title="View XAI Report" onClick={() => navigate(`/predictions/${p.id}/xai`)}>
                          <Eye size={16} />
                        </button>
                        <button className="icon-btn" title="Download Report" onClick={() => downloadReport(p.id)}>
                          <Download size={16} />
                        </button>
                        <button
                          className="icon-btn danger"
                          title="Delete prediction"
                          aria-label="Delete prediction"
                          onClick={() => deletePrediction(p.id)}
                          disabled={deletingId === p.id}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
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
