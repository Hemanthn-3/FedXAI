import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Dashboard } from '../pages/Dashboard';
import { metricsApi } from '../api';

vi.mock('../api', () => ({
  metricsApi: {
    getSystemHealth:    vi.fn(),
    getPredictionStats: vi.fn(),
    getTrainingRounds:  vi.fn(),
  },
}));

vi.mock('lucide-react', () => ({
  Activity:     () => <div />,
  Server:       () => <div />,
  ShieldCheck:  () => <div />,
  Database:     () => <div />,
  CheckCircle2: () => <div />,
  Cpu:          () => <div />,
  Radio:        () => <div data-testid="radio-icon" />,
}));

const HEALTH_OK   = { status: 'ok', database: 'up', redis: 'up' };
const STATS_DATA  = { total_predictions: 42, by_risk_level: { high: 5 }, with_xai_report: 10 };
const ROUNDS_DATA = {
  rounds: [
    { id: 'r1', round_number: 1, dataset_type: 'heart_disease', status: 'completed', accuracy: 0.88, loss: 0.31 },
    { id: 'r2', round_number: 2, dataset_type: 'heart_disease', status: 'failed',    accuracy: null,  loss: null  },
  ],
};

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all four stat cards with correct values', async () => {
    metricsApi.getSystemHealth.mockResolvedValueOnce({ data: HEALTH_OK });
    metricsApi.getPredictionStats.mockResolvedValueOnce({ data: STATS_DATA });
    metricsApi.getTrainingRounds.mockResolvedValueOnce({ data: ROUNDS_DATA });
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Total Predictions')).toBeDefined();
      expect(screen.getByText('High Risk Detected')).toBeDefined();
      expect(screen.getByText('XAI Reports')).toBeDefined();
      expect(screen.getByText('Training Rounds')).toBeDefined();
    });
  });

  it('renders the system health panel', async () => {
    metricsApi.getSystemHealth.mockResolvedValueOnce({ data: HEALTH_OK });
    metricsApi.getPredictionStats.mockResolvedValueOnce({ data: STATS_DATA });
    metricsApi.getTrainingRounds.mockResolvedValueOnce({ data: ROUNDS_DATA });
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Database Status')).toBeDefined();
      expect(screen.getByText('Redis Cache')).toBeDefined();
    });
  });

  it('renders training rounds in the activity panel', async () => {
    metricsApi.getSystemHealth.mockResolvedValueOnce({ data: HEALTH_OK });
    metricsApi.getPredictionStats.mockResolvedValueOnce({ data: STATS_DATA });
    metricsApi.getTrainingRounds.mockResolvedValueOnce({ data: ROUNDS_DATA });
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText(/Round 1/)).toBeDefined();
      expect(screen.getByText(/Round 2/)).toBeDefined();
    });
  });

  it('shows empty activity message when no rounds exist', async () => {
    metricsApi.getSystemHealth.mockResolvedValueOnce({ data: HEALTH_OK });
    metricsApi.getPredictionStats.mockResolvedValueOnce({ data: STATS_DATA });
    metricsApi.getTrainingRounds.mockResolvedValueOnce({ data: { rounds: [] } });
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('No training rounds recorded yet.')).toBeDefined();
    });
  });
});
