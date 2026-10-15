import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Brain, Download, RefreshCw, ArrowLeft, CheckCircle2,
  AlertTriangle, Loader, BarChart2, Zap
} from 'lucide-react';
import { predictionsApi, xaiApi } from '../api';

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

const featureLabel = (name) => FEATURE_LABELS[String(name).toLowerCase()] || name;

const formatLimeDescription = (desc, feature) => {
  if (!desc) return featureLabel(feature);
  let formatted = desc;
  Object.keys(FEATURE_LABELS).forEach((key) => {
    const regex = new RegExp(`\\b${key}\\b`, 'gi');
    formatted = formatted.replace(regex, FEATURE_LABELS[key]);
  });
  return formatted;
};

const formatFeatureValue = (value) => {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return value == null ? '-' : String(value);
};

export const XAIReport = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [prediction, setPrediction] = useState(null);
  const [report, setReport] = useState(null);
  const [loadingPred, setLoadingPred] = useState(true);
  const [loadingXAI, setLoadingXAI] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

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
      link.setAttribute('download', `FedPedia_XAI_Report_${id.substring(0, 8)}.pdf`);
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
    return (
      <div className="flex-1 flex items-center justify-center p-space-xl text-outline">
        <div className="flex items-center gap-3">
          <Loader size={24} className="animate-spin text-primary" />
          <span className="font-title-sm text-title-sm">Loading Clinical Prediction Telemetry...</span>
        </div>
      </div>
    );
  }

  const isHighRisk = prediction?.risk_level === 'high';
  const isModRisk = prediction?.risk_level === 'moderate';

  return (
    <div className="flex flex-col w-full relative min-h-screen">
      <div className="px-space-md sm:px-margin lg:px-margin-desktop py-space-lg flex flex-col gap-space-lg">
        {/* Top Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-md">
            <button
              onClick={() => navigate(-1)}
              className="w-10 h-10 rounded-xl bg-surface-container-low hover:bg-surface-container-high flex items-center justify-center text-on-surface transition-colors cursor-pointer border border-surface-container-high/60"
              title="Return"
              type="button"
            >
              <ArrowLeft size={18} />
            </button>
            <div className="flex flex-col">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-label-sm text-label-sm bg-secondary-fixed/50 text-secondary uppercase px-2.5 py-0.5 rounded-full font-bold">
                  Explainable AI (XAI) Engine
                </span>
                <span className="text-outline">•</span>
                <span className="font-code-telemetry text-code-telemetry text-outline text-xs">
                  Prediction #{id.substring(0, 8)}
                </span>
              </div>
              <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight flex items-center gap-2">
                <Brain size={24} className="text-primary inline-block" />
                <span>Diagnostic Explainability Report</span>
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-space-sm flex-wrap">
            {report && (
              <button
                onClick={handleDownloadPDF}
                className="px-space-md py-2.5 rounded-xl font-title-sm text-title-sm text-on-surface bg-surface-container-lowest hover:bg-surface-container-low transition-all flex items-center gap-2 border border-surface-container-high/60 cursor-pointer shadow-sm"
                type="button"
              >
                <Download size={16} className="text-primary" />
                <span>Download PDF</span>
              </button>
            )}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="px-space-lg py-2.5 rounded-xl font-title-sm text-title-sm text-on-primary bg-gradient-to-r from-primary to-secondary hover:shadow-lg transition-all flex items-center gap-2 cursor-pointer shadow-md disabled:opacity-75"
              type="button"
            >
              {generating ? (
                <>
                  <Loader size={16} className="animate-spin" />
                  <span>Generating…</span>
                </>
              ) : (
                <>
                  <RefreshCw size={16} />
                  <span>{report ? 'Re-generate' : 'Generate Report'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-error-container/60 text-error flex items-center gap-2 font-body-sm border border-error/30 animate-fade-in">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* Prediction Summary Hero Card */}
        {prediction && (
          <div className="bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
            <div className="flex items-center justify-between pb-2 border-b border-surface-container-high/40">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                  vital_signs
                </span>
                <h2 className="font-title-md text-title-md text-on-surface">Cardiovascular Inference Summary</h2>
              </div>
              <span className="font-code-telemetry text-code-telemetry text-tertiary px-2.5 py-0.5 rounded-full bg-tertiary-fixed/30 font-bold">
                Paillier Homomorphic Attestation
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-space-md">
              <div className="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Dataset</span>
                <span className="font-title-md text-title-md text-on-surface mt-1 capitalize">
                  {prediction.dataset_type?.replace('_', ' ') || 'Heart Disease'}
                </span>
              </div>

              <div className="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Risk Level</span>
                <span className={`font-title-md text-title-md mt-1 font-bold ${isHighRisk ? 'text-error' : isModRisk ? 'text-secondary' : 'text-tertiary'}`}>
                  {prediction.risk_level?.toUpperCase()}
                </span>
              </div>

              <div className="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Probability</span>
                <span className="font-headline-sm text-headline-sm text-primary font-bold mt-0.5">
                  {prediction.probability != null ? `${(prediction.probability * 100).toFixed(1)}%` : '—'}
                </span>
              </div>

              <div className="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Outcome</span>
                <span className="font-title-md text-title-md text-on-surface mt-1 flex items-center gap-1 font-semibold">
                  <span className={`material-symbols-outlined text-base ${prediction.prediction === 1 ? 'text-error' : 'text-tertiary'}`}>
                    {prediction.prediction === 1 ? 'warning' : 'check_circle'}
                  </span>
                  <span>{prediction.prediction ? 'Positive (Disease)' : 'Negative (No Disease)'}</span>
                </span>
              </div>
            </div>

            {/* Doctor Notes if present */}
            {prediction.doctor_notes && (
              <div className="p-space-sm rounded-xl bg-surface-container-low flex items-start gap-2 border border-surface-container-high/40">
                <span className="material-symbols-outlined text-secondary text-lg mt-0.5">stethoscope</span>
                <div className="flex flex-col">
                  <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Doctor Notes</span>
                  <span className="font-body-md text-body-md text-on-surface font-medium">{prediction.doctor_notes}</span>
                </div>
              </div>
            )}

            {/* Model Proof & Verification Panel */}
            <div className="p-space-sm rounded-xl bg-surface-container-low/60 flex flex-col gap-space-sm border border-surface-container-high/40">
              <div className="flex items-center gap-2 text-tertiary font-title-sm text-title-sm font-semibold">
                <CheckCircle2 size={16} />
                <span>Fresh model inference completed</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 font-code-telemetry text-xs">
                <div>
                  <span className="text-outline uppercase text-[10px] block">Prediction ID</span>
                  <span className="text-on-surface font-mono">{prediction.id}</span>
                </div>
                <div>
                  <span className="text-outline uppercase text-[10px] block">Model Record</span>
                  <span className="text-on-surface font-mono">{prediction.global_model_id || '-'}</span>
                </div>
                <div>
                  <span className="text-outline uppercase text-[10px] block">Model Source</span>
                  <span className="text-on-surface capitalize">{prediction.model_source?.replace('_', ' ') || '-'}</span>
                </div>
              </div>

              {/* Feature Vector Sent To Model */}
              <div className="mt-2 flex flex-col gap-2">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">
                  Feature Vector Sent To Model
                </span>
                {prediction.input_features && Object.keys(prediction.input_features).length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-2">
                    {Object.entries(prediction.input_features).map(([name, value]) => (
                      <div key={name} className="p-2 rounded-xl bg-surface-container-lowest flex flex-col border border-surface-container-high/40">
                        <span className="font-label-sm text-[11px] text-on-surface-variant truncate">{featureLabel(name)}</span>
                        <strong className="font-title-sm text-title-sm text-on-surface font-semibold">{formatFeatureValue(value)}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-outline text-xs">No model input vector was stored for this prediction.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* XAI Analytics Cards */}
        {loadingXAI ? (
          <div className="py-14 text-center text-outline flex items-center justify-center gap-2">
            <Loader size={20} className="animate-spin text-primary" />
            <span>Loading report…</span>
          </div>
        ) : !report ? (
          <div className="bg-surface-container-lowest rounded-2xl p-space-xl shadow-sm flex flex-col items-center justify-center text-center gap-space-sm border border-surface-container-high/60">
            <Brain size={48} className="text-secondary" />
            <h3 className="font-headline-sm text-headline-sm text-on-surface">No XAI Report Yet</h3>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
              Click <strong>Generate Report</strong> to run SHAP and LIME analysis for this prediction.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-space-lg">
            {/* Status banner */}
            <div className={`p-3.5 rounded-xl flex items-center gap-2 font-body-sm border ${
              report.status === 'completed'
                ? 'bg-tertiary-fixed/30 text-tertiary border-tertiary/30'
                : 'bg-error-container/40 text-error border-error/30'
            }`}>
              {report.status === 'completed' ? (
                <>
                  <CheckCircle2 size={16} />
                  <span>Report completed successfully.</span>
                </>
              ) : (
                <>
                  <AlertTriangle size={16} />
                  <span>Report status: {report.status}</span>
                </>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
              {/* Left 6 cols: SHAP Global Importance */}
              <div className="lg:col-span-6 flex flex-col gap-space-md bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm border border-surface-container-high/60">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BarChart2 size={18} className="text-primary" />
                    <h3 className="font-title-md text-title-md text-on-surface">SHAP — Global Feature Importance</h3>
                  </div>
                  <span className="font-label-sm text-label-sm bg-primary-fixed/50 text-primary px-2.5 py-0.5 rounded-full font-bold">
                    Kernel Explainer
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Top features driving overall model predictions:
                </p>

                {report.top_shap_features?.length > 0 ? (
                  <div className="overflow-x-auto w-full mt-2">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-surface-container-low/70 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider border-b border-surface-container-high/60">
                          <th className="py-2.5 px-3">#</th>
                          <th className="py-2.5 px-3">Feature</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-container-low font-body-sm text-body-sm">
                        {report.top_shap_features.map((feat, i) => (
                          <tr key={i} className="hover:bg-surface-container-low/30 transition-colors">
                            <td className="py-2.5 px-3 text-outline font-code-telemetry text-xs">{i + 1}</td>
                            <td className="py-2.5 px-3">
                              <span className="font-title-sm text-title-sm text-on-surface font-semibold bg-surface-container-low px-2.5 py-1 rounded-lg inline-block">
                                {featureLabel(feat)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-outline text-center py-4">No SHAP features available.</p>
                )}
              </div>

              {/* Right 6 cols: LIME Local Feature Conditions */}
              <div className="lg:col-span-6 flex flex-col gap-space-md bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm border border-surface-container-high/60">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap size={18} className="text-secondary" />
                    <h3 className="font-title-md text-title-md text-on-surface">LIME — Local Feature Conditions</h3>
                  </div>
                  <span className="font-label-sm text-label-sm bg-secondary-fixed/50 text-secondary px-2.5 py-0.5 rounded-full font-bold">
                    Local Surrogate
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Rule conditions for this prediction.{' '}
                  <span className="text-error font-bold">+ Toward Positive</span>{' '}|{' '}
                  <span className="text-tertiary font-bold">− Toward Negative</span>
                </p>

                {report.local_contributions?.length > 0 ? (
                  <div className="overflow-x-auto w-full mt-2">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-surface-container-low/70 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider border-b border-surface-container-high/60">
                          <th className="py-2 px-2.5">#</th>
                          <th className="py-2 px-2.5">Feature Condition</th>
                          <th className="py-2 px-2.5">Dir</th>
                          <th className="py-2 px-2.5">Impact</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-container-low font-body-sm text-body-sm">
                        {report.local_contributions.slice(0, 9).map((item, i) => {
                          const signed = Number(item.contribution ?? 0);
                          const abs = Number(item.abs_contribution ?? 0);
                          const isPos = signed >= 0;
                          const pct = Math.min(100, Math.max(10, abs * 400)).toFixed(1);

                          return (
                            <tr key={i} className="hover:bg-surface-container-low/30 transition-colors">
                              <td className="py-2.5 px-2.5 text-outline font-code-telemetry text-xs">{i + 1}</td>
                              <td className="py-2.5 px-2.5 font-medium text-on-surface text-xs sm:text-sm">
                                {formatLimeDescription(item.description, item.feature)}
                              </td>
                              <td className="py-2.5 px-2.5 whitespace-nowrap">
                                <span className={`font-label-sm text-xs font-bold ${isPos ? 'text-error' : 'text-tertiary'}`}>
                                  {isPos ? '+ Toward Positive' : '− Toward Negative'}
                                </span>
                              </td>
                              <td className="py-2.5 px-2.5 w-28">
                                <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      isPos
                                        ? 'bg-gradient-to-r from-secondary to-error'
                                        : 'bg-gradient-to-r from-tertiary to-tertiary-container'
                                    }`}
                                    style={{ width: `${pct}%` }}
                                  ></div>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-outline text-center py-4">No LIME features available.</p>
                )}
              </div>
            </div>

            {/* Full SHAP Feature Ranking Table */}
            {report.feature_ranking?.length > 0 && (
              <div className="flex flex-col gap-space-md bg-surface-container-lowest rounded-2xl p-space-lg shadow-sm border border-surface-container-high/60">
                <div className="flex items-center justify-between">
                  <h3 className="font-title-md text-title-md text-on-surface">Full SHAP Feature Ranking — Signed Contributions</h3>
                  <span className="font-code-telemetry text-code-telemetry text-outline text-xs">
                    {report.feature_ranking.length} Features Evaluated
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  <span className="text-error font-bold">Toward Positive (+)</span> — increases risk estimate.{' '}
                  <span className="text-tertiary font-bold">Toward Negative (−)</span> — decreases risk estimate.
                </p>

                <div className="overflow-x-auto w-full mt-2">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-surface-container-low/70 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider border-b border-surface-container-high/60">
                        <th className="py-2.5 px-3">Rank</th>
                        <th className="py-2.5 px-3">Feature</th>
                        <th className="py-2.5 px-3">Patient Value</th>
                        <th className="py-2.5 px-3">SHAP Contribution</th>
                        <th className="py-2.5 px-3">Direction</th>
                        <th className="py-2.5 px-3">Impact Bar</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-container-low font-body-sm text-body-sm">
                      {report.feature_ranking.map((item, i) => {
                        const signed = Number(item.contribution ?? 0);
                        const abs = Number(item.abs_contribution ?? 0);
                        const isPos = signed >= 0;
                        const pct = Math.min(100, Math.max(8, abs * 400)).toFixed(1);

                        return (
                          <tr key={i} className="hover:bg-surface-container-low/30 transition-colors">
                            <td className="py-3 px-3 text-outline font-code-telemetry text-xs">{i + 1}</td>
                            <td className="py-3 px-3">
                              <strong className="font-title-sm text-title-sm text-on-surface font-semibold">
                                {featureLabel(item.feature)}
                              </strong>
                            </td>
                            <td className="py-3 px-3">
                              <span className="font-code-telemetry text-xs bg-surface-container-low px-2 py-0.5 rounded text-on-surface">
                                {item.value != null ? String(item.value) : '—'}
                              </span>
                            </td>
                            <td className={`py-3 px-3 font-code-telemetry font-bold text-xs ${isPos ? 'text-error' : 'text-tertiary'}`}>
                              {isPos ? '+' : ''}{signed.toFixed(4)}
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-full font-label-sm text-xs font-bold ${
                                  isPos ? 'bg-error-container/40 text-error' : 'bg-tertiary-fixed/40 text-tertiary'
                                }`}
                              >
                                {isPos ? 'Toward Positive (+)' : 'Toward Negative (−)'}
                              </span>
                            </td>
                            <td className="py-3 px-3 w-36">
                              <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    isPos
                                      ? 'bg-gradient-to-r from-secondary to-error'
                                      : 'bg-gradient-to-r from-tertiary to-tertiary-container'
                                  }`}
                                  style={{ width: `${pct}%` }}
                                ></div>
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
    </div>
  );
};
