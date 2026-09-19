import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Predictions } from '../pages/Predictions';
import { predictionsApi } from '../api';

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}));

vi.mock('../api', () => ({
  predictionsApi: {
    list: vi.fn(),
    delete: vi.fn(),
  },
  xaiApi: {
    generate:          vi.fn(),
    getByPrediction:   vi.fn(),
    downloadPdfUrl:    vi.fn(() => 'http://localhost:8000/api/v1/reports/predictions/123/pdf'),
  },
}));

vi.mock('lucide-react', () => ({
  FileText: () => <div />,
  Eye:      () => <div data-testid="eye-icon" />,
  Download: () => <div data-testid="download-icon" />,
  Trash2:   () => <div data-testid="trash-icon" />,
}));

const SAMPLE_PREDICTIONS = [
  {
    id: 'pred-uuid-0001',
    patient_id: 'patient-uuid-0001',
    created_at: '2025-04-01T10:00:00Z',
    dataset_type: 'heart_disease',
    risk_level: 'high',
    probability: 0.82,
    prediction: 1,
  },
  {
    id: 'pred-uuid-0002',
    patient_id: 'patient-uuid-0002',
    created_at: '2025-04-02T11:00:00Z',
    dataset_type: 'diabetes',
    risk_level: 'low',
    probability: 0.15,
    prediction: 0,
  },
];

describe('Predictions Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    predictionsApi.delete.mockResolvedValue({ data: { message: 'Prediction deleted successfully' } });
    window.confirm = vi.fn(() => true);
  });

  it('renders predictions in the table', async () => {
    predictionsApi.list.mockResolvedValueOnce({ data: { items: SAMPLE_PREDICTIONS } });
    render(<Predictions />);

    await waitFor(() => {
      expect(screen.getByText('HIGH')).toBeDefined();
      expect(screen.getByText('LOW')).toBeDefined();
      expect(screen.getByText('82.0%')).toBeDefined();
      expect(screen.getByText('15.0%')).toBeDefined();
    });
  });

  it('shows "No predictions found." when list is empty', async () => {
    predictionsApi.list.mockResolvedValueOnce({ data: { items: [] } });
    render(<Predictions />);
    await waitFor(() => {
      expect(screen.getByText('No predictions found.')).toBeDefined();
    });
  });

  it('shows loading state initially', () => {
    predictionsApi.list.mockReturnValue(new Promise(() => {})); // never resolves
    render(<Predictions />);
    expect(screen.getByText('Loading predictions...')).toBeDefined();
  });

  it('renders Eye and Download buttons for each prediction', async () => {
    predictionsApi.list.mockResolvedValueOnce({ data: { items: SAMPLE_PREDICTIONS } });
    render(<Predictions />);
    await waitFor(() => {
      expect(screen.getAllByTestId('eye-icon').length).toBe(2);
      expect(screen.getAllByTestId('download-icon').length).toBe(2);
    });
  });

  it('renders delete buttons for each prediction', async () => {
    predictionsApi.list.mockResolvedValueOnce({ data: { items: SAMPLE_PREDICTIONS } });
    render(<Predictions />);
    await waitFor(() => {
      expect(screen.getAllByTestId('trash-icon').length).toBe(2);
    });
  });
});
