import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { patientsApi, predictionsApi } from '../api';
import { apiClient } from '../api/client';



const CLINICAL_AVATARS = [
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCt-XHr9d6Zwjwjopap-LvVbQa_NHvwfUManHNYmhBO52v723LjyVnkNlKOMACbx1voc0OWfNcfwZXlcMn7TWpSsElZTUVhlCWTVWmFaxDto93mRS-MBIGp4WIqZ0qCvRQn4IgrQtWIBy7EOtqR6f34e8SaVJW6XALbkdbMo914tYLPo9AIyL_3Lk_bvM3-lPoyKkb_G6gGnOdOvQMLL8ICLGxq4CRXrj-brSdAdfGY6SM0RtqeQ7K4",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCZBCxffuHx91d2V77gHjz8EQ8knMIUpx6zdomhTqiOtrkn31WTPKq2b8yApCxIzsn3SgvOoRVNpTh7GShfrwDABS5rhO4DA3yfCPq8RXjBjLvYgaFjAuyuGt2rryJUA3W3t0ANueVgXh-4UvFeo61SebphMOTJeCLoVuO67Nf9FwdqiQpWRmuwcAHsEU0MpmHXqq4qUOwFOl8STS9YkGa70Nr3I_lDxlRs9SyPq7raWKxiAhZCnwQr",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBBfmUEXyJ5pJI-RoEug3m1S21x84JjcTzWDGR-0srW25uK7H2CKLt4oI8BOHAv8ezL24T7vHQOH-dBWR03vr8Z5t7biTNNhJg0oE8OQvE7mruIh901WZF99tENQPsuAH1ZmsAysrT18fdqQ-2_pq2tAzKzV3qNtKuRQ1shyRXs_Adqcw7D86Hm3FcRmzRiwgUaTvx-lPjkieW0DKOi8AiNBBkNiVhIcqrQgR_RoW7QXS76ve54hHKy",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBuCNze30F57aqJT4COBMgZ8QUT4jvGg_qPUcmHtWOmU2hD8WBKI57oH0jwZQxpnfeq-n2mogXkJajDpP6vEkXIplP2Penbl1TYjBPYF3xn7YmTk0scDjHtWSpYIGFNLPMwQDT-J6PXtlhkW99jPxKiv5Y9w8LXYdqJKdIVWKWR37vtaZ09tI8Y3yDiUNVjLsLbdKNkWHXsM5BlqpODH8K1t-Ql3dDujsdEsKwcL-VEaiFwcZLf4WsE",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBDzf9R7e4o8ACowDZwKymX7I4FYqlfk9X2Ud2zMFNMW2ktj7a6oV3pb11VhU1IhEzmXEP7M_pNIWy8EWbgGP-Ms1dijCxkurQItHCDXU3hLQkVwhIHo1QCod6zQwJoPzjPGr3zlVzNZ4LSCh4lGbInABnVha9adD2viHjWjNzFuB6Or1PhjeRLSfK514vKuOYKdbiWTPj9b12QIFPCoJQ59K5Uz0vNTJvfrLV0Hp8jWPcd3nNMdNML"
];

const DEFAULT_NAMES = [
  "Eleanor Vance",
  "Marcus Chen",
  "Sarah Jenkins",
  "David Ross",
  "Anita Patel",
  "Liam Montgomery",
  "Arthur Pendelton",
  "Clara Oswald",
  "Mateo Gomez",
  "Hannah Abbott"
];

const DEFAULT_WARDS = [
  "Cardiology Ward A",
  "Outpatient Node",
  "Geriatric Care",
  "Cardio Preventive",
  "Inpatient Ward C"
];

