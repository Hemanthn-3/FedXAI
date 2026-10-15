import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Download, Trash2 } from 'lucide-react';
import { predictionsApi, xaiApi } from '../api';

const CLINICAL_AVATARS = [
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCt-XHr9d6Zwjwjopap-LvVbQa_NHvwfUManHNYmhBO52v723LjyVnkNlKOMACbx1voc0OWfNcfwZXlcMn7TWpSsElZTUVhlCWTVWmFaxDto93mRS-MBIGp4WIqZ0qCvRQn4IgrQtWIBy7EOtqR6f34e8SaVJW6XALbkdbMo914tYLPo9AIyL_3Lk_bvM3-lPoyKkb_G6gGnOdOvQMLL8ICLGxq4CRXrj-brSdAdfGY6SM0RtqeQ7K4",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCZBCxffuHx91d2V77gHjz8EQ8knMIUpx6zdomhTqiOtrkn31WTPKq2b8yApCxIzsn3SgvOoRVNpTh7GShfrwDABS5rhO4DA3yfCPq8RXjBjLvYgaFjAuyuGt2rryJUA3W3t0ANueVgXh-4UvFeo61SebphMOTJeCLoVuO67Nf9FwdqiQpWRmuwcAHsEU0MpmHXqq4qUOwFOl8STS9YkGa70Nr3I_lDxlRs9SyPq7raWKxiAhZCnwQr",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBBfmUEXyJ5pJI-RoEug3m1S21x84JjcTzWDGR-0srW25uK7H2CKLt4oI8BOHAv8ezL24T7vHQOH-dBWR03vr8Z5t7biTNNhJg0oE8OQvE7mruIh901WZF99tENQPsuAH1ZmsAysrT18fdqQ-2_pq2tAzKzV3qNtKuRQ1shyRXs_Adqcw7D86Hm3FcRmzRiwgUaTvx-lPjkieW0DKOi8AiNBBkNiVhIcqrQgR_RoW7QXS76ve54hHKy",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBuCNze30F57aqJT4COBMgZ8QUT4jvGg_qPUcmHtWOmU2hD8WBKI57oH0jwZQxpnfeq-n2mogXkJajDpP6vEkXIplP2Penbl1TYjBPYF3xn7YmTk0scDjHtWSpYIGFNLPMwQDT-J6PXtlhkW99jPxKiv5Y9w8LXYdqJKdIVWKWR37vtaZ09tI8Y3yDiUNVjLsLbdKNkWHXsM5BlqpODH8K1t-Ql3dDujsdEsKwcL-VEaiFwcZLf4WsE",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBDzf9R7e4o8ACowDZwKymX7I4FYqlfk9X2Ud2zMFNMW2ktj7a6oV3pb11VhU1IhEzmXEP7M_pNIWy8EWbgGP-Ms1dijCxkurQItHCDXU3hLQkVwhIHo1QCod6zQwJoPzjPGr3zlVzNZ4LSCh4lGbInABnVha9adD2viHjWjNzFuB6Or1PhjeRLSfK514vKuOYKdbiWTPj9b12QIFPCoJQ59K5Uz0vNTJvfrLV0Hp8jWPcd3nNMdNML"
];

