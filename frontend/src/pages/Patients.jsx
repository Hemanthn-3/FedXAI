import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, Plus, Search, Trash2, Users, X } from 'lucide-react';
import { patientsApi, predictionsApi } from '../api';
import './TablePages.css';

const emptyForm = {
  age: '',
  sex: '1',
  cp: '0',
  bp: '',
  cholesterol: '',
  fbs: '0',
  heart_rate: '',
  exang: '0',
  oldpeak: '0',
};

const errorMessage = (err, fallback) => (
  err?.response?.data?.error?.message ||
  err?.response?.data?.detail ||
  fallback
);

export const Patients = () => {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [predictingId, setPredictingId] = useState('');
  const [deletingId, setDeletingId] = useState('');
  const [predictionError, setPredictionError] = useState('');

  useEffect(() => {
    const fetchPatients = async () => {
      try {
        const { data } = await patientsApi.list();
        setPatients(data.items || []);
      } catch (err) {
        console.error('Failed to fetch patients', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPatients();
  }, []);

  const filtered = patients.filter(p =>
    searchQuery === '' || p.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const openModal = () => {
    setForm(emptyForm);
    setFormError('');
    setShowModal(true);
  };
  const closeModal = () => setShowModal(false);

  const updateForm = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.age || isNaN(form.age) || Number(form.age) < 1 || Number(form.age) > 120) {
      setFormError('Please enter a valid age from 1 to 120.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const payload = {
        age: Number(form.age),
        sex: Number(form.sex),
        cp: Number(form.cp),
        bp: Number(form.bp),
        cholesterol: Number(form.cholesterol),
        fbs: Number(form.fbs),
        heart_rate: Number(form.heart_rate),
        exang: Number(form.exang),
        oldpeak: Number(form.oldpeak),
      };
      const { data } = await patientsApi.create(payload);
      setPatients(prev => [data, ...prev]);
      closeModal();
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to create patient.'));
    } finally {
      setSaving(false);
    }
  };

  const handleRunPrediction = async (patient) => {
    setPredictingId(patient.id);
    setPredictionError('');
    try {
      const { data } = await predictionsApi.create({
        patient_id: patient.id,
        dataset_type: 'heart_disease',
        model_source: 'federated',
      });
      navigate(`/predictions/${data.id}/xai`);
    } catch (err) {
      setPredictionError(errorMessage(err, 'Failed to run disease prediction.'));
    } finally {
      setPredictingId('');
    }
  };

  const handleDeletePatient = async (patient) => {
    const confirmed = window.confirm(
      'Delete this patient and all saved predictions for this patient?'
    );
    if (!confirmed) {
      return;
    }
    setDeletingId(patient.id);
    setPredictionError('');
    try {
      await patientsApi.delete(patient.id);
      setPatients(prev => prev.filter(item => item.id !== patient.id));
    } catch (err) {
      setPredictionError(errorMessage(err, 'Failed to delete patient.'));
    } finally {
      setDeletingId('');
    }
  };

  return (
    <div className="page-container">
      <div className="page-header flex-between">
        <div>
          <h1><Users size={24} style={{ display: 'inline', marginRight: 10, verticalAlign: 'text-bottom' }} /> Patients</h1>
          <p>Manage patient records and run heart disease risk prediction.</p>
        </div>
        <button className="btn btn-primary" onClick={openModal}>
          <Plus size={18} /> New Patient
        </button>
      </div>

      {predictionError && (
        <div className="inline-error animate-fade-in">{predictionError}</div>
      )}

      <div className="glass-panel content-panel">
        <div className="panel-toolbar flex-between">
          <div className="search-bar input-group" style={{ width: '300px' }}>
            <div className="input-icon"><Search size={16} /></div>
            <input
              type="text"
              className="input-field with-icon"
              placeholder="Search by patient ID..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
          <span className="text-muted" style={{ fontSize: '0.85rem' }}>
            {filtered.length} of {patients.length} patients
          </span>
        </div>

        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Age</th>
                <th>Sex</th>
                <th>BP</th>
                <th>Cholesterol</th>
                <th>Heart Rate</th>
                <th>Registered</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="8" className="text-center">Loading patients...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan="8" className="text-center text-muted">
                  {searchQuery ? 'No patients match your search.' : 'No patients found.'}
                </td></tr>
              ) : (
                filtered.map(p => (
                  <tr key={p.id}>
                    <td><span className="text-monospace text-muted">{p.id.substring(0, 8)}...</span></td>
                    <td>{p.age}</td>
                    <td>{p.sex == null ? 'Unknown' : p.sex === 1 ? 'Male' : 'Female'}</td>
                    <td>{p.bp ?? '-'}</td>
                    <td>{p.cholesterol ?? '-'}</td>
                    <td>{p.heart_rate ?? '-'}</td>
                    <td>{new Date(p.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="action-buttons">
                        <button
                          className="btn btn-primary btn-compact"
                          onClick={() => handleRunPrediction(p)}
                          disabled={predictingId === p.id || deletingId === p.id}
                        >
                          <Brain size={16} />
                          {predictingId === p.id ? 'Running...' : 'Predict'}
                        </button>
                        <button
                          className="icon-btn danger"
                          title="Delete patient"
                          aria-label="Delete patient"
                          onClick={() => handleDeletePatient(p)}
                          disabled={deletingId === p.id || predictingId === p.id}
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

      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-box animate-fade-in" onClick={e => e.stopPropagation()}>
            <div className="flex-between" style={{ marginBottom: 24 }}>
              <h2 style={{ margin: 0 }}>New Patient</h2>
              <button className="icon-btn" onClick={closeModal}><X size={18} /></button>
            </div>

            <form onSubmit={handleCreate}>
              {formError && (
                <div className="inline-error" style={{ marginBottom: 16 }}>
                  {formError}
                </div>
              )}

              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="patient-age">Age</label>
                  <input
                    id="patient-age"
                    type="number"
                    className="input-field"
                    placeholder="45"
                    min="1" max="120"
                    value={form.age}
                    onChange={e => updateForm('age', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="patient-sex">Sex</label>
                  <select
                    id="patient-sex"
                    className="input-field"
                    value={form.sex}
                    onChange={e => updateForm('sex', e.target.value)}
                  >
                    <option value="1">Male</option>
                    <option value="0">Female</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="patient-cp">Chest Pain Type</label>
                  <select
                    id="patient-cp"
                    className="input-field"
                    value={form.cp}
                    onChange={e => updateForm('cp', e.target.value)}
                  >
                    <option value="0">Typical Angina</option>
                    <option value="1">Atypical Angina</option>
                    <option value="2">Non-anginal Pain</option>
                    <option value="3">Asymptomatic</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="patient-bp">Resting BP</label>
                  <input
                    id="patient-bp"
                    type="number"
                    className="input-field"
                    placeholder="120"
                    min="20" max="350"
                    value={form.bp}
                    onChange={e => updateForm('bp', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="patient-cholesterol">Cholesterol</label>
                  <input
                    id="patient-cholesterol"
                    type="number"
                    className="input-field"
                    placeholder="230"
                    min="0" max="1500"
                    value={form.cholesterol}
                    onChange={e => updateForm('cholesterol', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="patient-fbs">Fasting Blood Sugar</label>
                  <select
                    id="patient-fbs"
                    className="input-field"
                    value={form.fbs}
                    onChange={e => updateForm('fbs', e.target.value)}
                  >
                    <option value="0">120 mg/dL or lower</option>
                    <option value="1">Above 120 mg/dL</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="patient-heart-rate">Max Heart Rate</label>
                  <input
                    id="patient-heart-rate"
                    type="number"
                    className="input-field"
                    placeholder="150"
                    min="20" max="300"
                    value={form.heart_rate}
                    onChange={e => updateForm('heart_rate', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="patient-exang">Exercise Angina</label>
                  <select
                    id="patient-exang"
                    className="input-field"
                    value={form.exang}
                    onChange={e => updateForm('exang', e.target.value)}
                  >
                    <option value="0">No</option>
                    <option value="1">Yes</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="patient-oldpeak">Oldpeak</label>
                  <input
                    id="patient-oldpeak"
                    type="number"
                    className="input-field"
                    placeholder="1.0"
                    min="0" max="10" step="0.1"
                    value={form.oldpeak}
                    onChange={e => updateForm('oldpeak', e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Creating...' : 'Create Patient'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