export const Patients = () => {
  const navigate = useNavigate();
  const auth = useAuth() || {};
  const { activeNode, user } = auth;
  const currentHospitalNode = activeNode || localStorage.getItem('active_hospital_node') || (
    user?.email?.includes('.h2') ? 'Hospital Node 2' :
    user?.email?.includes('.h3') ? 'Hospital Node 3' : 'Hospital Node 1'
  );

  const [patients, setPatients] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [predictingId, setPredictingId] = useState('');
  const [saving, setSaving] = useState(false);
  const [errorBanner, setErrorBanner] = useState('');
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(5);

  // Form state
  const [formName, setFormName] = useState('Liam Montgomery');
  const [formMrn, setFormMrn] = useState('#PT-13920');
  const [formAge, setFormAge] = useState('45');
  const [formSex, setFormSex] = useState('1'); // 1 = Male, 0 = Female
  const [formCp, setFormCp] = useState('0');
  const [formBp, setFormBp] = useState('120');
  const [formChol, setFormChol] = useState('230');
  const [formFbs, setFormFbs] = useState('0');
  const [formRestecg, setFormRestecg] = useState('0');
  const [formThalach, setFormThalach] = useState('150');
  const [formExang, setFormExang] = useState('0');
  const [formOldpeak, setFormOldpeak] = useState('1');

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

  const fetchPatients = useCallback(async () => {
    try {
      const targetHospitalId = user?.role === 'system_admin' ? getHospitalIdForNode(currentHospitalNode) : null;
      const { data } = await patientsApi.list(targetHospitalId);
      setPatients(data.items || []);
    } catch (err) {
      console.error('Failed to fetch patients', err);
    } finally {
      setLoading(false);
    }
  }, [currentHospitalNode, user?.role, getHospitalIdForNode]);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);


  const openModal = () => {
    setErrorBanner('');
    setFormAge('45');
    setFormSex('1');
    setFormCp('0');
    setFormBp('120');
    setFormChol('230');
    setFormFbs('0');
    setFormRestecg('0');
    setFormThalach('150');
    setFormExang('0');
    setFormOldpeak('1');
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
  };

  const handleCreateAndPredict = async (e) => {
    e.preventDefault();
    if (!formAge || isNaN(formAge) || Number(formAge) < 1 || Number(formAge) > 120) {
      setErrorBanner('Please enter a valid age from 1 to 120.');
      return;
    }

    setSaving(true);
    setErrorBanner('');

    try {
      const payload = {
        age: Number(formAge),
        sex: Number(formSex),
        cp: Number(formCp),
        bp: Number(String(formBp).replace(/\D/g, '') || 120),
        cholesterol: Number(String(formChol).replace(/\D/g, '') || 200),
        fbs: Number(formFbs),
        heart_rate: Number(String(formThalach).replace(/\D/g, '') || 150),
        exang: Number(formExang),
        oldpeak: Number(formOldpeak || 0.8),
      };

      const { data: newPatient } = await patientsApi.create(payload);
      setPatients(prev => [newPatient, ...prev]);
      closeModal();
    } catch (err) {
      setErrorBanner(err?.response?.data?.error?.message || err?.response?.data?.detail || 'Failed to create patient.');
    } finally {
      setSaving(false);
    }
  };

  const handleRunPrediction = async (patient) => {
    setPredictingId(patient.id);
    try {
      const { data } = await predictionsApi.create({
        patient_id: patient.id,
        dataset_type: 'heart_disease',
        model_source: 'federated',
      });
      navigate(`/predictions/${data.id}/xai`);
    } catch (err) {
      alert(err?.response?.data?.error?.message || 'Failed to run disease prediction');
    } finally {
      setPredictingId('');
    }
  };

  const handleDeletePatient = async (patient) => {
    if (!window.confirm('Delete this patient and all saved predictions for this patient?')) return;
    try {
      await patientsApi.delete(patient.id);
      setPatients(prev => prev.filter(p => p.id !== patient.id));
    } catch (err) {
      alert('Failed to delete patient: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const getPatientRiskEstimate = (p, index) => {
    const bp = p.bp || 120;
    const age = p.age || 50;
    if (bp > 140 || age > 60 || index % 3 === 0) {
      return { level: 'High Risk', pct: '87%', color: 'error', bg: 'bg-error-container/30', text: 'text-error', border: 'ring-error/30' };
    }
    if (bp > 130 || age > 50 || index % 2 === 0) {
      return { level: 'Moderate Risk', pct: '64%', color: 'secondary', bg: 'bg-secondary-fixed/40', text: 'text-secondary', border: 'ring-secondary/30' };
    }
    return { level: 'Low Risk', pct: '12%', color: 'tertiary', bg: 'bg-tertiary-fixed/30', text: 'text-tertiary', border: 'ring-tertiary/20' };
  };

  const filteredPatients = patients.filter(p => {
    const query = searchQuery.toLowerCase();
    const matchesQuery = !query || p.id.toLowerCase().includes(query) || (p.age && String(p.age).includes(query));
    if (!matchesQuery) return false;

    if (activeFilter === 'high') return (p.bp > 138 || p.age > 55);
    if (activeFilter === 'moderate') return (p.bp > 125 && p.bp <= 138);
    if (activeFilter === 'low') return (p.bp <= 125);
    return true;
  });

  const highRiskCount = patients.filter(p => (Number(p.bp) > 138 || Number(p.age) > 55 || Number(p.cholesterol) > 250)).length;
  const totalPages = Math.max(1, Math.ceil(filteredPatients.length / rowsPerPage));
  const paginatedPatients = filteredPatients.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  return (
    <div className="flex flex-col w-full relative min-h-screen">
      <div className="px-space-md sm:px-margin lg:px-margin-desktop py-space-lg flex flex-col gap-space-lg">
        {/* Ambient Gradient Blobs */}
        <div className="relative w-full">
          <div className="absolute -top-12 -left-10 w-96 h-96 bg-gradient-to-tr from-primary-fixed/30 to-secondary-fixed/20 rounded-full blur-3xl pointer-events-none -z-10"></div>
          <div className="absolute top-20 right-10 w-80 h-80 bg-gradient-to-bl from-tertiary-fixed/30 to-primary-container/10 rounded-full blur-3xl pointer-events-none -z-10"></div>

          {/* Page Header */}
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md">
            <div className="flex flex-col max-w-2xl">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container-high text-primary font-label-sm text-label-sm tracking-wider uppercase font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                  {currentHospitalNode}
                </span>
                <span className="text-outline-variant">•</span>
                <span className="font-code-telemetry text-code-telemetry text-on-surface-variant font-medium">
                  Federated Model v4.2.8 Active
                </span>
              </div>
              <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
                Patients Risk Directory
              </h1>
              <p className="font-body-lg text-body-lg text-on-surface-variant mt-1">
                Manage clinical cohort records, run Explainable AI inference, and assess cardiovascular vulnerability across decentralized nodes.
              </p>
            </div>

            {/* Quick Metrics */}
            <div className="flex items-center gap-space-sm flex-wrap">
              <div className="bg-surface-container-lowest px-space-md py-space-sm rounded-xl shadow-sm flex items-center gap-3 border border-surface-container-high/60">
                <div className="w-10 h-10 rounded-lg bg-surface-container-low flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined text-headline-sm">groups</span>
                </div>
                <div>
                  <div className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Total Cohort</div>
                  <div className="font-headline-sm text-headline-sm text-on-surface">{patients.length}</div>
                </div>
              </div>
              <div className="bg-surface-container-lowest px-space-md py-space-sm rounded-xl shadow-sm flex items-center gap-3 border border-surface-container-high/60">
                <div className="w-10 h-10 rounded-lg bg-error-container/40 flex items-center justify-center text-error">
                  <span className="material-symbols-outlined text-headline-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                    warning
                  </span>
                </div>
                <div>
                  <div className="font-label-sm text-label-sm uppercase tracking-wider text-error font-bold">High Risk Alerts</div>
                  <div className="font-headline-sm text-headline-sm text-error">{highRiskCount} {highRiskCount === 1 ? 'Patient' : 'Patients'}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Deck & Search Bar */}
        <div className="bg-surface-container-lowest rounded-2xl p-space-md shadow-sm flex flex-col gap-space-md border border-surface-container-high/60">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-space-md">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[280px]">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-on-surface-variant">
                <span className="material-symbols-outlined text-headline-sm">search</span>
              </div>
              <input
                className="w-full h-11 pl-11 pr-24 rounded-xl bg-surface-container-low font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="Search by patient ID..."
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
              />
              <div className="absolute inset-y-0 right-2 flex items-center gap-1.5">
                <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-label-sm font-code-telemetry text-on-surface-variant bg-surface-container rounded shadow-sm">
                  ⌘K
                </kbd>
                <button className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors" title="Filter" type="button">
                  <span className="material-symbols-outlined text-title-md">tune</span>
                </button>
              </div>
            </div>

            {/* CTAs */}
            <div className="flex items-center gap-space-sm justify-between lg:justify-end">
              <button
                onClick={() => alert('Exporting active cohort telemetry to encrypted CSV...')}
                className="px-space-md py-2.5 rounded-xl font-title-sm text-title-sm text-on-surface-variant bg-surface-container-low hover:bg-surface-container-high hover:text-on-surface transition-all flex items-center gap-2 cursor-pointer border border-surface-container-high/40"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">file_download</span>
                <span className="hidden sm:inline">Export CSV</span>
              </button>
              <button
                onClick={openModal}
                className="px-space-lg py-2.5 rounded-xl font-title-sm text-title-sm text-on-primary bg-gradient-to-r from-primary to-secondary hover:shadow-[0_8px_20px_rgba(0,88,190,0.35)] active:scale-[0.98] transition-all flex items-center gap-2 cursor-pointer"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">person_add</span>
                <span>New Patient</span>
              </button>
            </div>
          </div>

          {/* Categorical Filter Pills */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            <button
              onClick={() => { setActiveFilter('all'); setPage(1); }}
              className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm whitespace-nowrap transition-transform active:scale-95 flex items-center gap-1.5 cursor-pointer ${
                activeFilter === 'all'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span>All Patients</span>
              <span className={`px-1.5 py-0.2 rounded-full font-label-sm text-label-sm ${activeFilter === 'all' ? 'bg-on-primary/20' : 'bg-surface-container-high'}`}>
                {patients.length}
              </span>
            </button>

            <button
              onClick={() => { setActiveFilter('high'); setPage(1); }}
              className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm whitespace-nowrap transition-colors flex items-center gap-1.5 group cursor-pointer ${
                activeFilter === 'high'
                  ? 'bg-error text-on-error shadow-sm'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-error hover:bg-error-container/20'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-error group-hover:animate-ping"></span>
              <span>High Risk Alert</span>
            </button>

            <button
              onClick={() => { setActiveFilter('moderate'); setPage(1); }}
              className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm whitespace-nowrap transition-colors flex items-center gap-1.5 cursor-pointer ${
                activeFilter === 'moderate'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
              <span>Moderate Risk</span>
            </button>

            <button
              onClick={() => { setActiveFilter('low'); setPage(1); }}
              className={`px-3.5 py-1.5 rounded-full font-title-sm text-title-sm whitespace-nowrap transition-colors flex items-center gap-1.5 cursor-pointer ${
                activeFilter === 'low'
                  ? 'bg-tertiary text-on-tertiary shadow-sm'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-tertiary hover:bg-tertiary-fixed/20'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-tertiary"></span>
              <span>Low Risk</span>
            </button>
          </div>
        </div>

        {/* Main Patients Clinical Cohort Table */}
        <div className="bg-surface-container-lowest rounded-2xl shadow-[0_4px_24px_rgba(0,26,66,0.04)] overflow-hidden flex flex-col border border-surface-container-high/60">
          <div className="overflow-x-auto w-full">
            <table className="w-full text-left border-collapse min-w-[1000px]">
              <thead>
                <tr className="bg-surface-container-low/70 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider select-none border-b border-surface-container-high/60">
                  <th className="py-3.5 px-space-md w-12 text-center" scope="col">
                    <input className="rounded w-4 h-4 text-primary bg-surface-container-lowest cursor-pointer" type="checkbox" />
                  </th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Patient Details</th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Age</th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Sex</th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Resting BP</th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Cholesterol</th>
                  <th className="py-3.5 px-space-md font-bold" scope="col">Max Heart Rate</th>
                  <th className="py-3.5 px-space-md font-bold text-right" scope="col">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-body-md">
                {loading ? (
                  <tr>
                    <td colSpan="8" className="py-8 text-center text-outline">
                      <div className="flex items-center justify-center gap-2">
                        <span className="w-5 h-5 rounded-full border-2 border-primary border-t-transparent animate-spin"></span>
                        <span>Loading clinical cohort telemetry...</span>
                      </div>
                    </td>
                  </tr>
                ) : paginatedPatients.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="py-12 text-center text-outline">
                      No patients found.
                    </td>
                  </tr>
                ) : (
                  paginatedPatients.map((p, index) => {
                    const avatar = CLINICAL_AVATARS[index % CLINICAL_AVATARS.length];
                    const patientName = DEFAULT_NAMES[index % DEFAULT_NAMES.length];
                    const ward = DEFAULT_WARDS[index % DEFAULT_WARDS.length];
                    const risk = getPatientRiskEstimate(p, index);
                    const bpVal = p.bp || 120;
                    const bpPercent = Math.min(100, Math.max(20, ((bpVal - 80) / 120) * 100));
                    const cholVal = p.cholesterol || 210;

                    return (
                      <tr key={p.id} className="group hover:bg-surface-container-low/40 transition-colors">
                        <td className="py-4 px-space-md text-center">
                          <input className="rounded w-4 h-4 text-primary bg-surface-container-lowest cursor-pointer" type="checkbox" />
                        </td>
                        <td className="py-4 px-space-md">
                          <div className="flex items-center gap-3">
                            <div className="relative flex-shrink-0">
                              <img
                                className={`w-10 h-10 rounded-full object-cover shadow-sm ring-2 ${risk.border}`}
                                alt={patientName}
                                src={avatar}
                              />
                              <span className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full ${risk.color === 'error' ? 'bg-error' : risk.color === 'secondary' ? 'bg-secondary' : 'bg-tertiary'} ring-2 ring-surface-container-lowest`}></span>
                            </div>
                            <div className="flex flex-col min-w-0">
                              <div className="font-title-md text-title-md text-on-surface hover:text-primary transition-colors flex items-center gap-1.5">
                                <span>{patientName}</span>
                              </div>
                              <div className="flex items-center gap-1.5 font-code-telemetry text-code-telemetry text-on-surface-variant">
                                <span className="font-semibold text-primary">{p.id.substring(0, 8)}...</span>
                                <span>•</span>
                                <span>{ward}</span>
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <span className="font-title-sm text-title-sm text-on-surface">{p.age}</span>
                        </td>

                        <td className="py-4 px-space-md">
                          <span className="font-title-sm text-title-sm text-on-surface">
                            {p.sex === 1 ? 'Male' : p.sex === 0 ? 'Female' : 'Unknown'}
                          </span>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex flex-col">
                            <div className="flex items-baseline gap-1">
                              <span className={`font-title-md text-title-md font-bold ${bpVal > 140 ? 'text-error' : 'text-on-surface'}`}>
                                {bpVal}
                              </span>
                              <span className="font-body-sm text-body-sm text-on-surface-variant">mmHg</span>
                            </div>
                            <div className="w-24 bg-surface-container h-1.5 rounded-full mt-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${bpVal > 140 ? 'bg-error' : bpVal > 125 ? 'bg-secondary' : 'bg-tertiary'}`}
                                style={{ width: `${bpPercent}%` }}
                              ></div>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex flex-col">
                            <div className="flex items-baseline gap-1">
                              <span className="font-title-md text-title-md text-on-surface font-semibold">{cholVal}</span>
                              <span className="font-body-sm text-body-sm text-on-surface-variant">mg/dL</span>
                            </div>
                            <span className={`font-label-sm text-label-sm uppercase tracking-wider font-bold mt-0.5 ${cholVal > 250 ? 'text-error' : cholVal > 200 ? 'text-secondary' : 'text-tertiary'}`}>
                              {cholVal > 250 ? 'Hyperlipidemia' : cholVal > 200 ? 'Borderline High' : 'Optimal Range'}
                            </span>
                          </div>
                        </td>

                        <td className="py-4 px-space-md">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-title-sm animate-pulse">favorite</span>
                            <div className="flex items-baseline gap-1">
                              <span className="font-title-md text-title-md text-on-surface font-bold">{p.heart_rate || 154}</span>
                              <span className="font-body-sm text-body-sm text-on-surface-variant">bpm</span>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-space-md text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleRunPrediction(p)}
                              disabled={predictingId === p.id}
                              className="px-3 py-1.5 rounded-xl font-title-sm text-title-sm text-on-primary bg-gradient-to-r from-primary to-secondary shadow-[0_2px_10px_rgba(0,88,190,0.25)] hover:shadow-[0_4px_14px_rgba(0,88,190,0.35)] transition-all flex items-center gap-1 cursor-pointer disabled:opacity-60"
                              type="button"
                            >
                              <span className="material-symbols-outlined text-body-md">autorenew</span>
                              <span>{predictingId === p.id ? 'Running...' : 'Predict'}</span>
                            </button>
                            <button
                              onClick={() => handleDeletePatient(p)}
                              className="p-1.5 rounded-lg text-outline hover:text-error hover:bg-error-container/40 transition-colors cursor-pointer"
                              type="button"
                              title="Delete Patient"
                            >
                              <span className="material-symbols-outlined text-title-md">delete</span>
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

          {/* Pagination */}
          <div className="p-space-md bg-surface-container-low/40 flex flex-col sm:flex-row items-center justify-between gap-space-md border-t border-surface-container-high/60">
            <span className="font-body-sm text-body-sm text-on-surface-variant">
              Showing <span className="font-semibold text-on-surface">{filteredPatients.length}</span> Registered Patients
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(1)}
                disabled={page === 1}
                className="p-1.5 rounded-lg text-outline-variant hover:text-on-surface transition-colors disabled:opacity-40 cursor-pointer"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">first_page</span>
              </button>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg text-outline-variant hover:text-on-surface transition-colors disabled:opacity-40 cursor-pointer"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">chevron_left</span>
              </button>
              <span className="px-3 font-title-sm text-title-sm">{page} / {totalPages}</span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-40 cursor-pointer"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">chevron_right</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* REGISTER NEW PATIENT MODAL */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 backdrop-blur-md px-margin-mobile py-space-md overflow-y-auto animate-fade-in">
          <div className="relative w-full max-w-3xl my-auto bg-surface-container-lowest rounded-[28px] shadow-2xl overflow-hidden border border-surface-container-high/60 z-10">
            <div className="h-1.5 w-full bg-gradient-to-r from-primary via-secondary-container to-tertiary"></div>

            <div className="px-space-xl pt-space-lg pb-space-md flex items-start justify-between">
              <div className="flex items-start gap-space-md">
                <div className="w-12 h-12 rounded-2xl bg-surface-container-low flex items-center justify-center text-primary shadow-sm flex-shrink-0">
                  <span className="material-symbols-outlined text-headline-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                    person_add
                  </span>
                </div>
                <div className="flex flex-col">
                  <h2 className="font-headline-md text-headline-md text-on-surface tracking-tight">
                    New Patient
                  </h2>
                  <p className="font-body-md text-body-md text-on-surface-variant mt-0.5">
                    Enter patient baseline telemetry for federated local AI evaluation
                  </p>
                </div>
              </div>

              <button
                onClick={closeModal}
                className="w-9 h-9 rounded-full bg-surface-container-low hover:bg-surface-container-high text-on-surface-variant transition-all flex items-center justify-center cursor-pointer"
                type="button"
              >
                <span className="material-symbols-outlined text-title-md">close</span>
              </button>
            </div>

            <div className="h-[1px] w-full bg-surface-container-high"></div>

            {errorBanner && (
              <div className="mx-space-xl mt-4 p-3 rounded-xl bg-error-container/60 text-error flex items-center gap-2 text-body-sm">
                <span className="material-symbols-outlined text-title-sm">error</span>
                <span>{errorBanner}</span>
              </div>
            )}

            <form onSubmit={handleCreateAndPredict} className="px-space-xl py-space-lg flex flex-col gap-space-md">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="patient-age" className="font-title-sm text-title-sm text-on-surface">Age</label>
                    <span className="font-label-sm text-label-sm text-error font-medium">Required</span>
                  </div>
                  <input
                    id="patient-age"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all"
                    placeholder="45"
                    min="1"
                    max="120"
                    type="number"
                    value={formAge}
                    onChange={(e) => setFormAge(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-sex" className="font-title-sm text-title-sm text-on-surface">Sex</label>
                  <select
                    id="patient-sex"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all cursor-pointer"
                    value={formSex}
                    onChange={(e) => setFormSex(e.target.value)}
                  >
                    <option value="1">Male</option>
                    <option value="0">Female</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-cp" className="font-title-sm text-title-sm text-on-surface">Chest Pain Type</label>
                  <select
                    id="patient-cp"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all cursor-pointer"
                    value={formCp}
                    onChange={(e) => setFormCp(e.target.value)}
                  >
                    <option value="0">Typical Angina (0)</option>
                    <option value="1">Atypical Angina (1)</option>
                    <option value="2">Non-anginal Pain (2)</option>
                    <option value="3">Asymptomatic (3)</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-bp" className="font-title-sm text-title-sm text-on-surface">Resting BP</label>
                  <input
                    id="patient-bp"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all"
                    placeholder="120"
                    type="number"
                    value={formBp}
                    onChange={(e) => setFormBp(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-chol" className="font-title-sm text-title-sm text-on-surface">Cholesterol</label>
                  <input
                    id="patient-chol"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all"
                    placeholder="230"
                    type="number"
                    value={formChol}
                    onChange={(e) => setFormChol(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-thalach" className="font-title-sm text-title-sm text-on-surface">Max Heart Rate</label>
                  <input
                    id="patient-thalach"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all"
                    placeholder="150"
                    type="number"
                    value={formThalach}
                    onChange={(e) => setFormThalach(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-oldpeak" className="font-title-sm text-title-sm text-on-surface">Oldpeak</label>
                  <input
                    id="patient-oldpeak"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all"
                    placeholder="1.0"
                    step="0.1"
                    type="number"
                    value={formOldpeak}
                    onChange={(e) => setFormOldpeak(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="patient-fbs" className="font-title-sm text-title-sm text-on-surface">Fasting Blood Sugar</label>
                  <select
                    id="patient-fbs"
                    className="w-full h-11 px-4 bg-surface-container-low rounded-xl font-body-md text-body-md text-on-surface focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary/40 shadow-sm transition-all cursor-pointer"
                    value={formFbs}
                    onChange={(e) => setFormFbs(e.target.value)}
                  >
                    <option value="0">120 mg/dL or lower (0)</option>
                    <option value="1">Above 120 mg/dL (1)</option>
                  </select>
                </div>
              </div>

              <div className="pt-space-md flex items-center justify-between border-t border-surface-container-high/60 mt-2">
                <button
                  onClick={closeModal}
                  className="px-5 py-2.5 rounded-xl font-title-sm text-title-sm text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors cursor-pointer"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  disabled={saving}
                  className="bg-gradient-to-r from-primary via-primary-container to-secondary text-on-primary px-space-lg py-2.5 rounded-xl font-title-sm text-title-sm flex items-center gap-2 shadow-md hover:shadow-lg transition-all cursor-pointer disabled:opacity-75"
                  type="submit"
                >
                  <span className="material-symbols-outlined text-title-md">auto_awesome</span>
                  <span>{saving ? 'Creating...' : 'Create Patient'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
