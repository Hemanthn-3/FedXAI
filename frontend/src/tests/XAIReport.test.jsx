
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { XAIReport } from '../pages/XAIReport';
import { predictionsApi, xaiApi } from '../api';

vi.mock('react-router-dom', () => ({
  useParams:   vi.fn(() => ({ id: 'test-pred-uuid-001' })),
  useNavigate: vi.fn(() => vi.fn()),
}));

vi.mock('../api', () => ({
  predictionsApi: { get: vi.fn() },
  xaiApi: {
    generate:       vi.fn(),
    getByPrediction: vi.fn(),
    downloadPdfUrl:  vi.fn(() => 'http://localhost/pdf/test-pred-uuid-001'),
  },
}));

vi.mock('lucide-react', () => ({
  Brain:       () => <div />,
  Download:    () => <div data-testid="download-icon" />,
  RefreshCw:   () => <div />,
  ArrowLeft:   () => <div data-testid="back-btn" />,
  CheckCircle2:() => <div />,
  AlertTriangle:()=> <div />,
  Loader:      () => <div data-testid="loader" />,
  BarChart2:   () => <div />,
  Zap:         () => <div />,
}));

const SAMPLE_PREDICTION = {
  id: 'test-pred-uuid-001',
  dataset_type: 'heart_disease',
  risk_level: 'high',
  probability: 0.88,
  prediction: 1,
  created_at: '2025-05-01T10:00:00Z',
  doctor_notes: 'Review required.',
};

const SAMPLE_REPORT = {
  id: 'report-uuid-001',
  status: 'completed',
  top_shap_features: ['age', 'chol'],
  top_lime_features: ['sex', 'trestbps'],
  feature_ranking: [
    { feature: 'age', abs_contribution: 0.42 },
    { feature: 'chol', abs_contribution: 0.28 },
  ],
  local_contributions: [],
};

describe('XAIReport Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders prediction summary after loading', async () => {
    predictionsApi.get.mockResolvedValueOnce({ data: SAMPLE_PREDICTION });
    xaiApi.getByPrediction.mockResolvedValueOnce({ data: SAMPLE_REPORT });
    render(<XAIReport />);

    await waitFor(() => {
      expect(screen.getByText('88.0%')).toBeDefined();
      expect(screen.getByText('HIGH')).toBeDefined();
      expect(screen.getByText('Review required.')).toBeDefined();
    });
  });

  it('shows SHAP and LIME feature tables when report is loaded', async () => {
    predictionsApi.get.mockResolvedValueOnce({ data: SAMPLE_PREDICTION });
    xaiApi.getByPrediction.mockResolvedValueOnce({ data: SAMPLE_REPORT });
    render(<XAIReport />);

    await waitFor(() => {
      // features appear in both SHAP/LIME tables and the full ranking — use getAllByText
      expect(screen.getAllByText('age').length).toBeGreaterThan(0);
      expect(screen.getAllByText('chol').length).toBeGreaterThan(0);
      expect(screen.getAllByText('sex').length).toBeGreaterThan(0);
      expect(screen.getAllByText('trestbps').length).toBeGreaterThan(0);
    });
  });

  it('shows "No XAI Report Yet" when no report exists', async () => {
    predictionsApi.get.mockResolvedValueOnce({ data: SAMPLE_PREDICTION });
    xaiApi.getByPrediction.mockRejectedValueOnce(new Error('404'));
    render(<XAIReport />);

    await waitFor(() => {
      expect(screen.getByText('No XAI Report Yet')).toBeDefined();
    });
  });

  it('calls generate API when Generate button is clicked', async () => {
    predictionsApi.get.mockResolvedValueOnce({ data: SAMPLE_PREDICTION });
    xaiApi.getByPrediction.mockRejectedValueOnce(new Error('404'));
    xaiApi.generate.mockResolvedValueOnce({ data: SAMPLE_REPORT });

    render(<XAIReport />);

    await waitFor(() => {
      expect(screen.getByText('No XAI Report Yet')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    await waitFor(() => {
      expect(xaiApi.generate).toHaveBeenCalledWith('test-pred-uuid-001');
    });
  });

  it('shows error banner when generate fails', async () => {
    predictionsApi.get.mockResolvedValueOnce({ data: SAMPLE_PREDICTION });
    xaiApi.getByPrediction.mockRejectedValueOnce(new Error('404'));
    xaiApi.generate.mockRejectedValueOnce(new Error('Server error'));

    render(<XAIReport />);
    await waitFor(() => { expect(screen.getByText('No XAI Report Yet')).toBeDefined(); });

    fireEvent.click(screen.getByRole('button', { name: /generate report/i }));

    await waitFor(() => {
      expect(screen.getByText(/Failed to generate XAI report/i)).toBeDefined();
    });
  });
});