export const Predictions = () => {
  const navigate = useNavigate();
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');

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
    if (!window.confirm('Delete this saved prediction?')) return;
    setDeletingId(id);
    setError('');
    try {
      await predictionsApi.delete(id);
      setPredictions(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to delete prediction.');
    } finally {
      setDeletingId('');
    }
  };

  const filteredPredictions = predictions.filter(p => {
    const matchSearch = !search || p.patient_id?.toLowerCase().includes(search.toLowerCase()) || p.id.toLowerCase().includes(search.toLowerCase());
    if (!matchSearch) return false;
    if (filter === 'high') return p.risk_level === 'high';
    if (filter === 'moderate') return p.risk_level === 'moderate';
    if (filter === 'low') return p.risk_level === 'low';
    return true;
  });

  const highRiskCount = predictions.filter(p => p.risk_level === 'high').length;

  return (
    <div className="flex flex-col w-full relative min-h-screen">
      <div className="px-space-md sm:px-margin lg:px-margin-desktop py-space-lg flex flex-col gap-space-lg">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md">
          <div className="flex flex-col max-w-2xl">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container-high text-primary font-label-sm text-label-sm tracking-wider uppercase font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                Inference Engine v4.2
              </span>
              <span className="text-outline-variant">•</span>
              <span className="font-code-telemetry text-code-telemetry text-on-surface-variant font-medium">
                Differential Privacy Guaranteed
              </span>
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
              Clinical Predictions &amp; XAI History
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant mt-1">
              Decentralized AI inference logs, cardiovascular risk classifications, and explainable feature-attribution reports.
            </p>
          </div>

          <div className="flex items-center gap-space-sm flex-wrap">
            <div className="bg-surface-container-lowest px-space-md py-space-sm rounded-xl shadow-sm flex items-center gap-3 border border-surface-container-high/60">
              <div className="w-10 h-10 rounded-lg bg-surface-container-low flex items-center justify-center text-primary">
                <span className="material-symbols-outlined text-headline-sm">batch_prediction</span>
              </div>
              <div>
                <div className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Predictions</div>
                <div className="font-headline-sm text-headline-sm text-on-surface">{predictions.length}</div>
              </div>
            </div>

            <div className="bg-surface-container-lowest px-space-md py-space-sm rounded-xl shadow-sm flex items-center gap-3 border border-surface-container-high/60">
              <div className="w-10 h-10 rounded-lg bg-error-container/40 flex items-center justify-center text-error">
                <span className="material-symbols-outlined text-headline-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                  warning
                </span>
              </div>
              <div>
                <div className="font-label-sm text-label-sm uppercase tracking-wider text-error font-bold">High Risk</div>
                <div className="font-headline-sm text-headline-sm text-error">{highRiskCount} Cases</div>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-error-container/60 text-error flex items-center gap-2 font-body-sm border border-error/30 animate-fade-in">
            <span className="material-symbols-outlined text-title-sm">error</span>
            <span>{error}</span>
          </div>
        )}

        {/* Action & Filter Deck */}
        <div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-space-md">
            <div className="relative flex-1 w-full sm:max-w-md">
              <span className="material-symbols-outlined absolute left-3.5 top-3 text-on-surface-variant text-lg">search</span>
              <input
                type="text"
                className="w-full h-11 pl-10 pr-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="Search by Patient MRN or Prediction UUID..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto">
              <button
                onClick={() => setFilter('all')}
                className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm cursor-pointer transition-all ${
                  filter === 'all'
                    ? 'bg-primary text-on-primary shadow-sm font-bold'
                    : 'bg-surface-container-low text-on-surface-variant hover:text-on-surface'
                }`}
              >
                All Records ({predictions.length})
              </button>
              <button
                onClick={() => setFilter('high')}
                className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm cursor-pointer transition-all ${
                  filter === 'high'
                    ? 'bg-error text-on-error shadow-sm font-bold'
                    : 'bg-surface-container-low text-on-surface-variant hover:text-error'
                }`}
              >
                High Risk
              </button>
              <button
                onClick={() => setFilter('moderate')}
                className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm cursor-pointer transition-all ${
                  filter === 'moderate'
                    ? 'bg-secondary text-on-secondary shadow-sm font-bold'
                    : 'bg-surface-container-low text-on-surface-variant hover:text-secondary'
                }`}
              >
                Moderate Risk
              </button>
              <button
                onClick={() => setFilter('low')}
                className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm cursor-pointer transition-all ${
                  filter === 'low'
                    ? 'bg-tertiary text-on-tertiary shadow-sm font-bold'
                    : 'bg-surface-container-low text-on-surface-variant hover:text-tertiary'
                }`}
              >
                Low Risk
              </button>
            </div>
          </div>
        </div>

        {/* Table Panel */}
        <div className="bg-surface-container-lowest rounded-2xl shadow-[0_4px_24px_rgba(0,26,66,0.04)] overflow-hidden flex flex-col border border-surface-container-high/60">
          <div className="overflow-x-auto w-full">
            <table className="w-full text-left border-collapse min-w-[960px]">
              <thead>
                <tr className="bg-surface-container-low/70 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider select-none border-b border-surface-container-high/60">
                  <th className="py-3.5 px-space-md font-bold">Inference Date</th>
                  <th className="py-3.5 px-space-md font-bold">Patient / MRN</th>
                  <th className="py-3.5 px-space-md font-bold">Dataset / Protocol</th>
                  <th className="py-3.5 px-space-md font-bold">Diagnostic Classification</th>
                  <th className="py-3.5 px-space-md font-bold">Risk Stratification</th>
                  <th className="py-3.5 px-space-md font-bold">Probability</th>
                  <th className="py-3.5 px-space-md font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-body-md">
                {loading ? (
                  <tr>
                    <td colSpan="7" className="py-12 text-center text-outline">
                      Loading predictions...
                    </td>
                  </tr>
                ) : filteredPredictions.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="py-14 text-center text-outline">
                      No predictions found.
                    </td>
                  </tr>
                ) : (
                  filteredPredictions.map((p, idx) => {
                    const avatar = CLINICAL_AVATARS[idx % CLINICAL_AVATARS.length];
                    const isHigh = p.risk_level === 'high';
                    const isMod = p.risk_level === 'moderate';
                    const probPct = (p.probability * 100).toFixed(1);

                    return (
                      <tr key={p.id} className="group hover:bg-surface-container-low/40 transition-colors">
                        <td className="py-4 px-space-md">
                          <div className="flex flex-col">
                            <span className="font-title-sm text-title-sm text-on-surface">
                              {new Date(p.created_at).toLocaleDateString()}
                            </span>
                            <span className="font-code-telemetry text-code-telemetry text-outline text-xs">
                              {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex items-center gap-3">
                            <img
                              alt="Patient Avatar"
                              src={avatar}
                              className="w-9 h-9 rounded-full object-cover ring-2 ring-surface-container-highest"
                            />
                            <div className="flex flex-col">
                              <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                                {p.patient_id.substring(0, 8)}...
                              </span>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-label-sm text-label-sm bg-surface-container-high text-on-surface font-semibold">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                            {p.dataset_type?.replace('_', ' ') || 'Heart Disease'}
                          </span>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`material-symbols-outlined text-base ${
                                p.prediction === 1 ? 'text-error' : 'text-tertiary'
                              }`}
                              style={{ fontVariationSettings: "'FILL' 1" }}
                            >
                              {p.prediction === 1 ? 'coronavirus' : 'check_circle'}
                            </span>
                            <span className="font-title-sm text-title-sm text-on-surface">
                              {p.prediction === 1 ? 'Disease detected' : 'No disease detected'}
                            </span>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <div
                            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-title-sm text-title-sm font-bold ${
                              isHigh
                                ? 'bg-error-container/40 text-error'
                                : isMod
                                ? 'bg-secondary-fixed/40 text-secondary'
                                : 'bg-tertiary-fixed/30 text-tertiary'
                            }`}
                          >
                            <span className={`w-2 h-2 rounded-full ${isHigh ? 'bg-error animate-ping' : isMod ? 'bg-secondary' : 'bg-tertiary'}`}></span>
                            <span>{p.risk_level?.toUpperCase()}</span>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex flex-col">
                            <span className="font-title-md text-title-md font-bold text-on-surface">
                              {probPct}%
                            </span>
                            <div className="w-24 bg-surface-container h-1.5 rounded-full mt-1 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  isHigh ? 'bg-error' : isMod ? 'bg-secondary' : 'bg-tertiary'
                                }`}
                                style={{ width: `${Math.min(100, Math.max(10, probPct))}%` }}
                              ></div>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-space-md text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => navigate(`/predictions/${p.id}/xai`)}
                              className="p-2 rounded-xl text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-all cursor-pointer flex items-center justify-center"
                              title="View XAI Report"
                              type="button"
                            >
                              <Eye size={18} />
                            </button>

                            <button
                              onClick={() => downloadReport(p.id)}
                              className="p-2 rounded-xl text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-all cursor-pointer flex items-center justify-center"
                              title="Download Report"
                              type="button"
                            >
                              <Download size={18} />
                            </button>

                            <button
                              onClick={() => deletePrediction(p.id)}
                              disabled={deletingId === p.id}
                              className="p-2 rounded-xl text-outline hover:text-error hover:bg-error-container/40 transition-colors cursor-pointer flex items-center justify-center"
                              title="Delete prediction"
                              type="button"
                            >
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
