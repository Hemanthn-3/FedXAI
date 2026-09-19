
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Patients } from '../pages/Patients';
import { patientsApi, predictionsApi } from '../api';

// Mock API module
vi.mock('../api', () => ({
  patientsApi: {
    list:   vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  predictionsApi: {
    create: vi.fn(),
  },
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Users:  () => <div data-testid="users-icon" />,
  Plus:   () => <div data-testid="plus-icon" />,
  Search: () => <div data-testid="search-icon" />,
  Brain:  () => <div data-testid="brain-icon" />,
  Trash2: () => <div data-testid="trash-icon" />,
  X:      () => <div data-testid="x-icon" />,
}));

const SAMPLE_PATIENTS = [
  { id: 'abc123de-0000-0000-0000-000000000001', age: 45, sex: 1, created_at: '2025-01-01T00:00:00Z' },
  { id: 'abc123de-0000-0000-0000-000000000002', age: 62, sex: 0, created_at: '2025-02-01T00:00:00Z' },
];

describe('Patients Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    predictionsApi.create.mockResolvedValue({ data: { id: 'prediction-id' } });
    patientsApi.delete.mockResolvedValue({ data: { message: 'Patient deleted successfully' } });
    window.confirm = vi.fn(() => true);
  });

  it('renders the table with patient data', async () => {
    patientsApi.list.mockResolvedValueOnce({ data: { items: SAMPLE_PATIENTS } });
    render(<Patients />);

    await waitFor(() => {
      // The ID span renders prefix + ellipsis as adjacent text nodes; use a function matcher
      const idCells = screen.getAllByText((content, el) =>
        el?.tagName === 'SPAN' && el.textContent.includes('abc123de')
      );
      expect(idCells.length).toBeGreaterThan(0);
    });
    expect(screen.getByText('45')).toBeDefined();
    expect(screen.getByText('Male')).toBeDefined();
    expect(screen.getByText('Female')).toBeDefined();
  });

  it('shows "No patients found." when list is empty', async () => {
    patientsApi.list.mockResolvedValueOnce({ data: { items: [] } });
    render(<Patients />);
    await waitFor(() => {
      expect(screen.getByText('No patients found.')).toBeDefined();
    });
  });

  it('filters patients by search query', async () => {
    patientsApi.list.mockResolvedValueOnce({ data: { items: SAMPLE_PATIENTS } });
    render(<Patients />);
    await waitFor(() => {
      const idCells = screen.getAllByText((content, el) =>
        el?.tagName === 'SPAN' && el.textContent.includes('abc123de')
      );
      expect(idCells.length).toBeGreaterThan(0);
    });

    const searchInput = screen.getByPlaceholderText('Search by patient ID…');
    fireEvent.change(searchInput, { target: { value: 'abc123de-0000-0000-0000-000000000001' } });

    // After filter, only 1 patient row visible (age 45)
    expect(screen.getByText('45')).toBeDefined();
    expect(screen.queryByText('62')).toBeNull();
  });

  it('opens the New Patient modal when button is clicked', async () => {
    patientsApi.list.mockResolvedValueOnce({ data: { items: [] } });
    render(<Patients />);
    await waitFor(() => {
      expect(screen.getByText('No patients found.')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /new patient/i }));
    // Modal heading appears (there are now two 'New Patient' occurrences: btn + modal h2)
    expect(screen.getAllByText(/new patient/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Age')).toBeDefined();
    expect(screen.getByLabelText('Biological Sex')).toBeDefined();
  });

  it('creates a new patient on form submit', async () => {
    const newPatient = { id: 'new-uuid-0000-0000-0000-000000000099', age: 30, sex: 1, created_at: '2025-03-01T00:00:00Z' };
    patientsApi.list.mockResolvedValueOnce({ data: { items: [] } });
    patientsApi.create.mockResolvedValueOnce({ data: newPatient });
    render(<Patients />);
    await waitFor(() => {
      expect(screen.getByText('No patients found.')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /new patient/i }));
    fireEvent.change(screen.getByLabelText('Age'), { target: { value: '30' } });
    fireEvent.click(screen.getByRole('button', { name: /create patient/i }));

    await waitFor(() => {
      expect(patientsApi.create).toHaveBeenCalledWith({ age: 30, sex: 1 });
    });
  });

  it('shows a validation error for invalid age', async () => {
    patientsApi.list.mockResolvedValueOnce({ data: { items: [] } });
    render(<Patients />);
    await waitFor(() => { expect(screen.getByText('No patients found.')).toBeDefined(); });

    fireEvent.click(screen.getByRole('button', { name: /new patient/i }));
    fireEvent.change(screen.getByLabelText('Age'), { target: { value: '200' } });
    // Use fireEvent.submit to bypass HTML5 constraint validation in jsdom
    const form = document.querySelector('form');
    fireEvent.submit(form);

    // Use regex to avoid em-dash encoding issues
    expect(screen.getByText(/valid age/i)).toBeDefined();
  });
});
