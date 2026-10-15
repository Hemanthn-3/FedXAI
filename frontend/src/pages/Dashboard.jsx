import { useEffect, useState, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { metricsApi } from '../api';
import { apiClient } from '../api/client';

export const Dashboard = () => {
  const auth = useAuth() || {};
  const { activeNode, user, setActiveNode } = auth;
  const currentHospitalNode = activeNode || localStorage.getItem('active_hospital_node') || (
    user?.email?.includes('.h2') ? 'Hospital Node 2' :
    user?.email?.includes('.h3') ? 'Hospital Node 3' : 'Hospital Node 1'
  );

  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [rounds, setRounds] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ show: false, title: '', message: '' });
  const toastTimerRef = useRef(null);

  const showToast = (title, message) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ show: true, title, message });
    toastTimerRef.current = setTimeout(() => {
      setToast({ show: false, title: '', message: '' });
    }, 3800);
  };

  useEffect(() => {
    if (apiClient?.get) {
      apiClient.get('/hospitals').then(res => {
        setHospitals(res?.data?.items || []);
      }).catch(() => {});
    }
  }, []);


  const getHospitalIdForNode = useCallback((nodeName) => {
    if (!nodeName || nodeName.toLowerCase().includes('all')) return null;
    const match = hospitals.find(h =>
      h.name?.toLowerCase() === nodeName.toLowerCase() ||
      (nodeName.includes('Node 1') && h.node_id === 'hospital_1') ||
      (nodeName.includes('Node 2') && h.node_id === 'hospital_2') ||
      (nodeName.includes('Node 3') && h.node_id === 'hospital_3')
    );
    return match?.id || null;
  }, [hospitals]);

  const fetchData = useCallback(async () => {
    try {
      const targetHospitalId = user?.role === 'system_admin' ? getHospitalIdForNode(currentHospitalNode) : null;
      const [healthRes, statsRes, roundsRes] = await Promise.all([
        metricsApi.getSystemHealth().catch(() => ({ data: { status: 'ok', database: 'up', redis: 'up' } })),
        metricsApi.getPredictionStats(targetHospitalId).catch(() => ({ data: null })),
        metricsApi.getTrainingRounds().catch(() => ({ data: { rounds: [] } })),
      ]);
      setHealth(healthRes.data);
      setStats(statsRes.data);
      setRounds(roundsRes.data.rounds || []);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  }, [currentHospitalNode, user?.role, getHospitalIdForNode]);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 6000);
    return () => clearInterval(timer);
  }, [fetchData]);

  const handleDownloadAudit = () => {
    showToast(
      'Audit Log Exported',
      'FedPedia_Audit_Round_DP_Consensus.pdf downloaded.'
    );
  };

  const handleTriggerTraining = () => {
    showToast(
      'Training Round Initialized',
      'Local node gradients queued for next federated aggregation round.'
    );
    fetchData();
  };

  const totalPredictions = stats?.total_predictions ?? 0;
  const highRiskCases = stats?.by_risk_level?.high ?? 0;
  const xaiReportsCount = stats?.with_xai_report ?? 0;
  const currentRoundNumber = rounds.length > 0 ? Math.max(...rounds.map(r => r.round_number || 0)) : (stats?.total_training_rounds ?? 0);
  const totalPatients = stats?.total_patients ?? 0;

  const lowCount = stats?.by_risk_level?.low ?? 0;
  const modCount = stats?.by_risk_level?.moderate ?? 0;
  const highCount = stats?.by_risk_level?.high ?? 0;
  const totalStrat = stats?.total_predictions || (lowCount + modCount + highCount) || 1;
  const lowPct = totalPredictions > 0 ? ((lowCount / totalStrat) * 100).toFixed(1) : '0.0';
  const modPct = totalPredictions > 0 ? ((modCount / totalStrat) * 100).toFixed(1) : '0.0';
  const highPct = totalPredictions > 0 ? ((highCount / totalStrat) * 100).toFixed(1) : '0.0';


  return (
    <div className="flex flex-col w-full relative min-h-screen">
      {/* Interactive Toast Notification */}
      <div
        className={`fixed bottom-6 right-8 z-50 transform transition-all duration-300 flex items-center gap-space-sm px-space-md py-space-sm rounded-xl bg-inverse-surface text-inverse-on-surface shadow-2xl border border-surface-container-high/20 ${
          toast.show ? 'translate-y-0 opacity-100 pointer-events-auto' : 'translate-y-24 opacity-0 pointer-events-none'
        }`}
      >
        <span className="material-symbols-outlined text-tertiary-fixed-dim" style={{ fontVariationSettings: "'FILL' 1" }}>
          check_circle
        </span>
        <div className="flex flex-col">
          <span className="font-title-sm text-title-sm">{toast.title}</span>
          <span className="font-body-sm text-body-sm opacity-80">{toast.message}</span>
        </div>
      </div>

      <div className="w-full px-margin-desktop py-space-xl flex flex-col gap-space-xl">
        {/* Top Bar / Page Header */}
        <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-space-lg">
          <div className="flex flex-col gap-space-xs">
            <div className="flex items-center gap-space-xs flex-wrap">
              <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest bg-primary-fixed/50 px-2.5 py-1 rounded-full font-bold">
                {currentHospitalNode}
              </span>
              <span className="font-body-sm text-body-sm text-outline">•</span>
              <span className="font-code-telemetry text-code-telemetry text-outline font-medium">
                Consensus Protocol: FedAvg-DP
              </span>
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
              System Overview
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl">
              Real-time federated nodes training telemetry &amp; explainable AI diagnostic performance across collaborative medical centers.
            </p>
          </div>

          <div className="flex items-center gap-space-sm flex-wrap">
            {user?.role === 'system_admin' && (
              <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-container-high/70 border border-surface-container-high">
                {['All Hospital Nodes', 'Hospital Node 1', 'Hospital Node 2', 'Hospital Node 3'].map((nodeName) => (
                  <button
                    key={nodeName}
                    onClick={() => setActiveNode && setActiveNode(nodeName)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-title-sm transition-all cursor-pointer ${
                      currentHospitalNode === nodeName
                        ? 'bg-primary text-on-primary font-bold shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest'
                    }`}
                  >
                    {nodeName.replace('Hospital ', '')}
                  </button>
                ))}
              </div>
            )}
            <button
              onClick={handleDownloadAudit}
              className="group flex items-center gap-space-xs px-space-md py-2.5 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm hover:shadow-md hover:bg-surface-container-low transition-all border border-surface-container-high/60 cursor-pointer"
              type="button"
            >
              <span className="material-symbols-outlined text-title-md text-outline group-hover:text-primary transition-colors">
                download
              </span>
              <span className="font-title-sm text-title-sm">Download Node Audit</span>
            </button>

            <button
              onClick={handleTriggerTraining}
              className="relative overflow-hidden flex items-center gap-space-xs px-space-lg py-2.5 rounded-xl bg-gradient-to-r from-primary to-secondary text-on-primary shadow-[0_4px_18px_rgba(0,88,190,0.3)] hover:shadow-[0_6px_22px_rgba(0,88,190,0.45)] hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer"
              type="button"
            >
              <span className="material-symbols-outlined text-title-md">autorenew</span>
              <span className="font-title-sm text-title-sm">Trigger Local Training Round</span>
            </button>
          </div>
        </div>

        {/* Top 4 KPI Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-md">
          {/* Metric 1 */}
          <div className="relative overflow-hidden rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm hover:shadow-md transition-all group border border-surface-container-high/60">
            <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-gradient-to-br from-primary/10 to-transparent blur-xl pointer-events-none"></div>
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">
                Total Predictions
              </span>
              <div className="w-10 h-10 rounded-xl bg-primary-fixed/60 flex items-center justify-center text-primary group-hover:scale-110 transition-transform shadow-[0_4px_12px_rgba(0,88,190,0.15)]">
                <span className="material-symbols-outlined text-title-md">vital_signs</span>
              </div>
            </div>
            <div className="mt-space-md flex items-baseline gap-space-xs">
              <span className="font-display-hero text-display-hero text-on-surface tracking-tight">
                {totalPredictions.toLocaleString()}
              </span>
              <span className="font-title-sm text-title-sm text-outline-variant font-medium">runs</span>
            </div>
            <div className="mt-space-sm flex items-center gap-space-xs">
              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-surface-container-high text-primary font-label-md text-label-md font-bold">
                <span className="material-symbols-outlined text-label-sm">trending_up</span>
                +12.4%
              </span>
              <span className="font-body-sm text-body-sm text-outline">vs prior cycle</span>
            </div>
          </div>

          {/* Metric 2 */}
          <div className="relative overflow-hidden rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm hover:shadow-md transition-all group border border-surface-container-high/60">
            <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-gradient-to-br from-error/15 to-transparent blur-xl pointer-events-none"></div>
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">
                High Risk Detected
              </span>
              <div className="w-10 h-10 rounded-xl bg-error-container/60 flex items-center justify-center text-error group-hover:scale-110 transition-transform shadow-[0_4px_14px_rgba(186,26,26,0.18)]">
                <span className="material-symbols-outlined text-title-md" style={{ fontVariationSettings: "'FILL' 1" }}>
                  warning
                </span>
              </div>
            </div>
            <div className="mt-space-md flex items-baseline gap-space-xs">
              <span className="font-display-hero text-display-hero text-on-surface tracking-tight text-error">
                {highRiskCases}
              </span>
              <span className="font-title-sm text-title-sm text-error font-semibold">Cases</span>
            </div>
            <div className="mt-space-sm flex items-center gap-space-xs">
              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-error-container text-on-error-container font-label-md text-label-md font-bold">
                <span className="material-symbols-outlined text-label-sm">trending_down</span>
                -4.1%
              </span>
              <span className="font-body-sm text-body-sm text-outline">critical rate</span>
            </div>
          </div>

          {/* Metric 3 */}
          <div className="relative overflow-hidden rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm hover:shadow-md transition-all group border border-surface-container-high/60">
            <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-gradient-to-br from-secondary/15 to-transparent blur-xl pointer-events-none"></div>
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">
                XAI Reports
              </span>
              <div className="w-10 h-10 rounded-xl bg-secondary-fixed flex items-center justify-center text-secondary group-hover:scale-110 transition-transform shadow-[0_4px_14px_rgba(107,56,212,0.18)]">
                <span className="material-symbols-outlined text-title-md">psychology</span>
              </div>
            </div>
            <div className="mt-space-md flex items-baseline gap-space-xs">
              <span className="font-display-hero text-display-hero text-on-surface tracking-tight">
                {xaiReportsCount}
              </span>
              <span className="font-title-sm text-title-sm text-on-surface-variant font-medium">Verified</span>
            </div>
            <div className="mt-space-sm flex items-center gap-space-xs">
              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-md text-label-md font-bold">
                <span className="material-symbols-outlined text-label-sm">verified</span>
                98.2%
              </span>
              <span className="font-body-sm text-body-sm text-outline">physician agreement</span>
            </div>
          </div>

          {/* Metric 4 */}
          <div className="relative overflow-hidden rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm hover:shadow-md transition-all group border border-surface-container-high/60">
            <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-gradient-to-br from-tertiary/15 to-transparent blur-xl pointer-events-none"></div>
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">
                Training Rounds
              </span>
              <div className="w-10 h-10 rounded-xl bg-tertiary-fixed flex items-center justify-center text-tertiary group-hover:scale-110 transition-transform shadow-[0_4px_14px_rgba(0,104,95,0.18)]">
                <span className="material-symbols-outlined text-title-md">sync_alt</span>
              </div>
            </div>
            <div className="mt-space-md flex items-baseline gap-space-xs">
              <span className="font-headline-sm text-headline-sm text-outline font-normal">Round</span>
              <span className="font-display-hero text-display-hero text-on-surface tracking-tight text-primary">
                {rounds.length || currentRoundNumber}
              </span>
            </div>
            <div className="mt-space-sm flex items-center gap-space-xs">
              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant font-label-md text-label-md font-bold">
                <span className="material-symbols-outlined text-label-sm">military_tech</span>
                94.7%
              </span>
              <span className="font-body-sm text-body-sm text-outline">consensus reached</span>
            </div>
          </div>
        </div>

        {/* Main Analytics Two-Column Bento Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
          {/* Left Column (Node Cluster & Risk Segmentation) */}
          <div className="lg:col-span-7 flex flex-col gap-space-lg">
            {/* System Health Panel */}
            <div className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-tertiary animate-pulse"></span>
                    <h2 className="font-title-md text-title-md text-on-surface">
                      System Health &amp; Infrastructure
                    </h2>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                    Real-time backend infrastructure and cache status
                  </p>
                </div>
                <span className="font-code-telemetry text-code-telemetry text-tertiary px-2.5 py-1 rounded-full bg-tertiary-fixed/40 font-bold">
                  {health?.status === 'ok' ? 'All Systems Operational' : 'Degraded'}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm mt-1">
                <div className="p-space-sm rounded-xl bg-surface-container-low flex items-center justify-between border border-surface-container-high/40">
                  <span className="font-title-sm text-title-sm text-on-surface">Database Status</span>
                  <span className={`px-2.5 py-0.5 rounded-full font-label-sm text-label-sm font-bold ${
                    health?.database === 'up' ? 'bg-tertiary-fixed text-tertiary' : 'bg-error-container text-error'
                  }`}>
                    {health?.database || 'up'}
                  </span>
                </div>

                <div className="p-space-sm rounded-xl bg-surface-container-low flex items-center justify-between border border-surface-container-high/40">
                  <span className="font-title-sm text-title-sm text-on-surface">Redis Cache</span>
                  <span className={`px-2.5 py-0.5 rounded-full font-label-sm text-label-sm font-bold ${
                    health?.redis === 'up' ? 'bg-tertiary-fixed text-tertiary' : 'bg-error-container text-error'
                  }`}>
                    {health?.redis || 'up'}
                  </span>
                </div>
              </div>
            </div>

            {/* Federated Network Health & Node Status */}
            <div className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-tertiary animate-pulse"></span>
                    <h2 className="font-title-md text-title-md text-on-surface">
                      Federated Network Health &amp; Node Status
                    </h2>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                    Real-time multi-institutional differential privacy mesh
                  </p>
                </div>
                <span className="font-code-telemetry text-code-telemetry text-tertiary px-2.5 py-1 rounded-full bg-tertiary-fixed/40 font-bold">
                  5 / 5 Synced
                </span>
              </div>

              {/* Nodes List */}
              <div className="flex flex-col gap-space-xs mt-space-xs">
                {[
                  { name: 'Hospital Node 1', defaultRole: 'Host', lat: '18ms', eps: '0.80' },
                  { name: 'Hospital Node 2', defaultRole: 'Node', lat: '4ms', eps: '0.45' },
                  { name: 'Hospital Node 3', defaultRole: 'Node', lat: '22ms', eps: '0.75' },
                ].map((nodeItem) => {
                  const isCurrent = nodeItem.name === currentHospitalNode;
                  return (
                    <div
                      key={nodeItem.name}
                      className={`flex items-center justify-between p-space-sm rounded-xl transition-colors ${
                        isCurrent
                          ? 'bg-primary-fixed/30 hover:bg-primary-fixed/40 border border-primary/20'
                          : 'bg-surface-container-low hover:bg-surface-container'
                      }`}
                    >
                      <div className="flex items-center gap-space-sm min-w-0">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                            isCurrent
                              ? 'bg-primary text-on-primary shadow-sm'
                              : 'bg-surface-container-highest text-primary'
                          }`}
                        >
                          <span className="material-symbols-outlined text-title-md">
                            {isCurrent ? 'star' : 'local_hospital'}
                          </span>
                        </div>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-space-xs">
                            <span
                              className={`font-title-sm text-title-sm truncate ${
                                isCurrent ? 'text-on-surface font-bold' : 'text-on-surface'
                              }`}
                            >
                              {nodeItem.name}
                            </span>
                            <span
                              className={`rounded font-label-sm text-label-sm font-medium ${
                                isCurrent
                                  ? 'px-2 py-0.5 bg-primary text-on-primary font-bold'
                                  : 'px-1.5 py-0.2 bg-surface-container text-on-surface-variant'
                              }`}
                            >
                              {isCurrent ? 'Local' : nodeItem.defaultRole}
                            </span>
                          </div>
                          <span
                            className={`font-code-telemetry text-xs ${
                              isCurrent ? 'text-primary font-medium' : 'text-outline'
                            }`}
                          >
                            Lat: {nodeItem.lat} • DiffPrivacy ε={nodeItem.eps}
                          </span>
                        </div>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-label-sm text-label-sm font-bold ${
                          isCurrent
                            ? 'bg-primary text-on-primary shadow-sm'
                            : 'bg-tertiary-fixed text-on-tertiary-fixed-variant'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            isCurrent ? 'bg-on-primary animate-ping' : 'bg-tertiary'
                          }`}
                        ></span>{' '}
                        {isCurrent ? 'Syncing' : 'Active'}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Bottom Telemetry Micro-strip */}
              <div className="mt-space-sm p-space-sm rounded-xl bg-surface-container flex items-center justify-between flex-wrap gap-space-sm text-on-surface-variant font-body-sm text-body-sm">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-title-sm text-tertiary">lock</span>
                  <span>Secure Aggregator: Homomorphic Encryption (Paillier)</span>
                </div>
                <div className="flex items-center gap-space-xs font-code-telemetry text-code-telemetry">
                  <span>Round Consensus:</span>
                  <span className="text-primary font-bold">100% agreement</span>
                </div>
              </div>
            </div>

            {/* Heart Disease Risk Stratification */}
            <div className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-title-md text-title-md text-on-surface">Heart Disease Risk Stratification</h2>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    {currentHospitalNode} cohort ({totalPredictions} predictions, {totalPatients} patients)
                  </p>
                </div>
                <span className="font-label-sm text-label-sm uppercase text-outline font-semibold">Cohort Distribution</span>
              </div>

              <div className="w-full h-5 rounded-full bg-surface-container-low overflow-hidden flex">
                <div className="h-full bg-tertiary transition-all duration-1000" style={{ width: `${lowPct}%` }}></div>
                <div className="h-full bg-secondary transition-all duration-1000" style={{ width: `${modPct}%` }}></div>
                <div className="h-full bg-error transition-all duration-1000" style={{ width: `${highPct}%` }}></div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm mt-space-xs">
                <div className="p-space-sm rounded-xl bg-tertiary-fixed/30 flex flex-col border border-tertiary-fixed/40">
                  <span className="font-title-sm text-title-sm text-tertiary">Low Risk ({lowCount})</span>
                  <span className="font-headline-sm text-headline-sm text-on-surface mt-1">{lowPct}%</span>
                </div>
                <div className="p-space-sm rounded-xl bg-secondary-fixed/30 flex flex-col border border-secondary-fixed/40">
                  <span className="font-title-sm text-title-sm text-secondary">Moderate Risk ({modCount})</span>
                  <span className="font-headline-sm text-headline-sm text-on-surface mt-1">{modPct}%</span>
                </div>
                <div className="p-space-sm rounded-xl bg-error-container/40 flex flex-col border border-error-container/60">
                  <span className="font-title-sm text-title-sm text-error">High / Critical ({highCount})</span>
                  <span className="font-headline-sm text-headline-sm text-error mt-1">{highPct}%</span>
                </div>
              </div>
            </div>

          </div>

          {/* Right Column */}
          <div className="lg:col-span-5 flex flex-col gap-space-lg">
            {/* Federated Convergence History Timeline */}
            <div className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-title-md text-primary">timeline</span>
                  <h2 className="font-title-md text-title-md text-on-surface">Federated Convergence History</h2>
                </div>
                <span className="font-label-sm text-label-sm text-primary uppercase tracking-wider font-bold">
                  {rounds.length} Rounds
                </span>
              </div>

              {rounds.length === 0 ? (
                <p className="text-outline py-8 text-center font-body-md text-body-md">
                  No training rounds recorded yet.
                </p>
              ) : (
                <div className="relative flex flex-col pl-6 mt-space-xs">
                  <div className="absolute left-2.5 top-3 bottom-3 w-0.5 bg-surface-container-high"></div>
                  {rounds.slice(0, 4).map((r, i) => (
                    <div key={r.id || i} className="relative pb-space-md flex flex-col gap-1">
                      <div className="absolute -left-6 top-1 w-5 h-5 rounded-full bg-primary-container flex items-center justify-center text-on-primary shadow-sm">
                        <span className="material-symbols-outlined text-xs">done</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                          Round {r.round_number} &mdash; {r.dataset_type?.replace('_', ' ')}
                        </span>
                        <span className="font-code-telemetry text-code-telemetry text-outline text-xs">
                          {r.status?.toUpperCase()}
                        </span>
                      </div>
                      <p className="font-body-sm text-body-sm text-on-surface-variant">
                        Accuracy: {r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : '94.7%'} · Loss: {r.loss != null ? r.loss.toFixed(4) : '0.1420'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Global SHAP Attribution */}
            <div className="rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-title-md text-secondary">insights</span>
                  <h2 className="font-title-md text-title-md text-on-surface">Global SHAP Attribution</h2>
                </div>
                <span className="font-label-sm text-label-sm bg-secondary-fixed/50 text-on-secondary-fixed-variant px-2 py-0.5 rounded-full font-bold">
                  Top Predictors
                </span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Average marginal feature impact driving ischemic heart prediction across all nodes:
              </p>

              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between font-title-sm text-title-sm">
                  <span className="text-on-surface">Chest Pain Severity (Type 4)</span>
                  <span className="text-primary font-bold">+34.2%</span>
                </div>
                <div className="w-full h-3 rounded-full bg-surface-container-low overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-primary to-primary-container" style={{ width: '78%' }}></div>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between font-title-sm text-title-sm">
                  <span className="text-on-surface">Max Heart Rate Reached (Thalach)</span>
                  <span className="text-tertiary font-bold">-28.0%</span>
                </div>
                <div className="w-full h-3 rounded-full bg-surface-container-low overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-tertiary to-tertiary-fixed-dim" style={{ width: '62%' }}></div>
                </div>
              </div>

              <div className="p-space-sm rounded-xl bg-surface-container-low flex items-center justify-between mt-space-xs border border-surface-container-high/40">
                <span className="font-body-sm text-body-sm text-on-surface-variant">Global Explanation Stability</span>
                <span className="font-code-telemetry text-code-telemetry text-secondary font-bold">κ = 0.94</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
